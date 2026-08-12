import json
import os
import hmac

print("WHOOP HEALTH COACH STARTED")

import psycopg2

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, Response

from functools import wraps

import requests

from openai import OpenAI

WHOOP_API_BASE = "https://api.prod.whoop.com/developer/v2"


# =========================
# DeepSeek
# =========================

client = OpenAI(
    api_key=os.environ.get(
        "DEEPSEEK_API_KEY"
    ),
    base_url="https://api.deepseek.com"
)


# =========================
# Flask
# =========================

app = Flask(__name__)

app.json.ensure_ascii = False

app.config["JSON_AS_ASCII"] = False


def require_chatgpt_api_key(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        expected_key = os.getenv(
            "CHATGPT_ACTION_API_KEY"
        )

        if not expected_key:

            return jsonify({
                "success": False,
                "error": "ChatGPT API authentication is not configured"
            }), 503

        authorization = request.headers.get(
            "Authorization",
            ""
        )

        if not authorization.startswith("Bearer "):

            return jsonify({
                "success": False,
                "error": "Authorization header is required"
            }), 401

        provided_key = authorization[
            len("Bearer "):
        ].strip()

        if not hmac.compare_digest(
            provided_key,
            expected_key
        ):

            return jsonify({
                "success": False,
                "error": "Invalid API key"
            }), 403

        return func(*args, **kwargs)

    return wrapper


# =========================
# 数据库连接
# =========================

def get_db_connection():

    import os
    import psycopg2


    database_url = os.getenv(
        "DATABASE_URL"
    )


    if not database_url:

        raise Exception(
            "DATABASE_URL NOT FOUND"
        )


    print(
        "POSTGRES DATABASE CONNECTING"
    )


    conn = psycopg2.connect(
        database_url
    )


    return conn


# =========================
# 保存 refresh token
# =========================

def save_refresh_token(token):

    if not token:
        print("NO REFRESH TOKEN")
        return


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT id
        FROM tokens
        LIMIT 1
        """
    )

    row = cur.fetchone()


    if row:

        cur.execute(
            """
            UPDATE tokens
            SET refresh_token=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (
                token,
                row[0]
            )
        )

        print(
            "REFRESH TOKEN UPDATED"
        )


    else:

        cur.execute(
            """
            INSERT INTO tokens
            (
                refresh_token,
                updated_at
            )
            VALUES
            (
                %s,
                CURRENT_TIMESTAMP
            )
            """,
            (
                token,
            )
        )

        print(
            "REFRESH TOKEN INSERTED"
        )


    conn.commit()

    cur.close()

    conn.close()


    print(
        "REFRESH TOKEN SAVED"
    )


# ==========================
# 从数据库读取最新 refresh token
# ==========================

def load_refresh_token():

    conn = get_db_connection()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT refresh_token
        FROM tokens
        WHERE refresh_token IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """
    )


    row = cur.fetchone()


    print("TOKEN DATABASE CHECK:")
    print("DB TOKEN ROW:", row)


    cur.close()
    conn.close()


    if row:

        print(
            "DATABASE REFRESH TOKEN FOUND"
        )

        return row[0]


    print(
        "DATABASE REFRESH TOKEN EMPTY"
    )

    return None
    
    
WHOOP_CLIENT_ID = os.environ.get(
    "WHOOP_CLIENT_ID",
    ""
).strip()

print(
    "START CLIENT ID:",
    WHOOP_CLIENT_ID[:6],
    "...",
    WHOOP_CLIENT_ID[-4:]
)


WHOOP_CLIENT_SECRET = os.environ.get(
    "WHOOP_CLIENT_SECRET",
    ""
).strip()



WHOOP_ACCESS_TOKEN = None


print("========== ENV CHECK ==========")

refresh_env = os.getenv(
    "WHOOP_REFRESH_TOKEN"
)


print(
    "REFRESH TOKEN:",
    bool(refresh_env)
)


if refresh_env:

    print(
        "TOKEN LENGTH:",
        len(refresh_env)
    )

else:

    print(
        "TOKEN LENGTH: 0"
    )
    
print("==============================")


# ==========================
# 启动时同步环境变量 token
# ==========================

def ensure_refresh_token():

    db_token = load_refresh_token()


    if db_token:

        print(
            "REFRESH TOKEN EXISTS IN DATABASE"
        )

        return db_token



    env_token = os.getenv(
        "WHOOP_REFRESH_TOKEN"
    )


    if env_token:


        print(
            "INITIALIZING REFRESH TOKEN FROM ENV"
        )


        save_refresh_token(
            env_token
        )


        print(
            "INITIAL REFRESH TOKEN SAVED"
        )


        return env_token



    print(
        "NO REFRESH TOKEN FOUND"
    )


    return None

# ==========================
# 保存 access token
# ==========================

def save_access_token_to_db(token):

    if not token:
        print("NO ACCESS TOKEN")
        return


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            SELECT id
            FROM tokens
            LIMIT 1
            """
        )

        row = cursor.fetchone()


        if row:


            cursor.execute(
                """
                UPDATE tokens
                SET access_token = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    token,
                    row[0]
                )
            )


            print(
                "ACCESS TOKEN UPDATED"
            )


        else:


            cursor.execute(
                """
                INSERT INTO tokens
                (
                    access_token,
                    updated_at
                )
                VALUES
                (
                    ?,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    token,
                )
            )


            print(
                "ACCESS TOKEN SAVED"
            )


        conn.commit()


    except Exception as e:


        print(
            "SAVE ACCESS TOKEN ERROR:",
            e
        )


    finally:

        cursor.close()

        conn.close()


# =========================
# 获取 Access Token
# =========================

