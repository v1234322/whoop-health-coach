import os
import time
import secrets
import threading
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlencode

import requests
import psycopg2
from psycopg2.extras import Json
from flask import Flask, request, jsonify, session, redirect
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)
app.secret_key = os.environ['APP_SECRET_KEY']
app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax')
BASE = os.environ.get('PUBLIC_BASE_URL', 'https://97231013.xyz').rstrip('/')
WHOOP = 'https://api.prod.whoop.com/developer/v2'
TOKEN = 'https://api.prod.whoop.com/oauth/oauth2/token'
SCOPES = 'read:sleep read:recovery read:workout read:cycles read:profile read:body_measurement offline'
signer = URLSafeTimedSerializer(app.secret_key, salt='wechat-personal')
log = logging.getLogger('whoop')
logging.basicConfig(level=logging.INFO)


def db():
    return psycopg2.connect(os.environ['DATABASE_URL'], connect_timeout=15)


def initialize():
    with db() as conn, conn.cursor() as cur:
        cur.execute('''CREATE TABLE IF NOT EXISTS mini_owner
          (id INTEGER PRIMARY KEY CHECK(id=1), openid TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS mini_tokens
          (id INTEGER PRIMARY KEY CHECK(id=1), access_token TEXT NOT NULL,
           refresh_token TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL);
          CREATE TABLE IF NOT EXISTS mini_records
          (kind TEXT NOT NULL, record_id TEXT NOT NULL, data JSONB NOT NULL,
           PRIMARY KEY(kind,record_id));
          CREATE TABLE IF NOT EXISTS mini_metadata
          (kind TEXT PRIMARY KEY, data JSONB NOT NULL);
          CREATE TABLE IF NOT EXISTS mini_sync_status
          (id INTEGER PRIMARY KEY CHECK(id=1), last_success TEXT,
           last_error TEXT);
          CREATE TABLE IF NOT EXISTS mini_auth_links
          (nonce TEXT PRIMARY KEY, openid TEXT NOT NULL,
           expires_at DOUBLE PRECISION NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE);''')


def owner():
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT openid FROM mini_owner WHERE id=1')
        row = cur.fetchone()
        return row[0] if row else None


def protected(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        value = request.headers.get('Authorization', '')
        if not value.startswith('Bearer '):
            return jsonify(error='请先登录'), 401
        try:
            identity = signer.loads(value[7:], max_age=86400 * 7)
        except (BadSignature, SignatureExpired):
            return jsonify(error='登录已过期'), 401
        if not isinstance(identity, dict) or not identity.get('openid') or identity.get('openid') != owner():
            return jsonify(error='仅限本人访问'), 403
        return fn(*args, **kwargs)
    return run


# In-process rate limiting for the single-instance deployment.
_attempts = {}
_attempt_lock = threading.Lock()
def permit_attempt():
    key = request.remote_addr or 'unknown'
    now = time.time()
    with _attempt_lock:
        times = [t for t in _attempts.get(key, []) if now - t < 900]
        if len(times) >= 10:
            return False
        _attempts[key] = times + [now]
        if len(_attempts) > 5000:
            for k in list(_attempts):
                if not any(now - t < 900 for t in _attempts[k]):
                    del _attempts[k]
        return True


@app.get('/healthz')
def healthz():
    return jsonify(ok=True)


# Short-lived links bind only the intended WHOOP account to this one-user server.
LINK_TTL = 900
link_signer = URLSafeTimedSerializer(app.secret_key, salt='whoop-binding-link')


def session_result(openid):
    return dict(token=signer.dumps({'openid': openid}), expires_in=604800)


def binding_link(openid):
    nonce = secrets.token_urlsafe(32)
    with db() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM mini_auth_links WHERE expires_at < %s', (time.time(),))
        cur.execute('INSERT INTO mini_auth_links(nonce,openid,expires_at) VALUES(%s,%s,%s)',
                    (nonce, openid, time.time() + LINK_TTL))
    ticket = link_signer.dumps({'nonce': nonce, 'openid': openid})
    return dict(authorization_required=True, binding_ticket=ticket,
                auth_url=BASE + '/whoop/login?' + urlencode({'ticket': ticket}))


def load_ticket(ticket):
    value = link_signer.loads(ticket, max_age=LINK_TTL)
    if not isinstance(value, dict) or not value.get('nonce') or not value.get('openid'):
        raise BadSignature('invalid binding ticket')
    return value


@app.post('/api/wechat/login')
def wechat_login():
    if not permit_attempt():
        return jsonify(error='请求过多，请稍后重试'), 429
    body = request.get_json(silent=True) or {}
    code = body.get('code')
    if not isinstance(code, str) or not code or len(code) > 512:
        return jsonify(error='缺少微信登录 code'), 400
    try:
        res = requests.get('https://api.weixin.qq.com/sns/jscode2session', params={
            'appid': os.environ['WECHAT_APP_ID'], 'secret': os.environ['WECHAT_APP_SECRET'],
            'js_code': code, 'grant_type': 'authorization_code'}, timeout=20)
        res.raise_for_status()
        openid = res.json().get('openid')
        if not isinstance(openid, str) or not openid:
            return jsonify(error='微信登录失败，请检查小程序配置'), 401
        current = owner()
        if current and current != openid:
            return jsonify(error='仅限已绑定的本人账号'), 403
        if current:
            return jsonify(**session_result(openid))
        return jsonify(**binding_link(openid))
    except Exception:
        log.warning('Wechat login failed (details suppressed)')
        return jsonify(error='登录服务暂时不可用'), 503


@app.post('/api/whoop/authorize')
@protected
def authorize_again():
    return jsonify(**binding_link(owner()))


@app.post('/api/wechat/binding/status')
def binding_status():
    try:
        body = request.get_json(silent=True) or {}
        identity = load_ticket(body.get('binding_ticket', ''))
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT completed,expires_at FROM mini_auth_links WHERE nonce=%s AND openid=%s',
                        (identity['nonce'], identity['openid']))
            row = cur.fetchone()
        if not row or row[1] < time.time():
            return jsonify(error='连接链接已过期，请重新连接 WHOOP'), 410
        if row[0] and owner() == identity['openid']:
            return jsonify(bound=True, **session_result(identity['openid']))
        return jsonify(bound=False)
    except (BadSignature, SignatureExpired, TypeError):
        return jsonify(error='连接链接已过期，请重新连接 WHOOP'), 410
    except Exception:
        return jsonify(error='暂时无法检查绑定状态，请稍后重试'), 503


