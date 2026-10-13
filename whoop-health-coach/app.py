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
BASE = os.environ.get('PUBLIC_BASE_URL', 'https://whoop-health-coach.onrender.com').rstrip('/')
WHOOP = 'https://api.prod.whoop.com/developer/v2'
TOKEN = 'https://api.prod.whoop.com/oauth/oauth2/token'
SCOPES = 'read:sleep read:recovery read:workout read:cycles offline'
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
          CREATE TABLE IF NOT EXISTS mini_sync_status
          (id INTEGER PRIMARY KEY CHECK(id=1), last_success TEXT,
           last_error TEXT);''')


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
        if identity.get('openid') != owner():
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
            'appid': os.environ['WECHAT_APP_ID'],
            'secret': os.environ['WECHAT_APP_SECRET'],
            'js_code': code, 'grant_type': 'authorization_code'}, timeout=20)
        res.raise_for_status()
        data = res.json()
        openid = data.get('openid')
        if not openid:
            return jsonify(error='微信登录失败，请检查小程序配置'), 401
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(81613001)')
            cur.execute('SELECT openid FROM mini_owner WHERE id=1')
            row = cur.fetchone()
            if row:
                if row[0] != openid:
                    return jsonify(error='仅限已绑定的本人账号'), 403
            else:
                supplied = body.get('pairing_code', '')
                expected = os.environ['PAIRING_CODE']
                if not isinstance(supplied, str) or not secrets.compare_digest(supplied, expected):
                    return jsonify(error='请填写个人绑定码', needs_pairing=True), 403
                cur.execute('INSERT INTO mini_owner(id,openid) VALUES(1,%s)', (openid,))
        return jsonify(token=signer.dumps({'openid': openid}), expires_in=604800)
    except Exception:
        log.warning('Wechat login failed (details suppressed)')
        return jsonify(error='登录服务暂时不可用'), 503


LOGIN_HTML = '''<!doctype html><meta charset="utf-8"><title>连接 WHOOP</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<body style="background:#242f35;color:white;font-family:sans-serif;padding:32px">
<h2>小麦的 WHOOP</h2><p>输入你在 Render 配置的个人绑定码，开始授权。</p>
<form method="post"><input name="pairing_code" type="password" required
 autocomplete="off"><button type="submit">连接 WHOOP</button></form></body>'''


@app.route('/whoop/login', methods=['GET', 'POST'])
def whoop_login():
    if request.method == 'GET':
        return LOGIN_HTML
    if not permit_attempt():
        return '请求过多，请稍后再试', 429
    if not secrets.compare_digest(request.form.get('pairing_code', ''), os.environ['PAIRING_CODE']):
        return '绑定码不正确', 403
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_started'] = time.time()
    params = {'client_id': os.environ['WHOOP_CLIENT_ID'], 'response_type': 'code',
              'scope': SCOPES, 'redirect_uri': BASE + '/callback', 'state': state}
    return redirect('https://api.prod.whoop.com/oauth/oauth2/auth?' + urlencode(params))


@app.get('/callback')
def callback():
    expected = session.pop('oauth_state', None)
    started = session.pop('oauth_started', 0)
    received = request.args.get('state', '')
    if not expected or time.time() - started > 600 or not secrets.compare_digest(expected, received):
        return '授权校验失败，请重新从连接页面开始', 400
    code = request.args.get('code')
    if not code:
        return '授权取消或未返回授权码', 400
    try:
        res = requests.post(TOKEN, data={
            'grant_type': 'authorization_code', 'code': code,
            'client_id': os.environ['WHOOP_CLIENT_ID'],
            'client_secret': os.environ['WHOOP_CLIENT_SECRET'],
            'redirect_uri': BASE + '/callback'}, timeout=30)
        res.raise_for_status()
        data = res.json()
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(81613002)')
            cur.execute('''INSERT INTO mini_tokens VALUES(1,%s,%s,%s)
              ON CONFLICT(id) DO UPDATE SET access_token=EXCLUDED.access_token,
              refresh_token=EXCLUDED.refresh_token, expires_at=EXCLUDED.expires_at''',
              (data['access_token'], data['refresh_token'], time.time() + data['expires_in']))
        return 'WHOOP 连接成功。后台将在下一次同步任务中拉取数据，可关闭此页面。'
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


def sync_once():
    lock_conn = db()
    try:
        with lock_conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(81613003)')
            if not cur.fetchone()[0]:
                return
        start = (datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
        all_records = {}
        for kind, path in [('sleep','/activity/sleep'), ('recovery','/recovery'),
                           ('workout','/activity/workout'), ('cycle','/cycle')]:
            all_records[kind] = fetch_records(path, start)
        with db() as conn, conn.cursor() as cur:
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
        reason = '需要重新授权 WHOOP' if str(exc) == 'needs_authorization' else '同步失败，后台将自动重试'
        try:
            with db() as conn, conn.cursor() as cur:
                cur.execute('''INSERT INTO mini_sync_status VALUES(1,NULL,%s)
                  ON CONFLICT(id) DO UPDATE SET last_error=EXCLUDED.last_error''', (reason,))
        except Exception:
            pass
        log.warning('WHOOP sync failed (details suppressed)')
    finally:
        lock_conn.close()


@app.get('/api/dashboard')
@protected
def dashboard():
    with db() as conn, conn.cursor() as cur:
        cur.execute('SELECT kind,data FROM mini_records')
        data = {k: [] for k in ['sleep','recovery','workout','cycle']}
        for kind, record in cur.fetchall():
            data[kind].append(record)
        cur.execute('SELECT last_success,last_error FROM mini_sync_status WHERE id=1')
        status = cur.fetchone()
        cur.execute('SELECT 1 FROM mini_tokens WHERE id=1')
        connected = bool(cur.fetchone())
    for records in data.values():
        records.sort(key=lambda r: r.get('start') or r.get('created_at') or '', reverse=True)
    return jsonify(connected=connected, last_sync=status[0] if status else None,
                   sync_error=status[1] if status else None, records=data)


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