def get_access_token():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT access_token
            FROM tokens
            WHERE access_token IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """
        )


        row = cur.fetchone()


        print(
            "DATABASE ACCESS TOKEN RESULT:",
            row
        )


        if row and row[0]:

            print(
                "USING DATABASE ACCESS TOKEN"
            )

            return row[0]



    except Exception as e:

        print(
            "GET ACCESS TOKEN DB ERROR:",
            e
        )


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()



    print(
        "NO ACCESS TOKEN, REFRESHING"
    )


    access_token = refresh_access_token()


    if access_token:

        save_access_token_to_db(
            access_token
        )


        print(
            "ACCESS TOKEN SAVED AFTER REFRESH"
        )


    return access_token

# =========================
# 刷新 Access Token
# =========================

def refresh_access_token():

    refresh_token = load_refresh_token()


    if refresh_token:

        print(
            "TOKEN SOURCE: DATABASE"
        )

    else:

        refresh_token = os.getenv(
            "WHOOP_REFRESH_TOKEN"
        )

        print(
            "TOKEN SOURCE: ENV"
        )


    if not refresh_token:

        raise Exception(
            "NO REFRESH TOKEN AVAILABLE"
        )


    client_id = os.getenv(
        "WHOOP_CLIENT_ID"
    )

    client_secret = os.getenv(
        "WHOOP_CLIENT_SECRET"
    )


    if not client_id:
        raise Exception(
            "WHOOP_CLIENT_ID NOT FOUND"
        )


    if not client_secret:
        raise Exception(
            "WHOOP_CLIENT_SECRET NOT FOUND"
        )


    payload = {

        "grant_type":
        "refresh_token",

        "refresh_token":
        refresh_token.strip(),

        "client_id":
        client_id.strip(),

        "client_secret":
        client_secret.strip(),

    }


    print(
        "REFRESH REQUEST:",
        {
            "grant_type":
            payload["grant_type"],

            "client_id":
            client_id[:6] + "...",

            "refresh_length":
            len(refresh_token)
        }
    )


    response = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",

        data=payload,

        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        },

        timeout=30

    )


    print(
        "REFRESH STATUS:",
        response.status_code
    )

    print(
        "REFRESH RESPONSE:",
        response.text
    )


    if response.status_code != 200:

        raise Exception(
            "REFRESH FAILED: "
            + response.text
        )


    token_data = response.json()


    access_token = token_data.get(
        "access_token"
    )


    new_refresh_token = token_data.get(
        "refresh_token"
    )


    if new_refresh_token:

        save_refresh_token(
            new_refresh_token
        )

        print(
            "NEW REFRESH TOKEN SAVED"
        )


    if not access_token:

        raise Exception(
            "NO ACCESS TOKEN RETURNED"
        )


    save_access_token_to_db(
        access_token
    )


    print(
        "NEW ACCESS TOKEN SAVED"
    )

    return access_token

# =========================
# WHOOP API 请求函数
# =========================

def whoop_get(endpoint):


    token = get_access_token()


    if not token:

        raise Exception(
            "NO ACCESS TOKEN"
        )


    r = requests.get(

        WHOOP_API_BASE + endpoint,

        headers={

            "Authorization":
            f"Bearer {token}",

            "Accept":
            "application/json"

        },

        timeout=30

    )


    print(
        "WHOOP STATUS:",
        r.status_code
    )


    if r.status_code == 401:


        print(
            "ACCESS TOKEN EXPIRED, REFRESHING"
        )


        token = refresh_access_token()


        r = requests.get(

            WHOOP_API_BASE + endpoint,

            headers={

                "Authorization":
                f"Bearer {token}",

                "Accept":
                "application/json"

            },

            timeout=30

        )

        print(
            "WHOOP RETRY STATUS:",
            r.status_code
        )


    print(
        "WHOOP RESPONSE:",
        r.text[:1000]
    )


    r.raise_for_status()


    return r.json()


def clean_duplicate_daily_metrics():

    conn = get_db_connection()

    cur = conn.cursor()

    try:

        cur.execute(
            """
            DELETE FROM daily_metrics
            WHERE id NOT IN
            (
                SELECT MAX(id)
                FROM daily_metrics
                GROUP BY report_date
            )
            """
        )

        deleted = cur.rowcount

        conn.commit()

        print(
            "DELETE DUPLICATE ROWS:",
            deleted
        )


    except Exception as e:

        print(
            "CLEAN ERROR:",
            e
        )


    finally:

        cur.close()
        conn.close()



# =========================
# 数据库初始化
# =========================

def init_db():

    conn = get_db_connection()

    cursor = conn.cursor()


    # =========================
    # WHOOP TOKEN
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tokens(

        id SERIAL PRIMARY KEY,

        access_token TEXT,

        refresh_token TEXT,

        expires_at BIGINT,

        updated_at TIMESTAMP DEFAULT NOW()

    )
    """)

   
    cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='tokens'
    """)

    print(
        "TOKENS COLUMNS:",
        cursor.fetchall()
    )

    # =========================
    # 重建 daily_metrics
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_metrics (

        id SERIAL PRIMARY KEY,

        report_date TEXT UNIQUE,

        recovery_score REAL,

        hrv REAL,

        resting_heart_rate REAL,

        sleep_score REAL,

        sleep_duration REAL,

        sleep_efficiency REAL,

        deep_sleep_duration REAL,

        rem_sleep_duration REAL,

        cycle_strain REAL,

        workout_data TEXT,

        health_score REAL

    )
    """)

    # =========================
    # 添加 health_score 字段
    # =========================

    try:

        cursor.execute(
            """
            ALTER TABLE daily_metrics
            ADD COLUMN health_score REAL
            """
        )

        print(
            "HEALTH SCORE COLUMN ADDED"
        )

    except Exception:

        conn.rollback()

    

    # =========================
    # 系统状态表
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_status (

        id SERIAL PRIMARY KEY,

        last_success_time TEXT

    )
    """)


    try:

        conn.commit()

    except Exception as e:

        print(
            "DATABASE INIT ERROR:",
            e
        )

        conn.rollback()


    conn.close()


    print("DATABASE READY")

    clean_duplicate_daily_metrics()

    ensure_refresh_token()


    
init_db()


@app.route("/callback")
def callback():

    print(
        "CALLBACK URL:",
        request.url
    )

    code = request.args.get("code")

    state = request.args.get("state")

    print(
        "CODE:",
        code
    )

    print(
        "STATE:",
        state
    )


    if not code:
        return "NO CODE"

    payload = {

        "grant_type": "authorization_code",

        "code": code,

        "client_id": WHOOP_CLIENT_ID,

        "client_secret": WHOOP_CLIENT_SECRET,

        "redirect_uri":
        "https://whoop-health-coach.onrender.com/callback"

    }


    response = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",

        data=payload,

        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        },

        timeout=30

    )


    print(
        "TOKEN RESPONSE:",
        response.text
    )


    response.raise_for_status()


    token_data = response.json()


    access_token = token_data.get(
        "access_token"
    )

    refresh_token = token_data.get(
        "refresh_token"
    )


    if refresh_token:

        save_refresh_token(
            refresh_token
        )

        print(
            "REFRESH TOKEN SAVED"
        )


    if access_token:

        save_access_token_to_db(
            access_token
        )

        print(
            "ACCESS TOKEN SAVED"
        )


    return "WHOOP AUTH SUCCESS"


@app.route("/whoop/login")
def whoop_login():

    import secrets

    state = secrets.token_urlsafe(16)


    auth_url = (
        "https://api.prod.whoop.com/oauth/oauth2/auth?"
        f"client_id={WHOOP_CLIENT_ID}"
        "&response_type=code"
        "&scope=read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement offline"
        "&redirect_uri=https://whoop-health-coach.onrender.com/callback"
        f"&state={state}"
    )


    print("WHOOP AUTH URL:")
    print(auth_url)


    return redirect(auth_url)
    

@app.route("/clear-token")
def clear_token():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM tokens"
        )

        conn.commit()

        cur.close()
        conn.close()

        return "TOKEN CLEARED"

    except Exception as e:

        return f"CLEAR TOKEN ERROR: {e}"


def get_latest_sleep():

    try:

        # 1. 获取睡眠列表
        sleep_list = whoop_get(
            "/activity/sleep"
        )


        print(
            "========== SLEEP LIST =========="
        )

        print(
            sleep_list
        )


        records = sleep_list.get(
            "records",
            []
        )


        if not records:

            print(
                "NO SLEEP RECORD"
            )

            return {}


        # 2. 找最新一条非小睡睡眠

        latest_sleep = None


        for record in records:

            if not record.get(
                "nap",
                False
            ):

                latest_sleep = record

                break


        if not latest_sleep:

            latest_sleep = records[0]


        sleep_id = latest_sleep.get(
            "id"
        )


        print(
            "LATEST SLEEP ID:",
            sleep_id
        )


        if not sleep_id:

            return latest_sleep



        # 3. 获取详细睡眠数据

        sleep_detail = whoop_get(
            f"/activity/sleep/{sleep_id}"
        )


        print(
            "========== SLEEP DETAIL =========="
        )

        print(
            sleep_detail
        )


        return sleep_detail



    except Exception as e:


        print(
            "GET SLEEP ERROR:",
            e
        )


        return {}
        


@app.route("/whoop/today")
def today():

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_score,
                sleep_duration,
                sleep_efficiency,
                deep_sleep_duration,
                rem_sleep_duration,
                cycle_strain,
                workout_data,
                health_score
                
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 1
            """
        )

        row = cur.fetchone()

        cur.close()
        conn.close()


        if not row:
            return "暂无健康数据"


        metrics = {

            "date": row[0],

            "recovery_score": row[1],

            "hrv": row[2],

            "resting_heart_rate": row[3],

            "sleep_score": row[4],

            "sleep_duration": row[5],

            "sleep_efficiency": row[6],

            "deep_sleep_duration": row[7],

            "rem_sleep_duration": row[8],

            "cycle_strain": row[9],

            "work_data": row[10],

            "health_score": row[11]

        }

        health_level = get_health_level(
            metrics.get("health_score",0)
        )

        recovery = metrics.get("recovery_score",0)

        if recovery >= 67:
            recovery_color = "🟢"
        elif recovery >= 34:
            recovery_color = "🟡"
        else:
            recovery_color = "🔴"

        strain_level = get_strain_level(
            metrics.get("cycle_strain",0)
        )

        
        # =========================
        # 今日健康评分
        # =========================

        recovery = metrics.get("recovery_score", 0) or 0
        sleep_score = metrics.get("sleep_score", 0) or 0
        hrv = metrics.get("hrv", 0) or 0
        rest_hr = metrics.get("resting_heart_rate", 0) or 0


        # HRV评分（简单标准化）
        hrv_score = min(
            max(hrv / 60 * 100, 0),
            100
        )


        # 静息心率评分（越低越好）
        rest_hr_score = max(
            min((80 - rest_hr) / 30 * 100, 100),
            0
        )


        health_score = (
            recovery * 0.4
            +
            sleep_score * 0.3
            +
            hrv_score * 0.2
            +
            rest_hr_score * 0.1
        )


        health_score = round(
            health_score,
            1
        )

        metrics["health_score"] = health_score

        save_daily_data(
            metrics
        )
        

        # =========================
        # 获取最近7天趋势
        # =========================

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                sleep_duration,
                sleep_score,
                cycle_strain
                
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 7
            """
        )

        trend_rows = cur.fetchall()

        cur.close()
        conn.close()


        def calculate_average(rows, index):

            values = [
                float(r[index])
                for r in rows
                if r[index] is not None
            ]

            if not values:
                return 0

            return sum(values) / len(values)



        if trend_rows:

            avg_recovery = calculate_average(
                trend_rows,
                1
            )

            avg_hrv = calculate_average(
                trend_rows,
                2
            )

            avg_sleep = calculate_average(
                trend_rows,
                3
            )

            avg_sleep_score = calculate_average(
                trend_rows,
                4
            )

            avg_strain = calculate_average(
                trend_rows,
                5
            )


        else:

            avg_recovery = 0
            avg_hrv = 0
            avg_sleep = 0
            avg_sleep_score = 0
            avg_strain = 0


    
        # =========================
        # AI健康教练
        # =========================

        ai_prompt = f"""

        WHOOP 数据:


        今日健康评分:
        {health_score}/100

        Recovery:
        {metrics.get("recovery_score")}

        HRV:
        {metrics.get("hrv")}

        静息心率:
        {metrics.get("resting_heart_rate")}

        睡眠:
        {metrics.get("sleep_duration")}

        睡眠评分:
        {metrics.get("sleep_score")}

        睡眠效率:
        {metrics.get("sleep_efficiency")}

        深度睡眠:
        {metrics.get("deep_sleep_duration")}

        REM:
        {metrics.get("rem_sleep_duration")}

        Strain:
        {metrics.get("cycle_strain")}


        最近7天趋势:

        平均 Recovery:
        {avg_recovery:.1f}

        平均 HRV:
        {avg_hrv:.1f}

        平均睡眠:
        {avg_sleep:.1f} 小时
                
        平均睡眠评分:
        {avg_sleep_score:.1f}
            
        平均 Strain:
        {avg_strain:.1f}


        请结合今天状态和最近7天趋势，
        生成今日健康教练建议。

        重点分析：

        1. 今日恢复是否高于或低于近期水平
        2. 是否存在疲劳累积
        3. 今日训练强度建议
        4. 未来1-3天调整方案

        """


        ai_summary = generate_ai_summary(
            ai_prompt
        )


        return f"""

        <html>

        <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
>

        <title>WHOOP 今日健康报告</title>

        <style>

        body {{
            font-family: Arial, sans-serif;
            background:#f5f7fa;
            padding:30px;
        }}

        .card {{
            background:white;
            border-radius:20px;
            padding:25px;
            margin-bottom:20px;
            box-shadow:0 4px 15px rgba(0,0,0,0.08);
        }}

        .title {{
            font-size:32px;
            font-weight:bold;
        }}

        .metric {{
            font-size:22px;
            margin:12px 0;
        }}


        .ai-text {{
            white-space:pre-line;
            font-size:20px;
            line-height:2;
        }}
        

        .ai-text::first-line {{

        font-weight:bold;

        }}
        

        .ai-text strong {{

            font-size:28px;
            font-weight:bold;
            margin-top:35px;
            margin-bottom:15px;

        }}


        .ai-text h3 {{

            font-size:30px;
            margin-top:35px;
            margin-bottom:15px;
            font-weight:bold;

        }}


        .coach-header {{

            background:#fafafa;
            border-radius:18px;
            padding:15px;
            margin-bottom:15px;
            text-align:center;

        }}


        .coach-score {{

            font-size:32px;
            font-weight:bold;
            margin:5px;

        }}


        .coach-status {{

            font-size:22px;

        }}


        .coach-section {{

            margin-top:25px;
            padding-top:15px;
            border-top:1px solid #eee;

        }}


        .score{{

        font-size:48px;

        font-weight:bold;

        text-align:center;

        margin:20px;

        }}



        .status{{

        font-size:22px;

        text-align:center;

        }}



        .whoop-grid {{

            display:grid;

            grid-template-columns:repeat(3,1fr);

            gap:20px;

            width:100%;

        }}


        .whoop-item {{

            background:#fafafa;
            
            border-radius:18px;
            
            padding:25px;
            
            text-align:center;

        }}


        .whoop-item strong {{

            display:block;

            font-size:42px;

            margin-top:12px;

        }}
        

        .whoop-label {{

            font-size:20px;
            font-weight:bold;

        }}
        

        .strain-level {{

            display:block;

            margin-top:8px;

            font-size:16px;

        }}

        .two-column {{

            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:20px;
            width:100%;

        }}
        
        .small-card {{

            background:white;
            border-radius:20px;
            padding:20px;
            box-shadow:0 4px 15px rgba(0,0,0,0.08);

        }}


        .coach-advice {{

            margin-top:20px;
            padding:20px;
            background:#fafafa;
            border-radius:18px;
            font-size:22px;
            line-height:1.8;

        }}

        </style>

        </head>


        <body>


        <div class="card">

        <div class="title">
        🧠 WHOOP 今日健康报告
        </div>

        </div>

        <div class="card">

        <h2>🧠 今日健康评分</h2>

        <div class="score">

        {metrics.get("health_score")} / 100

        </div>

        <div class="status">

        {health_level}

        </div>

        </div>



        <div class="card">

        <h2>📊 今日 WHOOP 状态</h2>


        <div class="whoop-grid">


        <div class="whoop-item">

        <span class="whoop-label">
        {recovery_color} Recovery
        </span>

        <strong>
        {metrics.get("recovery_score"):.1f}%
        </strong>

        </div>



        <div class="whoop-item">

        <span class="whoop-label">
        🔥 Strain
        </span>

        <strong>
        {metrics.get("cycle_strain"):.1f}
        </strong>

        <div class="strain-level">
        {strain_level}
        </div>

        </div>
        

        <div class="whoop-item">

        <span class="whoop-label">
        😴 Sleep
        </span>


        <strong>
        {metrics.get("sleep_score"):.1f}%
        </strong>

        </div>

        </div>

        </div>



        <div class="two-column">


        <div class="small-card">

        <h2>❤️ 身体指标</h2>

        <div class="metric">
        HRV: {metrics.get("hrv"):.1f} ms
        </div>

        <div class="metric">
        静息心率: {metrics.get("resting_heart_rate")} bpm
        </div>

        </div>


        <div class="small-card">

        <h2>😴 睡眠详情</h2>

        <div class="metric">
        睡眠时长: {metrics.get("sleep_duration")} 小时
        </div>

        <div class="metric">
        睡眠效率: {metrics.get("sleep_efficiency"):.1f}%
        </div>

        <div class="metric">
        深度睡眠: {metrics.get("deep_sleep_duration")} 小时
        </div>

        <div class="metric">
        REM睡眠: {metrics.get("rem_sleep_duration")} 小时
        </div>

        </div>


        </div>



        <div class="card">

        <h2>🤖 WHOOP AI Coach</h2>

        <div class="ai-text">

        {ai_summary}

        </div>


        </div>


        </body>

        </html>

        """


    except Exception as e:

        print(
            "TODAY ERROR:",
            e
        )

        return str(e)



@app.route("/whoop/trend")
def trend():

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                cycle_strain,
                health_score

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 7
            """
        )


        rows = cur.fetchall()

        print("TREND ROWS:", rows)


        
        cur.close()

        conn.close()


        if not rows:

            return """
            <h1>
            暂无历史数据
            </h1>
            """


        rows = list(
            reversed(rows)
        )


        # =========================
        # 7天趋势统计
        # =========================
        def avg_value(index):

            values = []

            for r in rows:

                    value = r[index]

                    if value is None:
                        continue

                        values.append(
                            float(value)
                        )

                    try:
                        values.append(float(value))

                    except (TypeError, ValueError):
                        continue

            if len(values) == 0:
                return 0


            return sum(values) / len(values)


        avg_recovery = avg_value(1)
        avg_hrv = avg_value(2)
        avg_resting_hr = avg_value(3)
        avg_sleep = avg_value(4)
        avg_sleep_score = avg_value(5)
        avg_strain = avg_value(6)
        avg_health_score = avg_value(7)

        print("AVG HEALTH SCORE:", avg_health_score)

        summary = f"""

<div style="
background:white;
padding:25px;
margin:20px;
border-radius:15px;
">

<h2>
📊 7天趋势总结
</h2>


<p>
🧠 平均健康评分:
{round(avg_health_score,1) if avg_health_score is not None else "-"}
</p>

<p>
🟢 平均 Recovery:
{round(avg_recovery,1) if avg_recovery is not None else "-"}%
</p>

<p>
❤️ 平均 HRV:
{round(avg_hrv,1) if avg_hrv is not None else "-"} ms
</p>

<p>
❤️ 平均静息心率:
{round(avg_resting_hr,1) if avg_resting_hr is not None else "-"} bpm
</p>

<p>
😴 平均睡眠:
{round(avg_sleep,2) if avg_sleep is not None else "-"} 小时
</p>

<p>
⭐ 平均睡眠评分:
{round(avg_sleep_score,1) if avg_sleep_score is not None else "-"}
</p>

<p>
🔥 平均 Strain:
{round(avg_strain,1) if avg_strain is not None else "-"}
</p>

</div>

"""


        cards = ""

        for r in rows:

            cards += f"""

        <div style="
        background:white;
        padding:20px;
        margin:15px;
        border-radius:15px;
        ">

        <h3>
        📅 {r[0]}
        </h3>

        <p>
        🟢 Recovery:
        {r[1] if r[1] is not None else "-"}%
        </p>

        <p>
        ❤️ HRV:
        {round(float(r[2]),1) if r[2] is not None else "-"} ms
        </p>

        <p>
        ❤️ 静息心率:
        {r[3] if r[3] is not None else "-"} bpm
        </p>

        <p>
        😴 睡眠:
        {round(float(r[4]),1) if r[4] is not None else "-"} 小时
        </p>

        <p>
        ⭐ 睡眠评分:
        {r[5] if r[5] is not None else "-"}
        </p>

        <p>
        🔥 Strain:
        {round(float(r[6]),1) if r[6] is not None else "-"}
        </p>

        </div>

        """



        return f"""

<html>

<head>

<meta charset="UTF-8">

</head>


<body style="
background:#f5f7fa;
font-family:Arial;
padding:30px;
">


<h1>
📈 WHOOP 7天趋势
</h1>


{summary}
{cards}


</body>

</html>

"""

    except Exception as e:

        print(
            "TREND ERROR:",
            e
        )

        return str(e)