LOGIN_HTML = '''<!doctype html><html lang="zh"><meta charset="utf-8">
<title>连接 WHOOP</title><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="background:#182329;color:white;font-family:sans-serif;padding:32px">
<h2>连接你的 WHOOP</h2><p>点击继续，登录 WHOOP 并授权。成功后返回小程序即可，无需输入绑定码。</p>
<form method="post"><button style="padding:14px 24px;border:0;border-radius:20px">继续 WHOOP 授权</button></form></body></html>'''


@app.route('/whoop/login', methods=['GET', 'POST'])
def whoop_login():
    try:
        ticket = request.args.get('ticket', '')
        identity = load_ticket(ticket)
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT openid,expires_at,completed FROM mini_auth_links WHERE nonce=%s',
                        (identity['nonce'],))
            row = cur.fetchone()
        if not row or row[0] != identity['openid'] or row[1] < time.time() or row[2]:
            return '链接已失效，请返回小程序重新点击连接 WHOOP', 410
        current = owner()
        if current and current != identity['openid']:
            return '此服务器仅限已绑定的本人账号', 403
    except (BadSignature, SignatureExpired, TypeError):
        return '请从小程序点击连接 WHOOP，使用新生成的授权链接', 410
    if request.method == 'GET':
        response = app.make_response(LOGIN_HTML)
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response
    if not permit_attempt():
        return '请求过多，请稍后再试', 429
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_started'] = time.time()
    session['binding_ticket'] = ticket
    params = {'client_id': os.environ['WHOOP_CLIENT_ID'], 'response_type': 'code',
              'scope': SCOPES, 'redirect_uri': BASE + '/callback', 'state': state}
    return redirect('https://api.prod.whoop.com/oauth/oauth2/auth?' + urlencode(params))