def format_weekly_report(report):

    if not report:
        return "暂无 AI 健康分析"

    sections = {
        "🟢【恢复趋势】": "ai-green",
        "❤️【HRV趋势】": "ai-heart",
        "😴【睡眠趋势】": "ai-sleep",
        "🔥【训练负荷】": "ai-fire",
        "⚠️【风险提醒】": "ai-warning",
        "📅【未来7天建议】": "ai-plan"
    }

    html_parts = []
    section_open = False

    # 删除 AI 返回内容中的空白行
    lines = [
        line.strip()
        for line in report.splitlines()
        if line.strip()
    ]

    for line in lines:

        matched_title = None

        for title in sections:
            if line.startswith(title):
                matched_title = title
                break

        if matched_title:

            if section_open:
                html_parts.append("</div>")

            css = sections[matched_title]

            html_parts.append(
                f"""
                <div class="ai-item">
                    <div class="ai-item-title {css}">
                        {matched_title}
                    </div>
                """
            )

            section_open = True

            # 保留标题后面可能存在的正文
            remaining_text = line[len(matched_title):].strip()

            if remaining_text:
                html_parts.append(
                    f'<div class="ai-item-content">{remaining_text}</div>'
                )

        else:

            if section_open:
                html_parts.append(
                    f'<div class="ai-item-content">{line}</div>'
                )
            else:
                html_parts.append(
                    f'<div class="ai-item-content">{line}</div>'
                )

    if section_open:
        html_parts.append("</div>")

    return "".join(html_parts)


@app.route("/api/whoop/today", methods=["GET"])
@require_chatgpt_api_key
def api_whoop_today():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                cycle_strain
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 1
            """
        )

        row = cur.fetchone()

        if not row:

            return jsonify({
                "success": False,
                "error": "No WHOOP data available"
            }), 404

        return jsonify({
            "success": True,
            "data": {
                "report_date": row[0],
                "recovery_score": row[1],
                "hrv_ms": row[2],
                "resting_heart_rate_bpm": row[3],
                "sleep_duration_hours": row[4],
                "sleep_score": row[5],
                "cycle_strain": row[6]
            }
        })

    except Exception as e:

        print(
            "WHOOP TODAY API ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "error": "Unable to retrieve WHOOP data"
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


@app.route("/api/whoop/weekly", methods=["GET"])
@require_chatgpt_api_key
def api_whoop_weekly():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                cycle_strain
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 7
            """
        )

        rows = cur.fetchall()
        rows = list(reversed(rows))

        records = []

        for row in rows:

            records.append({
                "report_date": row[0],
                "recovery_score": row[1],
                "hrv_ms": row[2],
                "resting_heart_rate_bpm": row[3],
                "sleep_duration_hours": row[4],
                "sleep_score": row[5],
                "cycle_strain": row[6]
            })

        sleep_valid_days = sum(
            1
            for record in records
            if record["sleep_duration_hours"] is not None
        )

        if records:
            start_date = records[0]["report_date"]
            end_date = records[-1]["report_date"]
        else:
            start_date = None
            end_date = None

        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "valid_days": len(records),
                "sleep_valid_days": sleep_valid_days,
                "expected_days": 7,
                "is_complete": len(records) >= 7
            },
            "records": records
        })

    except Exception as e:

        print(
            "WHOOP WEEKLY API ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "error": "Unable to retrieve weekly WHOOP data"
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


@app.route("/whoop/weekly")
def weekly():

    try:

        weekly_report = generate_weekly_analysis()

        print("WEEKLY REPORT RAW:")
        print(weekly_report)

        import re

        # 压缩AI输出中的多余空行
        weekly_report = re.sub(
            r'\n\s*\n+',
            '\n',
            weekly_report
        )

        weekly_report = format_weekly_report(weekly_report)

        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                sleep_duration,
                cycle_strain

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 7
            """
        )


        rows = cur.fetchall()


        cur.close()

        conn.close()


        rows = list(
            reversed(rows)
        )

        valid_days = len(rows)

        if valid_days < 7:
            score_period_text = f"{valid_days}天阶段性综合状态"
        else:
            score_period_text = "近7天综合状态"

        
        dates = [
            r[0]
            for r in rows
        ]
            

        sleep_valid_days = sum(
            1 for r in rows
            if r[3] is not None
        )

        if dates:
            report_period = f"{dates[0]} 至 {dates[-1]}"
        else:
            report_period = "暂无数据"
            

        recovery_values = [
            r[1]
            for r in rows
        ]


        hrv_values = [
            r[2]
            for r in rows
        ]


        sleep_values = [
            r[3]
            for r in rows
        ]


        strain_values = [
            r[4]
            for r in rows
        ]


        def safe_avg(values):

            valid_values = [
                float(v)
                for v in values
                if v is not None
            ]

            if not valid_values:
                return None

            return round(
                sum(valid_values) / len(valid_values),
                1
            )
    

        def recovery_status(value):

            if value is None:
                return "gray"

            if value >= 67:
                return "green"

            if value >= 34:
                return "orange"

            return "red"



        def sleep_status(value):

            if value is None:
                return "gray"

            if value >= 7:
                return "green"

            if value >= 6:
                return "orange"

            return "red"



        def strain_status(value):

            if value is None:
                return "gray"

            if value < 6:
                return "orange"

            if value <= 14:
                return "green"

            if value <= 18:
                return "orange"

            return "red"

        
        def hrv_status(value):

            if value is None:
                return "gray"

            if value >= 60:
                return "green"

            if value >= 40:
                return "orange"

            return "red"

    
        def recovery_label(value):

            if value is None:
                return "暂无数据"

            if value >= 67:
                return "恢复良好"

            if value >= 34:
                return "恢复一般"

            return "需要恢复"



        def sleep_label(value):

            if value is None:
                return "暂无数据"

            if value >= 7:
                return "睡眠充足"

            if value >= 6:
                return "略有不足"

            return "睡眠不足"



        def strain_label(value):

            if value is None:
                return "暂无数据"

            if value < 6:
                return "训练负荷较低"

            if value <= 14:
                return "中等训练负荷"

            if value <= 18:
                return "较高训练负荷"

            return "训练负荷过高"
    
    
        avg_recovery = safe_avg(
            recovery_values
        )


        avg_hrv = safe_avg(
            hrv_values
        )

        valid_hrv_values = [
            float(v)
            for v in hrv_values
            if v is not None
        ]

        hrv_color = "gray"
        hrv_text = "数据不足"

        if len(valid_hrv_values) >= 2:

            first_hrv = valid_hrv_values[0]
            latest_hrv = valid_hrv_values[-1]

            if first_hrv > 0:
                hrv_change = (
                    latest_hrv - first_hrv
                ) / first_hrv * 100

                if hrv_change >= 5:
                    hrv_color = "green"
                    hrv_text = "较期初上升"

                elif hrv_change <= -5:
                    hrv_color = "red"
                    hrv_text = "较期初下降"

                else:
                    hrv_color = "orange"
                    hrv_text = "整体稳定"
            

        avg_sleep = safe_avg(
            sleep_values
        )


        avg_strain = safe_avg(
            strain_values
        )

        
        # 综合健康评分

        health_score = 0


        # Recovery 权重40%
        if avg_recovery is not None:
            health_score += avg_recovery * 0.4


        # HRV 权重30%
        if avg_hrv is not None:
            health_score += min(avg_hrv,100) * 0.3


        # 睡眠权重20%
        if avg_sleep is not None:
            sleep_score = min(avg_sleep / 8 * 100, 100)
            health_score += sleep_score * 0.2


        # Strain权重10%
        if avg_strain is not None:
            strain_score = max(0,100-avg_strain*5)
            health_score += strain_score * 0.1


        health_score = round(health_score)


        recovery_color = recovery_status(
            avg_recovery
        )

        sleep_color = sleep_status(
            avg_sleep
        )

        strain_color = strain_status(
            avg_strain
        )


        recovery_text = recovery_label(
            avg_recovery
        )


        sleep_text = sleep_label(
            avg_sleep
        )


        strain_text = strain_label(
            avg_strain
        )

        

        dates_json = json.dumps(dates)

        recovery_json = json.dumps(recovery_values)

        hrv_json = json.dumps(hrv_values)

        sleep_json = json.dumps(sleep_values)

        strain_json = json.dumps(strain_values)


        return f"""

<!DOCTYPE html>

<html>

<head>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
WHOOP 7天健康趋势
</title>


<style>


.summary-grid {{

display:grid;

grid-template-columns:repeat(4,1fr);

gap:18px;

margin-bottom:30px;

}}



.summary-card {{

background:#fafafa;

border-radius:16px;

padding:20px;

text-align:center;

}}



.summary-label {{

font-size:16px;

margin-bottom:10px;

}}



.summary-value {{

font-size:28px;

font-weight:bold;

}}



.status-green {{
color:#16a34a;
}}


.status-orange {{
color:#f59e0b;
}}


.status-red {{
color:#dc2626;
}}


.status-gray {{
color:#666;
}}


.status-text {{

font-size:14px;

font-weight:bold;

margin-top:8px;

}}



body {{

background:#f5f7fa;

font-family:
-apple-system,
BlinkMacSystemFont,
"Segoe UI",
Arial;

padding:20px;

}}



.container {{

max-width:1100px;

margin:auto;

}}



.title {{

font-size:34px;

font-weight:700;

margin-bottom:25px;

}}



.card {{

background:white;

border-radius:20px;

padding:30px;

box-shadow:
0 8px 25px rgba(0,0,0,0.08);

margin-bottom:30px;

}}



.chart-box {{

height:350px;

margin-bottom:40px;

}}



h2 {{

margin-top:0;

font-size:22px;

}}


.section h2 {{

font-size:18px;

margin-bottom:8px;

}}


.section {{

margin-top:20px;

padding:20px;

border-radius:15px;

background:#fafafa;

height:auto;

min-height:0;


}}


.ai-box {{

background:#ffffff;

border-radius:18px;

padding:25px;

line-height:1.9;

font-size:17px;

}}


.ai-title {{

font-size:24px;

font-weight:bold;

margin-bottom:25px;

}}


.ai-item {{

background:#fafafa;

border-radius:16px;

padding:14px 18px;

margin-bottom:12px;

}}


.ai-item-title {{

font-size:28px;

font-weight:bold;

margin-bottom:4px;

color:#111;

}}


.ai-content {{

font-size:16px;

line-height:1.6;

}}


.ai-green {{

color:#16a34a;

}}

.ai-heart {{

color:#dc2626;

}}

.ai-sleep {{

color:#f59e0b;

}}

.ai-fire {{

color:#ea580c;

}}

.ai-warning {{

color:#dc2626;

}}

.ai-plan {{

color:#2563eb;

}}


.health-score-card {{

background:white;

border-radius:20px;

padding:25px;

margin-bottom:25px;

text-align:center;

box-shadow:
0 8px 25px rgba(0,0,0,0.08);

}}


.health-score-title {{

font-size:20px;

font-weight:700;

}}


.health-score-value {{

font-size:48px;

font-weight:bold;

color:#16a34a;

margin:15px 0;

}}


.health-score-text {{

font-size:16px;

color:#666;

}}

.data-coverage {{
    color:#666;
    font-size:15px;
    margin-top:-15px;
    margin-bottom:25px;
}}



* {{
    box-sizing: border-box;
}}

body {{
    overflow-x: hidden;
}}

.ai-content,
.ai-item,
.card {{
    overflow-wrap: anywhere;
    word-break: break-word;
}}


/* 平板和手机 */

@media (max-width: 768px) {{

    body {{
        padding: 12px;
    }}

    .container {{
        width: 100%;
        max-width: 100%;
    }}

    .title {{
        font-size: 26px;
        line-height: 1.3;
        margin-bottom: 18px;
    }}

    .health-score-card {{
        padding: 20px 15px;
        margin-bottom: 16px;
        border-radius: 16px;
    }}

    .health-score-title {{
        font-size: 18px;
    }}

    .health-score-value {{
        font-size: 44px;
        margin: 10px 0;
    }}

    .health-score-text {{
        font-size: 14px;
    }}

    .data-coverage {{
        font-size: 13px;
        line-height: 1.7;
        margin-top: 0;
        margin-bottom: 16px;
    }}

    .summary-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 20px;
    }}

    .summary-card {{
        padding: 15px 8px;
        border-radius: 14px;
    }}

    .summary-label {{
        font-size: 14px;
        margin-bottom: 8px;
    }}

    .summary-value {{
        font-size: 23px;
        white-space: nowrap;
    }}

    .status-text {{
        font-size: 12px;
        margin-top: 6px;
    }}

    .card {{
        padding: 16px 12px;
        border-radius: 16px;
        margin-bottom: 18px;
    }}

    .chart-box {{
        height: 260px;
        margin-bottom: 30px;
    }}

    h2 {{
        font-size: 19px;
        line-height: 1.4;
    }}

    .ai-box {{
        padding: 4px;
        font-size: 15px;
        line-height: 1.7;
    }}

    .ai-title {{
        font-size: 21px;
        margin-bottom: 16px;
    }}

    .ai-item {{
        padding: 14px;
        margin-bottom: 10px;
        border-radius: 14px;
    }}

    .ai-item-title {{
        font-size: 21px;
        line-height: 1.4;
        margin-bottom: 6px;
    }}

    .ai-item-content {{
        font-size: 15px;
        line-height: 1.7;
    }}
}}


/* 小屏手机 */

@media (max-width: 390px) {{

    body {{
        padding: 8px;
    }}

    .title {{
        font-size: 23px;
    }}

    .summary-grid {{
        gap: 8px;
    }}

    .summary-card {{
        padding: 13px 6px;
    }}

    .summary-label {{
        font-size: 13px;
    }}

    .summary-value {{
        font-size: 21px;
    }}

    .chart-box {{
        height: 230px;
    }}

    .ai-item-title {{
        font-size: 19px;
    }}

    .ai-item-content {{
        font-size: 14px;
    }}
}}

</style>


</head>



<body>


<div class="container">



<div class="title">

📊 WHOOP 7天健康趋势报告

</div>




<!-- SUMMARY -->

<div class="health-score-card">

<div class="health-score-title">

🧠 综合健康评分

</div>


<div class="health-score-value">

{health_score}

</div>


<div class="health-score-text">

{score_period_text}

</div>

</div>

<div class="data-coverage">
统计周期：{report_period}　
有效记录：{valid_days}/7天　
睡眠记录：{sleep_valid_days}/7天
</div>


<div class="summary-grid">


<div class="summary-card">

<div class="summary-label">

🟢 平均 Recovery

</div>


<div class="summary-value">

<span class="status-{recovery_color}">

{avg_recovery if avg_recovery is not None else "-"}

</span>

%

</div>


<div class="status-text">

{recovery_text}

</div>


</div>





<div class="summary-card">


<div class="summary-label">

❤️ 平均 HRV

</div>


<div class="summary-value">


<span class="status-{hrv_color}">

{avg_hrv if avg_hrv is not None else "-"}

</span>

ms


</div>


<div class="status-text">

{hrv_text}

</div>


</div>






<div class="summary-card">


<div class="summary-label">

😴 平均睡眠

</div>


<div class="summary-value">


<span class="status-{sleep_color}">

{avg_sleep if avg_sleep is not None else "-"}

</span>

h


</div>


<div class="status-text">

{sleep_text}

</div>


</div>







<div class="summary-card">


<div class="summary-label">

🔥 平均 Strain

</div>


<div class="summary-value">


<span class="status-{strain_color}">

{avg_strain if avg_strain is not None else "-"}

</span>


</div>


<div class="status-text">

{strain_text}

</div>


</div>



</div>





<!-- CHARTS -->


<div class="card">


<h2>
📈 Recovery趋势
</h2>


<div class="chart-box">

<canvas id="recoveryChart"></canvas>

</div>





<h2>
❤️ HRV趋势
</h2>


<div class="chart-box">

<canvas id="hrvChart"></canvas>

</div>






<h2>
😴 睡眠趋势
</h2>


<div class="chart-box">

<canvas id="sleepChart"></canvas>

</div>






<h2>
🔥 Strain趋势
</h2>


<div class="chart-box">

<canvas id="strainChart"></canvas>

</div>




</div>






<!-- AI REPORT -->


<div class="card">


<div class="ai-box">


<div class="ai-title">

🤖 AI健康教练建议

</div>


<div class="ai-content">

{weekly_report}

</div>

</div>

</div>

<script>


new Chart(
document.getElementById("recoveryChart"),
{{

type:"line",

data:{{

labels:{dates_json},

datasets:[{{

label:"Recovery",

data:{recovery_json}

}}]

}},


options:{{

responsive:true,

maintainAspectRatio:false

}}


}}

);





new Chart(
document.getElementById("hrvChart"),
{{

type:"line",

data:{{

labels:{dates_json},

datasets:[{{

label:"HRV",

data:{hrv_json}

}}]

}},


options:{{

responsive:true,

maintainAspectRatio:false

}}


}}

);






new Chart(
document.getElementById("sleepChart"),
{{

type:"bar",

data:{{

labels:{dates_json},

datasets:[{{

label:"Sleep Hours",

data:{sleep_json}

}}]

}},


options:{{

responsive:true,

maintainAspectRatio:false

}}


}}

);






new Chart(
document.getElementById("strainChart"),
{{

type:"bar",

data:{{

labels:{dates_json},

datasets:[{{

label:"Strain",

data:{strain_json}

}}]

}},


options:{{

responsive:true,

maintainAspectRatio:false

}}


}}

);



</script>



</body>

</html>

"""


    except Exception as e:


        print(
            "WEEKLY PAGE ERROR:",
            e
        )


        return str(e)



def generate_ai_summary(ai_prompt):

    try:

        response = client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                    "role":"system",
                    "content":
                    """
                    
输出格式要求：

你是一名 WHOOP 风格私人健康教练。

不要输出总标题，直接开始今日分析。

请严格按照以下结构输出：

【🟡 今日教练总结】

用1-2句话总结今天身体状态。
告诉用户今天最重要的一件事。


【🧠 今日身体状态】

总结今天身体恢复情况。
结合近期趋势分析，不要只重复数据。


【❤️ 恢复分析】

分析：
Recovery
HRV
静息心率

解释身体可能出现的信号。


【😴 睡眠分析】

分析：
睡眠时间
睡眠效率
深睡
REM

说明睡眠对恢复的影响，并给出改善建议。


【🏋️ 今日训练建议】

必须明确：

✅ 推荐：
今天适合做什么训练。

❌ 避免：
今天不建议做什么训练。


📈 明日恢复预测

根据今天状态预测未来趋势。

说明：
如果今晚恢复良好，明天可能如何变化。


回答规则：

1. 使用中文简体。
2. 使用emoji作为章节标识。
3. 不使用Markdown符号。
4. 不使用 **。
5. 不使用 ---。
6. 不输出代码。
7. 不重复罗列大量数据。
8. 重点解释身体信号。
9. 给明确可执行建议。
10. 使用第二人称“你”。
11. 每个章节控制3-5句话。
12. 语言像私人WHOOP Coach，而不是医学报告。
13. 总长度控制在500字以内。
"""
},

            {
                "role": "user",
                "content": ai_prompt[:3000]
            }

        ],

        temperature=0.4,

        max_tokens=600

    )


        return response.choices[0].message.content


    except Exception as e:

        print(
            "AI SUMMARY ERROR:",
            e
        )

        return "⚠️ AI教练暂时无法生成建议"



def generate_weekly_ai_summary(ai_prompt):

    try:

        response = client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                    "role": "system",
                    "content": """
你是 WHOOP 私人健康教练。

你的任务：
根据用户最近最多7天的 WHOOP 数据，
生成专业、谨慎、简洁、可执行的趋势分析。

必须严格使用以下标题，标题文字和emoji不能改变：

🟢【恢复趋势】

❤️【HRV趋势】

😴【睡眠趋势】

🔥【训练负荷】

⚠️【风险提醒】

📅【未来7天建议】

分析规则：

1. 只能使用用户提供的数据，不得编造或猜测。
2. 数据缺失时，必须明确写“数据缺失，无法判断”。
3. 不得把没有训练记录解释为休息日或高强度训练。
4. 不得根据单日变化作出确定性医学结论。
5. 数据不足7天时，必须说明这是阶段性趋势。
6. 必须区分短期波动和连续下降趋势。
7. 不重复堆砌所有原始数据，只引用支持结论的关键数值。
8. 睡眠建议必须结合睡眠时长和睡眠评分。
9. 训练建议必须结合 Recovery、HRV、睡眠和 Strain。
10. 未来7天建议必须是条件式建议，不得预先安排固定的HIIT或高强度训练。

训练建议标准：

- Recovery较低或睡眠不足6小时：
  建议休息或主动恢复。

- Recovery处于中等水平：
  建议低至中等强度训练。

- Recovery较高、HRV稳定且睡眠充足：
  才可以建议中高强度训练。

风险表达规则：

- 使用“可能”“建议关注”等谨慎表达。
- 不得诊断疾病。
- 不得声称一定会受伤或生病。
- 如出现持续异常，建议咨询医疗专业人员。

输出要求：