def expected_whoop_id(cur):
    configured = os.environ.get('WHOOP_OWNER_ID', '').strip()
    if configured:
        return configured
    cur.execute("SELECT data FROM mini_metadata WHERE kind='binding_owner'")
    saved = cur.fetchone()
    if saved and isinstance(saved[0], dict) and saved[0].get('user_id') is not None:
        return str(saved[0]['user_id'])
    cur.execute("SELECT data FROM mini_metadata WHERE kind='profile'")
    row = cur.fetchone()
    if row and isinstance(row[0], dict) and row[0].get('user_id') is not None:
        return str(row[0]['user_id'])
    # Existing access/refresh tokens belong to the original account. Fail closed
    # if we cannot verify it; do not let the first visitor claim stored records.
    cur.execute('SELECT access_token,refresh_token,expires_at FROM mini_tokens WHERE id=1')
    row = cur.fetchone()
    if row:
        token = row[0]
        if row[2] <= time.time() + 120:
            result = requests.post(TOKEN, data={'grant_type':'refresh_token',
                'refresh_token':row[1], 'client_id':os.environ['WHOOP_CLIENT_ID'],
                'client_secret':os.environ['WHOOP_CLIENT_SECRET'], 'scope':'offline'}, timeout=30)
            result.raise_for_status()
            refreshed = result.json()
            token = refreshed['access_token']
            cur.execute('UPDATE mini_tokens SET access_token=%s,refresh_token=%s,expires_at=%s WHERE id=1',
                        (token,refreshed['refresh_token'],time.time()+refreshed['expires_in']))
        result = requests.get(WHOOP+'/user/profile/basic',
                              headers={'Authorization':'Bearer '+token},timeout=30)
        result.raise_for_status()
        uid = result.json().get('user_id')
        if uid is not None:
            cur.execute("INSERT INTO mini_metadata VALUES('binding_owner',%s) ON CONFLICT(kind) DO NOTHING",
                        (Json({'user_id':str(uid)}),))
            return str(uid)
    return None


@app.get('/callback')
def callback():
    expected = session.pop('oauth_state', None)
    started = session.pop('oauth_started', 0)
    ticket = session.pop('binding_ticket', '')
    received = request.args.get('state', '')
    if not expected or time.time() - started > 600 or not secrets.compare_digest(expected, received):
        return '授权校验失败，请重新从小程序连接', 400
    code = request.args.get('code')
    if not code:
        return '授权已取消，请返回小程序重新连接', 400
    try:
        identity = load_ticket(ticket)
        res = requests.post(TOKEN, data={'grant_type':'authorization_code','code':code,
            'client_id':os.environ['WHOOP_CLIENT_ID'], 'client_secret':os.environ['WHOOP_CLIENT_SECRET'],
            'redirect_uri':BASE+'/callback'},timeout=30)
        res.raise_for_status()
        tokens = res.json()
        profile_res = requests.get(WHOOP+'/user/profile/basic',
            headers={'Authorization':'Bearer '+tokens['access_token']},timeout=30)
        profile_res.raise_for_status()
        profile = profile_res.json()
        uid = profile.get('user_id')
        if uid is None:
            return '无法确认 WHOOP 账号身份，请重新授权个人资料权限', 403
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(81613001)')
            cur.execute('SELECT pg_advisory_xact_lock(81613002)')
            cur.execute('SELECT openid,expires_at,completed FROM mini_auth_links WHERE nonce=%s FOR UPDATE',
                        (identity['nonce'],))
            link = cur.fetchone()
            if not link or link[0] != identity['openid'] or link[1] < time.time() or link[2]:
                return '链接已失效，请返回小程序重新连接', 410
            cur.execute('SELECT openid FROM mini_owner WHERE id=1')
            bound = cur.fetchone()
            if bound and bound[0] != identity['openid']:
                return '此服务器已绑定其他微信账号', 403
            allowed = expected_whoop_id(cur)
            if allowed:
                matches = str(uid) == allowed
            else:
                email = os.environ.get('WHOOP_OWNER_EMAIL', '').strip().casefold()
                if not email:
                    return '请先在服务器配置 WHOOP_OWNER_EMAIL（本人 WHOOP 登录邮箱），再重新连接', 409
                matches = str(profile.get('email') or '').strip().casefold() == email
            if not matches:
                return 'WHOOP 账号不匹配，请使用此服务器的本人 WHOOP 账号', 403
            cur.execute("INSERT INTO mini_metadata VALUES('binding_owner',%s) ON CONFLICT(kind) DO NOTHING",
                        (Json({'user_id':str(uid)}),))
            cur.execute('INSERT INTO mini_owner VALUES(1,%s) ON CONFLICT(id) DO NOTHING', (identity['openid'],))
            cur.execute('''INSERT INTO mini_tokens VALUES(1,%s,%s,%s)
              ON CONFLICT(id) DO UPDATE SET access_token=EXCLUDED.access_token,
              refresh_token=EXCLUDED.refresh_token,expires_at=EXCLUDED.expires_at''',
                        (tokens['access_token'],tokens['refresh_token'],time.time()+tokens['expires_in']))
            cur.execute("INSERT INTO mini_metadata VALUES('profile',%s) ON CONFLICT(kind) DO UPDATE SET data=EXCLUDED.data",(Json(profile),))
            cur.execute('UPDATE mini_auth_links SET completed=TRUE WHERE nonce=%s',(identity['nonce'],))
        threading.Thread(target=sync_once,daemon=True).start()
        return 'WHOOP 已连接，微信账号已自动绑定。请返回小程序，数据正在同步。'
    except (BadSignature, SignatureExpired):
        return '授权链接已过期，请返回小程序重新连接', 410
    except Exception:
        log.warning('OAuth callback failed (details suppressed)')
        return 'WHOOP 授权保存失败，请检查后台配置后重新连接', 502