- 中文简体
- 使用emoji
- 500字以内
- 不输出代码
- 不使用Markdown表格
- 像谨慎、专业的WHOOP私人教练
"""
                },

                {
                    "role": "user",
                    "content": ai_prompt[:5000]
                }

            ],

            temperature=0.3,

            max_tokens=900

        )

        return response.choices[0].message.content

    except Exception as e:

        print(
            "WEEKLY AI SUMMARY ERROR:",
            e
        )

        return "⚠️ 周报 AI 教练暂时无法生成建议"

def generate_weekly_analysis():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                sleep_duration,
                sleep_score,
                cycle_strain
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 7
            """
        )

        rows = cur.fetchall()

        print("WEEKLY DATA:", rows)

        if len(rows) < 3:
            return "历史数据不足3天，暂无法生成可靠趋势分析"

        # 数据库查询为倒序，这里转换成日期正序
        rows = list(reversed(rows))

        def show_value(value, suffix=""):

            if value is None or value == "":
                return "数据缺失"

            return f"{value}{suffix}"

        data_lines = []

        for row in rows:

            (
                report_date,
                recovery_score,
                hrv,
                sleep_duration,
                sleep_score,
                cycle_strain
            ) = row

            data_lines.append(
                f"""
日期：{report_date}
Recovery：{show_value(recovery_score, "%")}
HRV：{show_value(hrv, " ms")}
睡眠时长：{show_value(sleep_duration, " 小时")}
睡眠评分：{show_value(sleep_score, " 分")}
Strain：{show_value(cycle_strain)}
""".strip()
            )

        valid_days = len(rows)
        start_date = rows[0][0]
        end_date = rows[-1][0]

        weekly_data_text = "\n\n".join(data_lines)

        prompt = f"""
统计周期：{start_date} 至 {end_date}
有效记录：{valid_days}/7天

以下是按日期排列的 WHOOP 数据：

{weekly_data_text}

请严格按照指定的六个标题生成周报。

特别要求：

- 当前只有{valid_days}天记录。
- 如果不足7天，说明当前结论属于阶段性趋势。
- 不得对缺失日期和缺失指标进行推测。
- 不得把“无训练数据”解释为休息或高强度训练。
- 重点分析Recovery、HRV、睡眠和Strain之间的关系。
- 未来7天采用条件式建议，根据每日Recovery和睡眠决定强度。
"""

        result = generate_weekly_ai_summary(prompt)

        return result

    except Exception as e:

        print(
            "WEEKLY ANALYSIS ERROR:",
            e
        )

        return "⚠️ 周报告暂时无法生成"

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


def privacy():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Privacy Policy</title>
        <meta charset="utf-8">
    </head>

    <body>
        <h1>Privacy Policy</h1>

        <p>
        WHOOP Health Coach accesses WHOOP data only to provide
        personal health analysis and training recommendations.
        </p >

        <p>
        The app does not sell, share, or publicly distribute user data.
        </p >

        <p>
        Users can revoke WHOOP authorization at any time.
        </p >

    </body>
    </html>
    """

def check_api_key():

    key = request.headers.get(
        "X-API-Key"
    )


    api_secret = os.getenv(
        "API_SECRET"
    )


    return key == api_secret
    

def whoop_token():


    code = request.args.get(
        "code"
    )


    if not code:

        return jsonify(
            {
                "error":
                "missing code"
            }
        ),400



    r = requests.post(


        WHOOP_TOKEN_URL,


        data={

            "grant_type":"authorization_code",

            "code":code,
        
            "client_id":WHOOP_CLIENT_ID,

            "client_secret":WHOOP_CLIENT_SECRET,

            },

        headers={


            "Content-Type":
            "application/x-www-form-urlencoded"

        },


        timeout=30

    )



    print(
        "TOKEN RESPONSE:"
    )


    print(
        r.text
    )


    token_data = r.json()
    
    new_refresh_token = token_data.get("refresh_token")

    if new_refresh_token:
        save_refresh_token(new_refresh_token)
        print("REFRESH TOKEN SAVED TO DATABASE")
    else:
        print("NO REFRESH TOKEN RETURNED")
        

    return jsonify(token_data)



def extract_daily_metrics(data):

    print(
        "FUNCTION INPUT CYCLE:",
        data.get("cycle")
    )

    result = {}


    # =========================
    # Recovery
    # =========================

    try:

        recovery_data = data.get("recovery", [])

        if isinstance(recovery_data, dict):

            recovery_records = recovery_data.get(
                "records",
                []
            )

        else:

            recovery_records = recovery_data


        recovery = (
            recovery_records[0]
            if recovery_records
            else {}
        )


        recovery_score_data = recovery.get(
            "score",
            {}
        )


        result["recovery_score"] = recovery_score_data.get(
            "recovery_score"
        )


        result["hrv"] = recovery_score_data.get(
            "hrv_rmssd_milli"
        )


        result["resting_heart_rate"] = recovery_score_data.get(
            "resting_heart_rate"
        )


        print(
            "RECOVERY PARSED:",
            result["recovery_score"],
            result["hrv"],
            result["resting_heart_rate"]
        )


    except Exception as e:

        print(
            "RECOVERY ERROR:",
            e
        )

        result["recovery_score"] = None
        result["hrv"] = None
        result["resting_heart_rate"] = None


    # =====================
    # Sleep
    # =====================

    try:

        sleep_data = data.get(
            "sleep",
            {}
        )

        if not sleep_data and "score" in data:
            sleep_data = data

        if isinstance(sleep_data, dict):

            sleep_records = sleep_data.get(
                "records",
                []
            )

            if not sleep_records and sleep_data.get("score"):
                sleep_records = [sleep_data]

        
        else:

            sleep_records = sleep_data

        # 优先选择非小睡且已评分的睡眠
        main_sleep = None

        for record in sleep_records:

            if (
                not record.get("nap", False)
                and record.get("score_state") == "SCORED"
            ):

                main_sleep = record
                break

        if main_sleep is None:

            main_sleep = (
                sleep_records[0]
                if sleep_records
                else {}
            )

        sleep_score_data = (
            main_sleep.get("score") or {}
        )

        stage = (
            sleep_score_data
            .get("stage_summary") or {}
        )


        result["sleep_score"] = (
            sleep_score_data.get(
                "sleep_performance_percentage"
            )
        )


        # 实际睡眠时间：
        # 浅睡 + 深睡 + REM
        light_sleep = (
            stage.get(
                "total_light_sleep_time_milli"
            ) or 0
        )

        deep_sleep = (
            stage.get(
                "total_slow_wave_sleep_time_milli"
            ) or 0
        )

        rem_sleep = (
            stage.get(
                "total_rem_sleep_time_milli"
            ) or 0
        )

        total_sleep = (
            light_sleep
            + deep_sleep
            + rem_sleep
        )


        result["sleep_duration"] = (
            round(
                total_sleep / 3600000,
                2
            )
            if total_sleep
            else None
        )


        result["sleep_efficiency"] = (
            sleep_score_data.get(
                "sleep_efficiency_percentage"
            )
        )


        result["deep_sleep_duration"] = (
            round(
                deep_sleep / 3600000,
                2
            )
            if deep_sleep
            else None
        )


        result["rem_sleep_duration"] = (
            round(
                rem_sleep / 3600000,
                2
            )
            if rem_sleep
            else None
        )


    except Exception as e:

        print(
            "SLEEP PARSE ERROR:",
            e
        )

        result["sleep_score"] = None
        result["sleep_duration"] = None
        result["sleep_efficiency"] = None
        result["deep_sleep_duration"] = None
        result["rem_sleep_duration"] = None


    # =====================
    # Cycle
    # =====================

    strain = None


    try:

        cycle_data = data.get(
            "cycle",
            {}
        )


        cycle_records = cycle_data.get(
            "records",
            []
        )


        print(
            "CYCLE RECORD COUNT:",
            len(cycle_records)
        )


        for cycle in cycle_records:

            score = cycle.get(
                "score",
                {}
            )


            if score.get("strain") is not None:

                strain = score.get(
                    "strain"
                )

                break


    except Exception as e:

        print(
            "CYCLE PARSE ERROR:",
            e
        )


    print(
        "FINAL CYCLE STRAIN:",
        strain
    )

    result["cycle_strain"] = strain
    
    # =========================
    # Workout
    # =========================

    try:

        workout_data = data.get(
            "workout",
            {}
        )


        if isinstance(workout_data, dict):

            result["workout_data"] = (
                workout_data.get(
                    "records",
                    workout_data
                )
            )

        else:

            result["workout_data"] = workout_data


    except Exception as e:

        print(
            "WORKOUT ERROR:",
            e
        )

        result["workout_data"] = {}

    print(
        "FINAL EXTRACT METRICS:",
        result
    )

    return result

def save_daily_data(metrics):

    conn = None
    cur = None

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        today = (
            datetime.utcnow()
            + timedelta(hours=8)
        ).strftime("%Y-%m-%d")


        cur.execute(
            """
            INSERT INTO daily_metrics
            (
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_score,
                sleep_duration,
                sleep_efficiency,
                deep_sleep_duration,
                rem_sleep_duration,
                cycle_strain,
                workout_data,
                health_score
            )
            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
           ON CONFLICT (report_date)

           DO UPDATE SET

           recovery_score = EXCLUDED.recovery_score,

           hrv = EXCLUDED.hrv,

           resting_heart_rate = EXCLUDED.resting_heart_rate,

           sleep_score = EXCLUDED.sleep_score,

           sleep_duration = EXCLUDED.sleep_duration,

           sleep_efficiency = EXCLUDED.sleep_efficiency,

           deep_sleep_duration = EXCLUDED.deep_sleep_duration,

           rem_sleep_duration = EXCLUDED.rem_sleep_duration,

           cycle_strain = EXCLUDED.cycle_strain,

           workout_data = EXCLUDED.workout_data,

           health_score = EXCLUDED.health_score

           """,
            (
                today,
                metrics.get("recovery_score",0),
                metrics.get("hrv",0),
                metrics.get("resting_heart_rate",0),
                metrics.get("sleep_score",0),
                metrics.get("sleep_duration",0),
                metrics.get("sleep_efficiency",0),
                metrics.get("deep_sleep_duration",0),
                metrics.get("rem_sleep_duration",0),
                metrics.get("cycle_strain",0),
                str(metrics.get("workout_data","")),
                metrics.get("health_score",0)
            )
            )


        conn.commit()


        print("AUTO DAILY SAVE OK")

        print("BEFORE SELECT TEST")

        print("SAVED METRICS:", metrics)

        cur.execute(
            """
            SELECT *
            FROM daily_metrics
            ORDER BY id DESC
            LIMIT 1
            """
        )

        latest_row = cur.fetchone()

        
        print(
            "LATEST DAILY ROW:",
            latest_row
        )

    except Exception as e:

        print(
            "SAVE DAILY DATA ERROR:",
            e
        )


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


def convert_utc_to_beijing(obj):

    if isinstance(obj, dict):

        for key, value in obj.items():

            if isinstance(value, (dict, list)):

                convert_utc_to_beijing(value)


            elif isinstance(value, str):

                if value.endswith("Z"):

                    try:

                        dt = datetime.fromisoformat(
                            value.replace(
                                "Z",
                                "+00:00"
                            )
                        )


                        bj_time = dt.astimezone(
                            timezone(
                                timedelta(hours=8)
                            )
                        )


                        obj[key] = bj_time.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )


                    except Exception:

                        pass


    elif isinstance(obj, list):

        for item in obj:

            convert_utc_to_beijing(item)

def generate_coach_advice(
    recovery_score,
    hrv,
    sleep_duration,
    sleep_debt,
    cycle_strain
):

    recovery_score = float(recovery_score)
    hrv = float(hrv)
    sleep_duration = float(sleep_duration)
    sleep_debt = float(sleep_debt)
    strain = float(strain)
    

    # ======================
    # Recovery 判断
    # ======================

    recovery = recovery_score

    if recovery >= 70:

        status = "🟢 状态良好"

        training = (
            "今天身体恢复状态优秀，可以进行正常训练。\n"
            "推荐：力量训练 + Zone2有氧。\n"
            "目标 Strain：8-12"
        )


    elif recovery >= 40:

        status = "🟡 状态一般"

        training = (
            "今天恢复一般，建议控制训练量。\n"
            "推荐：中低强度训练或技术训练。\n"
            "目标 Strain：5-8"
        )


    else:

        status = "🔴 恢复不足"

        training = (
            "今天恢复不足，优先恢复。\n"
            "推荐：散步、拉伸、低强度活动。\n"
            "目标 Strain：<5"
        )


    # ======================
    # 睡眠判断
    # ======================

    if sleep_debt >= 6:

        sleep_warning = (
            "⚠️ 睡眠债较高，需要优先补觉。"
        )

    elif sleep_debt >= 3:

        sleep_warning = (
            "🟡 存在轻中度睡眠债，建议今晚提前睡。"
        )

    else:

        sleep_warning = (
            "🟢 睡眠恢复正常。"
        )


    # ======================
    # HRV判断
    # ======================

    if hrv < 30:

        hrv_status = (
            "HRV偏低，注意压力和恢复。"
        )

    else:

        hrv_status = (
            "HRV状态稳定。"
        )


    # ======================
    # Strain风险
    # ======================

    if strain >= 15:

        strain_warning = (
            "⚠️ 今日负荷较高，避免连续高强度。"
        )

    else:

        strain_warning = (
            "🟢 当前训练负荷合理。"
        )

    advice = {}
    
    advice["status"] = status

    advice["training"] = training

    advice["sleep"] = sleep_warning

    advice["hrv"] = hrv_status

    advice["strain"] = strain_warning


    return advice
    

def get_health_level(score):

    if score >= 85:
        return "🟢 优秀状态"

    elif score >= 70:
        return "🟡 良好状态"

    elif score >= 50:
        return "🟠 一般状态"

    else:
        return "🔴 需要恢复"


def get_strain_level(strain):

    if strain < 10:
        return "🟢 低负荷"

    elif strain < 15:
        return "🟡 中等负荷"

    else:
        return "🔴 高负荷"
        

def generate_health_report(data):

    print("REPORT INPUT DATA:")
    print(data)

    recovery_raw = data.get("recovery", {})
    sleep_raw = data.get("sleep", {})

    print(
        "SLEEP TYPE:",
        type(sleep_raw)
    )

    print(
        "SLEEP RAW DEBUG:",
        sleep_raw
    )

    
    workout_raw = data.get("workout", {})


    # ======================
    # Recovery Parser
    # ======================

    if isinstance(recovery_raw, dict):

        recovery = (
            recovery_raw.get("records", [{}])[0]
        )

    else:

        recovery = {}

    
    # ======================
    # WHOOP API 返回 records
    # ======================
    
    if isinstance(sleep_raw, dict):

        if "score" in sleep_raw:

            sleep = sleep_raw

        else:

            sleep = (
                sleep_raw.get("records", [{}])[0]
            )

    else:

        sleep = {}
    

    if isinstance(workout_raw, dict):

        workout = (
            workout_raw.get("records", [{}])[0]
        )

    else:

        workout = {}


    score = recovery.get("score", {})


    recovery_score = float(
        score.get("recovery_score",0)
        or 0
    )

    hrv = float(
        score.get("hrv_rmssd_milli",0)
        or 0
    )

    resting_hr = float(
        score.get("resting_heart_rate",0)
        or 0
    )


    # =========================
    # WHOOP Sleep Parser V2
    # =========================

    sleep_duration = 0
    sleep_performance = 0
    sleep_efficiency = 0
    sleep_quality = "Unknown"
    sleep_cycles = 0
    sleep_needed = 0
    awake_time = 0


    try:

        print("RAW SLEEP RESPONSE:")
        print(sleep)


        latest_sleep = sleep
    

        print(
            "LATEST SLEEP TYPE:",
            type(latest_sleep)
        )

        print(
            "LATEST SLEEP:",
            latest_sleep
        )



        # =========================
        # SCORE
        # =========================

        sleep_score_data = latest_sleep.get(
            "score",
            {}
        )


        if not isinstance(
            sleep_score_data,
            dict
        ):
            print(
                "INVALID SLEEP SCORE:",
                sleep_score_data
            )

            sleep_score_data = {}


        # =========================
        # STAGE
        # =========================

        stage = sleep_score_data.get(
            "stage_summary",
            {}
        )


        if not isinstance(
            stage,
            dict
        ):
            print(
                "INVALID STAGE DATA TYPE:",
                type(stage)
            )

            stage = {}


        deep_sleep_duration = round(
            (
                stage.get(
                    "total_slow_wave_sleep_time_milli",
                    0
                )
            ) / 3600000,
            2
        )


        rem_sleep_duration = round(
            (
                stage.get(
                    "total_rem_sleep_time_milli",
                    0
                )
            ) / 3600000,
            2
        )


        sleep_duration = round(
            (
                stage.get(
                    "total_light_sleep_time_milli",
                    0
                )
                +
                stage.get(
                    "total_slow_wave_sleep_time_milli",
                    0
                )
                +
                stage.get(
                    "total_rem_sleep_time_milli",
                    0
                )
            )
            / 3600000,
            2
        )


        sleep_performance = sleep_score_data.get(
            "sleep_performance_percentage",
            0
        )


        sleep_efficiency = sleep_score_data.get(
            "sleep_efficiency_percentage",
            0
        )


        sleep_cycles = stage.get(
            "sleep_cycle_count",
            0
        )


        sleep_needed = round(
            score.get(
                "sleep_needed",
                {}
            ).get(
                "baseline_milli",
                0
            ) / 3600000,
            2
        )


        awake_time = round(
            stage.get(
                "total_awake_time_milli",
                0
            ) / 60000,
            1
        )


        if sleep_performance >= 85:
            sleep_quality = "Excellent"

        elif sleep_performance >= 70:
            sleep_quality = "Good"

        elif sleep_performance >= 50:
            sleep_quality = "Fair"

        else:
            sleep_quality = "Poor"


    except Exception as e:

        print(
            "SLEEP PARSER ERROR:",
            e
        )


    # =========================
    # WHOOP Strain Parser
    # =========================

    strain = 0.0


    try:

        cycle_raw = data.get(
            "cycle",
            {}
        )


        if isinstance(cycle_raw, dict):

            cycle_record = (
                cycle_raw.get(
                    "records",
                    [{}]
                )[0]
            )


            cycle_score = cycle_record.get(
                "score",
                {}
            )


            strain = float(
                cycle_score.get(
                    "strain",
                    0
                )
                or 0
            )



        # 如果cycle没有strain，备用读取workout

        if strain == 0 and isinstance(workout, dict):

            workout_score = workout.get(
                "score",
                {}
            )


            strain = float(
                workout_score.get(
                    "strain",
                    0
                )
                or 0
            )


    except Exception as e:

        print(
            "STRAIN PARSER ERROR:",
            e
        )

        strain = 0.0


    # =========================
    # 训练信息
    # =========================

    training_advice = "根据 Recovery 调整训练强度"

    print(
        "Recovery:",
        recovery_score,
        "HRV:",
        hrv,
        "Rest HR:",
        resting_hr,
        "Sleep:",
        sleep_duration
    )


    print(
        "SLEEP FINAL CHECK:",
        sleep_duration,
        sleep_performance,
        sleep_efficiency,
        deep_sleep_duration,
        rem_sleep_duration
    )

    
    return {

        "recovery_score": recovery_score,

        "hrv": hrv,

        "resting_heart_rate": resting_hr,

        "sleep_duration": sleep_duration,

        "sleep_score": sleep_performance,

        "sleep_efficiency": sleep_efficiency,

        "deep_sleep_duration": deep_sleep_duration,

        "rem_sleep_duration": rem_sleep_duration,

        "cycle_strain": strain,

        "sleep_quality": sleep_quality,

        "sleep_cycles": sleep_cycles,

        "sleep_needed": sleep_needed,

        "awake_minutes": awake_time,

        "training_advice": training_advice

    }


def get_whoop_data():

    try:

        recovery = whoop_get("/recovery")

        sleep = whoop_get("/activity/sleep")

        cycle = whoop_get("/cycle")

        workout = whoop_get("/activity/workout")


        print("API RECOVERY:")
        print(recovery)


        print("API SLEEP:")
        print(sleep)


        print("API CYCLE:")
        print(cycle)


        print("API WORKOUT:")
        print(workout)


        return {
            "recovery": recovery,
            "sleep": sleep,
            "cycle": cycle,
            "workout": workout
        }


    except Exception as e:

        print(
            "GET WHOOP DATA ERROR:",
            e
        )

        return {}


def today():

    try:

        data = get_whoop_data()

        report = generate_health_report(data)

        return report


    except Exception as e:

        print("TODAY ERROR:", e)

        return str(e)

def get_whoop_week_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            report_date,
            recovery_score,
            hrv,
            resting_heart_rate,
            sleep_score,
            sleep_duration,
            sleep_efficiency,
            cycle_strain
        FROM daily_metrics
        ORDER BY id DESC
        LIMIT 7
    """)

    rows = cursor.fetchall()


    print("WEEK ROW COUNT:", len(rows))
    print("WEEK ROWS:", rows)

    cursor.close()
    conn.close()

    return rows

def predict_recovery(
    recovery_list,
    hrv_list,
    hr_list,
    sleep_debt
):


    score = 0


    # Recovery趋势

    if len(recovery_list)>=2:

        if recovery_list[0] < recovery_list[-1]:
            score += 1
        else:
            score -=1



    # HRV

    if len(hrv_list)>=2:

        if hrv_list[0] < hrv_list[-1]:
            score +=1
        else:
            score-=1



    # 静息心率

    if len(hr_list)>=2:

        if hr_list[0] <= hr_list[-1]:
            score +=1
        else:
            score-=1



    # 睡眠债

    if sleep_debt < 2:

        score+=1

    else:

        score-=1



    if score>=2:

        return "📈 明日 Recovery 预计提升，身体状态改善"

    elif score<=-2:

        return "📉 明日 Recovery 可能下降，需要增加恢复"

    else:

        return "➡️ 明日 Recovery 预计保持稳定"

def generate_training_plan(
    recovery,
    strain
):

    if recovery >= 67:

        return '''
今日适合训练

推荐：
- 力量训练45-60分钟
- Zone2有氧40分钟

建议目标 Strain:
8-12
'''


    elif recovery >= 34:

        return '''
中等恢复状态

推荐：
- Zone2轻松有氧
- 技术训练
- 拉伸恢复

建议目标 Strain:
5-8
'''


    else:

        return '''
恢复不足

建议：
- 休息
- 散步
- 拉伸


避免：
- HIIT
- 大重量训练
'''