def access_token(force=False):
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(81613002)')
        cur.execute('SELECT access_token,refresh_token,expires_at FROM mini_tokens WHERE id=1 FOR UPDATE')
        row = cur.fetchone()
        if not row:
            raise ValueError('needs_authorization')
        if not force and row[2] > time.time() + 120:
            return row[0]
        res = requests.post(TOKEN, data={
            'grant_type': 'refresh_token', 'refresh_token': row[1],
            'client_id': os.environ['WHOOP_CLIENT_ID'],
            'client_secret': os.environ['WHOOP_CLIENT_SECRET'], 'scope': 'offline'}, timeout=30)
        if res.status_code in (400, 401):
            raise ValueError('needs_authorization')
        res.raise_for_status()
        data = res.json()
        cur.execute('UPDATE mini_tokens SET access_token=%s,refresh_token=%s,expires_at=%s WHERE id=1',
                    (data['access_token'], data['refresh_token'], time.time()+data['expires_in']))
        return data['access_token']


def fetch_records(path, start):
    records = []
    token = access_token()
    params = {'start': start, 'limit': 25}
    for page in range(200):
        for attempt in range(3):
            res = requests.get(WHOOP + path, params=params,
                               headers={'Authorization': 'Bearer ' + token}, timeout=30)
            if res.status_code == 401 and attempt == 0:
                token = access_token(force=True)
                continue
            if res.status_code == 429 or res.status_code >= 500:
                if attempt < 2:
                    time.sleep(min(15, 2 ** (attempt + 1)))
                    continue
            res.raise_for_status()
            break
        data = res.json()
        records.extend(data['records'])
        next_token = data.get('next_token')
        if not next_token:
            return records
        params['nextToken'] = next_token
    raise ValueError('pagination_limit')


def fetch_object(path):
    token = access_token()
    for attempt in range(3):
        res = requests.get(WHOOP + path, headers={'Authorization': 'Bearer ' + token}, timeout=30)
        if res.status_code == 401 and attempt == 0:
            token = access_token(force=True)
            continue
        if res.status_code == 403:
            return None
        if (res.status_code == 429 or res.status_code >= 500) and attempt < 2:
            time.sleep(2 ** (attempt + 1))
            continue
        res.raise_for_status()
        return res.json()
    raise ValueError('metadata_fetch_failed')


def safe_sync_reason(exc, stage):
    if isinstance(exc, ValueError) and exc.args == ('needs_authorization',):
        return '需要重新授权 WHOOP'
    if isinstance(exc, requests.exceptions.HTTPError):
        code = exc.response.status_code if exc.response is not None else 0
        label = {400:'请求参数未被接受',401:'授权失效',403:'缺少接口权限',404:'接口或记录未找到',429:'请求频率受限'}.get(code,'WHOOP 服务异常')
        return f'{stage}：{label}（HTTP {code}）'
    if isinstance(exc, requests.exceptions.Timeout):
        return stage + '：WHOOP 请求超时，稍后重试'
    if isinstance(exc, requests.exceptions.ConnectionError):
        return stage + '：无法连接 WHOOP，稍后重试'
    if isinstance(exc, psycopg2.Error):
        return stage + '：数据库操作失败，请检查数据库状态'
    if isinstance(exc, (KeyError, TypeError)):
        return stage + '：返回数据格式不符合预期'
    if isinstance(exc, ValueError) and exc.args == ('pagination_limit',):
        return stage + '：历史数据超过单次分页限制'
    return stage + '：同步失败（' + type(exc).__name__ + '）'