def generate_week_report(data):

    if not data:
        return "暂无7天数据"


    recovery_list = []
    hrv_list = []
    hr_list = []
    sleep_list = []
    strain_list = []

    daily_html = ""


    for row in data:

        date = row[0]

        recovery = row[1] or 0

        hrv = row[2] or 0

        resting_hr = row[3] or 0

        sleep = row[5] or 0

        strain = row[7] or 0


        recovery_list.append(float(recovery))
        hrv_list.append(float(hrv))
        hr_list.append(float(resting_hr))
        sleep_list.append(float(sleep))
        strain_list.append(float(strain))


        daily_html += f"""

        <hr>

        <h3>📅 {date}</h3>

        💚 Recovery:
        {recovery:.1f}%<br>

        ❤️ HRV:
        {hrv:.1f} ms<br>

        ❤️‍🔥 静息心率:
        {resting_hr:.1f} bpm<br>

        😴 睡眠:
        {sleep:.2f} 小时<br>

        🔥 Strain:
        {strain:.2f}

        """



    days = len(data)


    avg_recovery = (
        sum(recovery_list)
        /
        days
    )

    avg_hrv = (
        sum(hrv_list)
        /
        days
    )

    avg_hr = (
        sum(hr_list)
        /
        days
    )

    avg_sleep = (
        sum(sleep_list)
        /
        days
    )

    avg_strain = (
        sum(strain_list)
        /
        days
    )


    latest_recovery = recovery_list[-1]


    recovery_change = (
        latest_recovery
        -
        avg_recovery
    )


    ai_prompt = f"""

你是我的 WHOOP 私人健康教练。


请根据最近7天WHOOP数据生成健康分析。


📊 数据：

7天平均 Recovery:
{avg_recovery:.1f}%


最近一次 Recovery:
{latest_recovery:.1f}%


Recovery趋势变化:
{recovery_change:+.1f}%


平均 HRV:
{avg_hrv:.1f} ms


平均静息心率:
{avg_hr:.1f} bpm


平均睡眠:
{avg_sleep:.2f} 小时


平均 Strain:
{avg_strain:.2f}



请严格按照格式输出：



🟢 【总体状态】

判断：

🟢 良好

🟡 需要注意

🔴 风险


用2句话总结。



💚 【Recovery恢复分析】

分析：

- Recovery水平
- 最近趋势
- HRV状态
- 心率恢复情况



😴 【睡眠分析】

分析：

- 睡眠是否支持训练
- 是否存在恢复不足风险
- 给出睡眠目标



🔥 【训练建议】

根据：

Recovery

HRV

Strain


给出：

🏋️ 是否适合训练

训练类型

建议强度



⚠️ 【未来3天行动计划】


第1天：

训练建议


第2天：

恢复建议


第3天：

训练调整建议



要求：

- 中文简体
- 不超过400字
- 像私人健康教练
- 不解释WHOOP概念
- 不输出代码


"""


    coach_advice = generate_ai_summary(
        ai_prompt
    )


    return f"""

<div>

{daily_html}

<hr>

<h2>🧠 WHOOP健康教练7天分析</h2>

{coach_advice}

</div>

"""

    # =========================
    # 趋势分析
    # =========================

    if len(recovery_list) >= 2:

        if recovery_list[0] > recovery_list[-1]:
            recovery_trend = "📈 Recovery 正在提升"

        elif recovery_list[0] < recovery_list[-1]:
            recovery_trend = "📉 Recovery 有下降趋势"

        else:
            recovery_trend = "➡️ Recovery 保持稳定"

    else:
        recovery_trend = "数据不足"


    if len(hrv_list) >= 2:

        if hrv_list[0] > hrv_list[-1]:
            hrv_trend = "📈 HRV 上升，恢复能力改善"

        elif hrv_list[0] < hrv_list[-1]:
            hrv_trend = "📉 HRV 下降，需要关注恢复"

        else:
            hrv_trend = "➡️ HRV 稳定"

    else:
        hrv_trend = "数据不足"


    # ======================
    # Recovery趋势
    # ======================

    if len(recovery_list) >= 2:

        recovery_change = (
            recovery_list[-1]
            -
            recovery_list[0]
        )

    else:

        recovery_change = 0



    if recovery_change > 5:

        recovery_trend = "📈 Recovery提升，身体状态改善"

    elif recovery_change < -5:

        recovery_trend = "📉 Recovery下降，需要增加恢复"

    else:

        recovery_trend = "➡️ Recovery保持稳定"



    # ======================
    # HRV趋势
    # ======================

    if len(hrv_list) >= 2:

        hrv_change = (
            hrv_list[-1]
            -
            hrv_list[0]
        )

    else:

        hrv_change = 0



    if hrv_change > 5:

        hrv_comment = "✅ HRV提升，恢复能力增强"

    elif hrv_change < -5:

        hrv_comment = "⚠️ HRV下降，注意疲劳"

    else:

        hrv_comment = "HRV稳定"



    # ======================
    # 睡眠债
    # ======================

    sleep_debt = 0


    for s in sleep_list:

        if s < 8:

            sleep_debt += (8 - s)



    if sleep_debt >= 5:

        sleep_comment = "⚠️ 累积睡眠债较高，建议增加睡眠"

    elif sleep_debt > 0:

        sleep_comment = "轻微睡眠不足"

    else:

        sleep_comment = "睡眠充足"



    # ======================
    # Strain风险
    # ======================

    high_strain_days = 0


    for s in strain_list:

        if s >= 14:

            high_strain_days += 1



    if high_strain_days >= 3:

        strain_comment = " 多天高 Strain，存在过劳风险"

    elif high_strain_days > 0:

        strain_comment = " 有高负荷训练，需要匹配恢复"

    else:

        strain_comment = " 当前训练负荷合理"



    # ======================
    # 状态判断
    # ======================

    if avg_recovery >= 70:

        status = " 良好"

    elif avg_recovery >= 40:

        status = " 需小心"

    else:

        status = " 危险"



    # ======================
    # 自动训练建议
    # ======================

    if avg_recovery >= 67:

        training_plan = '''
        可以正常训练

        推荐：
        - 力量训练
        - Zone2有氧

        目标 Strain:
        8-12
        '''

    elif avg_recovery >= 34:

        training_plan = '''
        建议降低训练量

        推荐：
        - 轻松有氧
        - 技术训练
        - 拉伸恢复

        目标 Strain:
        5-8
        '''

    else:

        training_plan = '''
        建议恢复

        避免：
        - HIIT
        - 高强度力量

        优先睡眠和恢复
        '''

    ai_summary = f'''
    {coach_advice}


    训练建议：
    {training_plan}
    '''


    return f"""

<h1>
WHOOP 最近7天私人健康报告
</h1>


<h2>
整体状态：
{status}
</h2>

<h2>每日记录</h2>

{daily_html}


<h2>平均指标</h2>

Recovery:
<b>{avg_recovery:.1f}%</b><br>

HRV:
<b>{avg_hrv:.1f} ms</b><br>

静息心率:
<b>{avg_hr:.1f} bpm</b><br>

睡眠:
<b>{avg_sleep:.2f} 小时</b><br>

Strain:
<b>{avg_strain:.2f}</b>



<h2>睡眠债分析</h2>

累计睡眠债:
<b>{sleep_debt:.2f} 小时</b>

<br>

{sleep_comment}



<h2>数据趋势</h2>

Recovery趋势：
{recovery_trend}

<br>

HRV趋势：
{hrv_comment}

<br>

睡眠情况：
{sleep_comment}

<br>

Strain风险：
{strain_comment}

<br>


<h2>未来1-3天</h2>

1. 保证睡眠 ≥8小时<br>
2. 根据 Recovery 调整训练<br>
3. 避免连续高 Strain


<h2>AI 周总结</h2>

<div style="white-space:pre-line;">
{ai_summary}
</div>


<h2>私人教练建议</h2>

{training_plan}

"""

def whoop_week():
    try:
        data = get_whoop_week_data()
        report = generate_week_report(data)
        return report

    except Exception as e:
        print("WEEK ERROR:", e)
        return "暂无数据"


def auto_save_daily():

    print("AUTO SAVE START")

    try:
        

        data = get_whoop_data()

        print("WHOOP DATA:")
        print(data)

        metrics = extract_daily_metrics(
            data
        )

        print("METRICS:")
        print(metrics)

        save_daily_data(
            metrics
        )

        print(
            "AUTO DAILY SAVE OK"
        )


    except Exception as e:

        print(
            "AUTO DAILY SAVE ERROR:",
            e
        )

@app.route("/whoop/auto-report")
def auto_report():


    if not check_api_key():

        return jsonify({

            "error":
            "unauthorized"

        }),401


    try:

        print(
            "========== AUTO REPORT START =========="
        )


        # =========================
        # 1. 获取 WHOOP 数据
        # =========================

        data = {

            "recovery":
            whoop_get("/recovery"),


            "cycle":
            whoop_get("/cycle"),


            "sleep":
            whoop_get("/activity/sleep"),


            "workout":
            whoop_get("/activity/workout")

        }


        print( 
            "SLEEP RECORD COUNT:",
            len(
                data["sleep"].get("records",[])
            )
        )


        # =========================
        # 2. 时间转换
        # =========================

        convert_utc_to_beijing(
            data
        )

        
        # =========================
        # 3. 提取健康指标
        # =========================

        metrics = extract_daily_metrics(
            data
        )


        print(
            "DAILY METRICS SAVING:",
            {
                "recovery_score": metrics.get("recovery_score"),
                "hrv": metrics.get("hrv"),
                "sleep_duration": metrics.get("sleep_duration"),
                "cycle_strain": metrics.get("cycle_strain")
            }
        )


        # =========================
        # 4. 保存数据库
        # =========================

        print("===== BEFORE SAVE DAILY DATA =====")

        save_daily_data(
            metrics
        )

        print("===== AFTER SAVE DAILY DATA =====")


        # =========================
        # 5. 生成基础报告
        # =========================

        report = generate_health_report(
            data
        )



        # =========================
        # 6. AI健康教练
        # =========================

        ai_prompt = f"""

你是 WHOOP 私人健康教练。


今日数据：

💚 Recovery:
{metrics.get("recovery_score",0)}%


❤️ HRV:
{metrics.get("hrv",0)} ms


❤️‍🔥 静息心率:
{metrics.get("resting_heart_rate",0)} bpm


😴 睡眠时间:
{metrics.get("sleep_duration",0)} 小时


🌙 睡眠评分:
{metrics.get("sleep_score",0)}%


🔥 Strain:
{metrics.get("cycle_strain",0)}



请生成：

🟢 今日身体状态

💚 Recovery分析

😴 睡眠分析

🔥 训练建议

⚠️ 风险提醒

📅 未来1-3天建议


要求：

中文简体

使用emoji

400字以内

不要编造数据

像私人WHOOP教练

"""


        coach_advice = generate_ai_summary(
            ai_prompt
        )


        print(
            "AI COACH GENERATED"
        )


        print(
            "========== DAILY REPORT SUCCESS =========="
        )


        success_time = (
            datetime.utcnow()
            + timedelta(hours=8)
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )


        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            DELETE FROM system_status
            """
        )


        cur.execute(
            """
            INSERT INTO system_status
            (last_success_time)

            VALUES
            (%s)
            """,
            (
                success_time,
            )
        )


        conn.commit()

        print(
                "SYSTEM STATUS UPDATED:",
                success_time
            )


        conn.commit()

        cur.close()

        conn.close()


        print(
            "SYSTEM STATUS UPDATED:",
            success_time
        )

    

        print(
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "recovery": metrics.get("recovery_score"),
                "hrv": metrics.get("hrv"),
                "sleep": metrics.get("sleep_duration"),
                "strain": metrics.get("cycle_strain"),
                "ai": "OK",
                "database": "OK"
            }
        )

        
        
        # =========================
        # 7. 返回
        # =========================

        return jsonify({

            "status":
            "daily report generated",


            "report":
            report,


            "coach":
            coach_advice,


            "metrics":
            metrics

        })


    except Exception as e:


        print(
            "AUTO REPORT ERROR:",
            e
        )


        return jsonify({

            "error":
            str(e)

        })

@app.route("/health")
def health():

    try:

        # =====================
        # WHOOP TOKEN CHECK
        # =====================

        whoop_token_status = "ERROR"


        try:

            conn_token = get_db_connection()

            cur_token = conn_token.cursor()


            cur_token.execute(
                """
                SELECT access_token
                FROM tokens
                WHERE access_token IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """
            )


            token_row = cur_token.fetchone()


            if token_row and token_row[0]:

                whoop_token_status = "OK"

            else:

                whoop_token_status = "MISSING"


            cur_token.close()

            conn_token.close()


        except Exception as e:

            print(
                "TOKEN HEALTH ERROR:",
                e
            )

            whoop_token_status = "ERROR"


        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                sleep_duration,
                cycle_strain
            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 1
            """
        )


        row = cur.fetchone()


        # =====================
        # SYSTEM STATUS CHECK
        # =====================

        cur.execute(
             """
             SELECT last_success_time
             FROM system_status
             LIMIT 1
             """
        )


        status_row = cur.fetchone()


        cur.close()

        conn.close()


        if row:

            return jsonify({

                "app": "OK",

                "database": "OK",

                "whoop_token":
                whoop_token_status,
            
                "last_report":
                row[0],

                "last_success_time":
                status_row[0] if status_row else None,

                "recovery":
                row[1],

                "sleep":
                row[2],

                "strain":
                row[3]

            })


        else:

            return jsonify({

                "app": "OK",

                "database": "OK",

                "last_report": None

            })


    except Exception as e:


        print(
            "HEALTH CHECK ERROR:",
            e
        )


        return jsonify({

            "app": "ERROR",

            "database": "ERROR",

            "error": str(e)

        }), 500
        

def trend_report():

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                cycle_strain

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 7
            """
        )


        rows = cur.fetchall()


        cur.close()

        conn.close()



        if not rows:

            return """

            <h1>
            暂无历史数据
            </h1>

            """



        # 转换为日期正序

        rows = list(
            reversed(rows)
        )



        history = []


        recovery_values = []

        hrv_values = []

        resting_hr_values = []

        sleep_values = []

        sleep_score_values = []

        strain_values = []



        for r in rows:


            item = {

                "date": r[0],

                "recovery_score": r[1],

                "hrv": r[2],

                "resting_heart_rate": r[3],

                "sleep_duration": r[4],

                "sleep_score": r[5],

                "cycle_strain": r[6]

            }


            history.append(item)



            if r[1] is not None:

                recovery_values.append(
                    float(r[1])
                )


            if r[2] is not None:

                hrv_values.append(
                    float(r[2])
                )


            if r[3] is not None:

                resting_hr_values.append(
                    float(r[3])
                )


            if r[4] is not None:

                sleep_values.append(
                    float(r[4])
                )


            if r[5] is not None:

                sleep_score_values.append(
                    float(r[5])
                )


            if r[6] is not None:

                strain_values.append(
                    float(r[6])
                )




        # =====================
        # 基础计算
        # =====================

        def avg(values):

            if not values:

                return 0


            return round(
                sum(values) / len(values),
                2
            )



        def change_percent(values):

            if len(values) < 2:

                return 0


            first = values[0]

            last = values[-1]


            if first == 0:

                return 0


            return round(
                ((last-first)/first)*100,
                1
            )




        avg_recovery = avg(
            recovery_values
        )


        avg_hrv = avg(
            hrv_values
        )


        avg_resting_hr = avg(
            resting_hr_values
        )


        avg_sleep = avg(
            sleep_values
        )


        avg_sleep_score = avg(
            sleep_score_values
        )


        avg_strain = avg(
            strain_values
        )



        recovery_change = change_percent(
            recovery_values
        )


        hrv_change = change_percent(
            hrv_values
        )


        sleep_change = change_percent(
            sleep_values
        )


        strain_change = change_percent(
            strain_values
        )




        # =====================
        # Readiness训练准备度
        # =====================

        readiness = 0



        readiness += avg_recovery * 0.4



        if avg_sleep >= 8:

            readiness += 30


        elif avg_sleep >= 6.5:

            readiness += 20


        else:

            readiness += 10




        if avg_strain < 5:

            readiness += 20


        elif avg_strain < 12:

            readiness += 30


        else:

            readiness += 10



        readiness = round(
            min(readiness,100),
            1
        )


        # =====================
        # 风险检测
        # =====================

        risks = []


        if len(history) < 3:

            risks.append(
                "历史数据不足3天，趋势判断仅供参考"
            )



        if avg_recovery < 60:

            risks.append(
                "平均Recovery偏低，需要关注恢复"
            )



        if hrv_change < -10:

            risks.append(
                "HRV下降超过10%，可能存在疲劳累积"
            )



        if avg_resting_hr > 0 and len(resting_hr_values) >= 3:


            rhr_change = change_percent(
                resting_hr_values
            )


            if rhr_change > 5:

                risks.append(
                    "静息心率升高，身体压力增加"
                )



        if avg_sleep < 6.5:

            risks.append(
                "平均睡眠不足，可能影响恢复"
            )




        # =====================
        # 风险等级
        # =====================

        if len(risks) == 0:

            risk_level = " 低风险"


        elif len(risks) <= 2:

            risk_level = " 中风险"


        else:

            risk_level = " 高风险"



        # =====================
        # AI教练建议
        # =====================

        coach = []


        if readiness >= 80:


            coach.append(
                "训练准备度优秀，可以保持正常训练"
            )


            coach.append(
                "建议目标 Strain：10-12"
            )


        elif readiness >= 60:


            coach.append(
                "训练准备度一般，建议中等强度训练"
            )


            coach.append(
                "避免连续高负荷训练"
            )


        else:


            coach.append(
                "训练准备度偏低，优先恢复"
            )


            coach.append(
                "未来1-3天建议降低训练量20-30%"
            )



        if risks:


            coach.append(
                "近期存在恢复压力信号，请关注睡眠"
            )




        risk_html = "<br>".join(
            [
                "⚠️ " + r
                for r in risks
            ]
        )


        if not risk_html:

            risk_html = " 暂未发现明显恢复风险"



        coach_html = "<br>".join(
            [
                "• " + c
                for c in coach
            ]
        )

        # =====================
        # 趋势总结文字
        # =====================

        if recovery_change > 5:

            recovery_summary = "⬆️ Recovery 明显提升，身体恢复状态变好"

        elif recovery_change < -5:

            recovery_summary = "⬇️ Recovery 下降，需要关注恢复"

        else:

            recovery_summary = "➡️ Recovery 保持稳定"
        

        if hrv_change > 5:

            hrv_summary = "HRV 上升，神经恢复状态良好"

        elif hrv_change < -10:

            hrv_summary = "HRV 下降，可能存在疲劳累积"

        else:

            hrv_summary = "HRV 保持稳定"



        if sleep_change > 5:

            sleep_summary = "睡眠时间增加，恢复条件改善"

        elif sleep_change < -10:

            sleep_summary = "睡眠减少，需要增加休息"

        else:

            sleep_summary = "睡眠保持稳定"



        trend_summary = (
            recovery_summary
            + "<br>"
            + hrv_summary
            + "<br>"
            + sleep_summary
        )


        return f"""

        <!DOCTYPE html>

        <html>

        <head>

        <meta charset="UTF-8">

        <title>WHOOP 7天趋势</title>


        <style>

        body {{
            font-family:Arial;
            background:#f5f7fa;
            padding:30px;
        }}


        .card {{

            background:white;

            border-radius:15px;

            padding:25px;

            margin-bottom:20px;

            box-shadow:0 4px 12px rgba(0,0,0,0.1);

        }}


        .metric {{

            font-size:20px;
    
            margin:12px;

        }}

        </style>


        </head>



        <body>


        <div class="card">

        <h1>
        📈 WHOOP 7天趋势分析
        </h1>


        </div>

       
        <div class="card">

        <h2>
        📊 平均状态
        </h2>


        <div class="metric">

        💚 平均 Recovery:
        {avg_recovery}%

        </div>


        <div class="metric">

        ❤️ 平均 HRV:
        {avg_hrv} ms

        </div>


        <div class="metric">

        🔥 平均静息心率:
        {avg_resting_hr} bpm

        </div>


        <div class="metric">

        😴 平均睡眠:
        {avg_sleep} 小时

        </div>


        <div class="metric">

        🔥 平均 Strain:
        {avg_strain}

        </div>


        </div>

        <div class="card">

        <h2>
        🧠 趋势分析
        </h2>


        <p>

        {trend_summary}

        </p>


        </div>


        <div class="card">


        <h2>

        🧠 训练准备度

        </h2>


        <div class="metric">

        {readiness}/100

        </div>


        </div>




        <div class="card">


        <h2>

        ⚠️ 风险等级

        </h2>


        <div class="metric">

        {risk_level}

        </div>


        <p>

        {risk_html}

        </p>


        </div>




        <div class="card">


        <h2>

        🤖 AI健康教练建议

        </h2>


        <p>

        {coach_html}

        </p>


        </div>



    
        <div class="card">


        <h2>

        📅 最近7天记录

        </h2>


        {''.join(

        f"""

        <hr>

        <h3>{item['date']}</h3>

        <p>
        Recovery:
        {item['recovery_score']}%
        </p>

        <p>
        HRV:
        {item['hrv']} ms
        </p>


        <p>
        睡眠:
        {item['sleep_duration']} 小时
        </p>


        <p>
        Strain:
        {item['cycle_strain']}
        </p>

        """

        for item in history

        )}


        </div>



        </body>

        </html>

        """

    except Exception as e:

        print(
            "TREND REPORT ERROR:",
            e
        )

        return str(e)
        

def home():

    status = " 系统正常"

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                sleep_duration,
                cycle_strain
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 1
            """
        )


        row = cur.fetchone()


        cur.close()
        conn.close()



        if row:

            date = row[0]

            recovery = row[1]

            hrv = row[2]

            sleep = row[3]

            strain = row[4]


        else:

            date = "暂无数据"

            recovery = None

            hrv = None

            sleep = None

            strain = None



        # =====================
        # Readiness训练准备度
        # =====================

        readiness = 0


        if recovery is not None:

            readiness += float(recovery) * 0.4



        if sleep is not None:


            if float(sleep) >= 8:

                readiness += 30


            elif float(sleep) >= 6:

                readiness += 20


            else:

                readiness += 10



        if strain is not None:


            if float(strain) < 5:

                readiness += 20


            elif float(strain) < 12:

                readiness += 30


            else:

                readiness += 10



        readiness = round(
            min(readiness,100),
            1
        )


        # =====================
        # Strain解释
        # =====================


        if strain is not None:


            strain_value = float(strain)



            if strain_value < 5:


                strain_text = (
                    " 恢复日\n"
                    "当前训练压力较低，适合增加Zone2有氧或轻力量训练。"
                )


            elif strain_value < 12:


                strain_text = (
                    " 最佳训练区间\n"
                    "当前负荷适中，可以完成主要训练。"
                )


            elif strain_value < 17:


                strain_text = (
                    " 高压力训练\n"
                    "注意睡眠和恢复。"
                )


            else:


                strain_text = (
                    " 极高压力\n"
                    "建议降低训练量。"
                )


        else:


            strain_text = "暂无训练压力数据"



        # =====================
        # AI建议
        # =====================


        if readiness >= 80:


            advice = (
                "恢复能力优秀。"
                "今天适合完成主要训练。"
                "建议目标 Strain 10-12。"
            )


        elif readiness >=60:


            advice = (
                "身体状态一般。"
                "建议中等强度训练，避免连续高负荷。"
            )


        else:


            advice = (
                "当前恢复不足。"
                "建议优先恢复、睡眠和低强度活动。"
            )


        return f"""

<!DOCTYPE html>

<html lang="zh-CN">

<head>

<meta charset="UTF-8">

<title>WHOOP AI Coach</title>


<style>


body{{

font-family:Arial;

background:#f4f5f7;

padding:20px;

}}


.container{{

max-width:700px;

margin:auto;

}}


.card{{

background:white;

padding:25px;

border-radius:18px;

margin-bottom:18px;

box-shadow:0 3px 12px rgba(0,0,0,.08);

}}


.value{{

font-size:36px;

font-weight:bold;

}}


.button{{

display:block;

background:#111;

color:white;

padding:15px;

margin-top:10px;

border-radius:12px;

text-align:center;

text-decoration:none;

}}


</style>


</head>


<body>


<div class="container">



<div class="card">

<h1>WHOOP AI 教练</h1>

<h2>{status}</h2>

<p>最新数据：{date}</p>

</div>




<div class="card">

<h3>训练准备度 Readiness</h3>

<div class="value">

{readiness}/100

</div>

<p>
综合 Recovery、睡眠、训练压力计算
</p>

</div>





<div class="card">

<h3>恢复 Recovery</h3>

<div class="value">

{recovery if recovery is not None else "-" }%

</div>

</div>





<div class="card">

<h3>HRV 心率变异性</h3>

<div class="value">

{round(float(hrv),2) if hrv else "-" } ms

</div>

</div>





<div class="card">

<h3>睡眠</h3>

<div class="value">

{round(float(sleep),2) if sleep else "-" } 小时

</div>

</div>





<div class="card">

<h3>训练压力 Strain</h3>

<div class="value">

{round(float(strain),2) if strain else "-"}

</div>


<p>

{strain_text}

</p>

</div>





<div class="card">

<h3>AI教练建议</h3>


<p>

{coach_advice}

</p>


</div>





<div class="card">


<a class="button"
href="/whoop/today">

今日报告

</a>


<a class="button"
href="/whoop/trend">

最近7天趋势

</a>


<a class="button"
href="/whoop/auto-report">

最新生成报告

</a>


</div>



</div>


</body>

</html>

"""



    except Exception as e:


        return f"""

        <h1>WHOOP Dashboard Error</h1>

        <p>{str(e)}</p>

        """



if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8080
    )