def sync_once():
    lock_conn = None
    stage = '连接数据库'
    try:
        lock_conn = db()
        with lock_conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(81613003)')
            if not cur.fetchone()[0]:
                return
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM mini_metadata WHERE kind='history_loaded'")
            history_loaded = bool(cur.fetchone())
        lookback = 30 if history_loaded else 360
        start = (datetime.now(timezone.utc)-timedelta(days=lookback)).isoformat()
        all_records = {}
        for kind, path in [('sleep','/activity/sleep'), ('recovery','/recovery'),
                           ('workout','/activity/workout'), ('cycle','/cycle')]:
            stage = {'sleep':'睡眠数据','recovery':'恢复数据','workout':'运动数据','cycle':'身体负荷数据'}[kind]
            all_records[kind] = fetch_records(path, start)
        metadata = {}
        warnings = []
        for kind, path, label in [('profile','/user/profile/basic','个人资料'), ('body','/user/measurement/body','身体测量')]:
            try:
                value = fetch_object(path)
                if value is None:
                    warnings.append(label + '：缺少权限，请重新授权')
                    metadata[kind] = None
                else:
                    metadata[kind] = value
            except Exception as exc:
                warning = safe_sync_reason(exc, label)
                warnings.append(warning)
                log.warning('%s', warning)
        metadata['warnings'] = warnings
        stage = '保存同步数据'
        with db() as conn, conn.cursor() as cur:
            metadata['history_loaded'] = True
            for kind, value in metadata.items():
                cur.execute('INSERT INTO mini_metadata VALUES(%s,%s) ON CONFLICT(kind) DO UPDATE SET data=EXCLUDED.data', (kind, Json(value)))
            for kind, records in all_records.items():
                for record in records:
                    identity = record.get('cycle_id') if kind == 'recovery' else record['id']
                    cur.execute('''INSERT INTO mini_records VALUES(%s,%s,%s)
                      ON CONFLICT(kind,record_id) DO UPDATE SET data=EXCLUDED.data''',
                      (kind, str(identity), Json(record)))
            cur.execute('''INSERT INTO mini_sync_status VALUES(1,%s,NULL)
              ON CONFLICT(id) DO UPDATE SET last_success=EXCLUDED.last_success,last_error=NULL''',
              (datetime.now(timezone.utc).isoformat(),))
        log.info('WHOOP sync completed')
    except Exception as exc:
        reason = safe_sync_reason(exc, stage)
        try:
            with db() as conn, conn.cursor() as cur:
                cur.execute('''INSERT INTO mini_sync_status VALUES(1,NULL,%s)
                  ON CONFLICT(id) DO UPDATE SET last_error=EXCLUDED.last_error''', (reason,))
        except Exception:
            pass
        log.warning('WHOOP sync failed: %s', reason)
    finally:
        if lock_conn is not None:
            lock_conn.close()


@app.get('/api/dashboard')
@protected
def dashboard():
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT kind,data FROM mini_records')
        data = {k: [] for k in ['sleep','recovery','workout','cycle']}
        for kind, record in cur.fetchall():
            data[kind].append(record)
        cur.execute('SELECT kind,data FROM mini_metadata')
        metadata = dict(cur.fetchall())
        cur.execute('SELECT last_success,last_error FROM mini_sync_status WHERE id=1')
        status = cur.fetchone()
        cur.execute('SELECT 1 FROM mini_tokens WHERE id=1')
        connected = bool(cur.fetchone())
    for records in data.values():
        records.sort(key=lambda r: r.get('start') or r.get('created_at') or '', reverse=True)
    return jsonify(connected=connected, last_sync=status[0] if status else None,
                   sync_error=status[1] if status else None, records=data,
                   profile=metadata.get('profile'), body=metadata.get('body'),
                   metadata_warning='；'.join(metadata.get('warnings') or []) or ('请重新授权，以读取个人资料和身体测量' if any(metadata.get(k) is None for k in ['profile','body']) else ''))


@app.post('/api/sync')
@protected
def request_sync():
    threading.Thread(target=sync_once, daemon=True).start()
    return jsonify(message='已发起同步'), 202


def sync_loop():
    while True:
        try:
            sync_once()
        except Exception:
            log.warning('Sync task temporarily unavailable')
        time.sleep(1800)


initialize()
if os.environ.get('ENABLE_AUTO_SYNC', 'false').lower() == 'true':
    threading.Thread(target=sync_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))
