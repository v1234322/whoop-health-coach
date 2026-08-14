import json
import os
import hmac

print("WHOOP HEALTH COACH STARTED")

import psycopg2

from psycopg2.extras import RealDictCursor

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

    cur = conn.cursor()

    cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name='daily_metrics'
    """)

    print(
        "DAILY METRICS COLUMNS:",
        cur.fetchall()
    )    


    # =========================
    # WHOOP TOKEN
    # =========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tokens(

        id SERIAL PRIMARY KEY,

        access_token TEXT,

        refresh_token TEXT,

        expires_at BIGINT,

        updated_at TIMESTAMP DEFAULT NOW()

    )
    """)

   
    cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='tokens'
    """)

    print(
        "TOKENS COLUMNS:",
        cur.fetchall()
    )

    # =========================
    # 重建 daily_metrics
    # =========================

    cur.execute("""
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_coach_reports (

        id SERIAL PRIMARY KEY,

        report_date TEXT UNIQUE,

        recovery REAL,

        whoop_strain REAL,

        climbing_load REAL,

        hangboard_load REAL,

        fatigue_score REAL,

        training_advice TEXT,

        risk_warning TEXT,

        ai_report TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );
    """)
    

    # ==============================
    # 攀岩训练日志
    # ==============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS climbing_training_log (

        id SERIAL PRIMARY KEY,

        training_date TEXT,

        training_type TEXT,

        duration INTEGER,

        intensity TEXT,

        climbing_grade TEXT,

        boulder_count INTEGER,

        hangboard_seconds INTEGER,

        hangboard_weight REAL,

        finger_fatigue INTEGER,

        forearm_fatigue INTEGER,

        notes TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)



    # ==============================
    # 指力板训练日志
    # ==============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS hangboard_training_log (

        id SERIAL PRIMARY KEY,

        training_date TEXT,

        protocol TEXT,

        session_type TEXT,

        edge_size TEXT,

        grip_type TEXT,

        added_weight REAL,

        hold_seconds INTEGER,

        duration INTEGER,

        sets INTEGER,

        total_hang_time INTEGER,

        intensity TEXT,

        finger_fatigue INTEGER,
        
        elbow_fatigue INTEGER,

        recovery_after INTEGER,

        notes TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );
    """)


    # =========================
    # 修复旧 hangboard 表字段
    # =========================

    hangboard_columns = [
        ("protocol", "TEXT"),
       ("session_type", "TEXT"),
        ("edge_size", "TEXT"),
        ("grip_type", "TEXT"),
        ("added_weight", "REAL"),
        ("hold_seconds", "INTEGER"),
        ("duration", "INTEGER"),
        ("sets", "INTEGER"),
        ("total_hang_time", "INTEGER"),
        ("intensity", "TEXT"),
        ("finger_fatigue", "INTEGER"),
        ("elbow_fatigue", "INTEGER"),
        ("recovery_after", "INTEGER"),
    ]


    for column, dtype in hangboard_columns:

        try:

            cur.execute(
                f"""
                ALTER TABLE hangboard_training_log
                ADD COLUMN IF NOT EXISTS {column} {dtype}
                """
            )

            print(
                f"HANGBOARD CHECK COLUMN: {column}"
            )

        except Exception as e:

            print(
                "HANGBOARD MIGRATION ERROR:",
                e
            )
            conn.rollback()

    

    # ==============================
    # 训练周期分析
    # ==============================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS training_cycle_analysis (

        id SERIAL PRIMARY KEY,

        analysis_date TEXT UNIQUE,

        weekly_climbing_sessions INTEGER,

        weekly_total_duration INTEGER,

        avg_finger_fatigue REAL,

        avg_forearm_fatigue REAL,

        hard_session_count INTEGER,

        recovery_status TEXT,

        training_recommendation TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );
    """)


    # ==============================
    # 检查攀岩训练表
    # ==============================

    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='climbing_training_log'
         ORDER BY ordinal_position
         """
     )

    print(
        "CLIMBING TABLE COLUMNS:",
        cur.fetchall()
    )


    # =========================
    # 检查指力板训练表
    # =========================

    conn.commit()

    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='hangboard_training_log'
        ORDER BY ordinal_position
        """
    )


    print(
        "HANGBOARD TABLE COLUMNS:",
        cur.fetchall()
    )



    # =========================
    # 系统状态表
    # =========================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_status (

        id SERIAL PRIMARY KEY,

        last_success_time TEXT

    )
    """)


    # =========================
    # 健康扩展模块
    # 经期 / 身体温度 / 伤病管理
    # =========================


    # 经期记录
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS menstrual_cycle_log(

        id SERIAL PRIMARY KEY,

        cycle_date DATE NOT NULL,

        cycle_day INTEGER,

        phase TEXT,

        symptoms TEXT,

        pain_level INTEGER DEFAULT 0,

        energy_level INTEGER DEFAULT 0,

        notes TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    print("MENSTRUAL TABLE READY")



    # 身体温度监测

    cur.execute("""
    ALTER TABLE daily_metrics
    ADD COLUMN IF NOT EXISTS skin_temperature REAL
    """)

    cur.execute("""
    ALTER TABLE daily_metrics
    ADD COLUMN IF NOT EXISTS temperature_status TEXT
    """)

    cur.execute("""
    ALTER TABLE daily_metrics
    ADD COLUMN IF NOT EXISTS temperature_deviation REAL
    """)

    print("TEMPERATURE FIELD READY")


    # 伤病记录

    cur.execute("""
    CREATE TABLE IF NOT EXISTS injury_log(

        id SERIAL PRIMARY KEY,

        injury_date DATE,

        body_part TEXT,

        injury_type TEXT,

        pain_level INTEGER DEFAULT 0,

        description TEXT,

        movement_limit TEXT,

        training_effect TEXT,

        notes TEXT,
    
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)  

    print("INJURY TABLE READY")

    try:

        conn.commit()

        print(
            "DATABASE INIT SUCCESS"
        )

    except Exception as e:

        print(
            "DATABASE INIT ERROR:",
            e
        )

        conn.rollback()


    finally:

        cur.close()

        conn.close()


    print(
        "DATABASE READY"
    )



# 启动初始化

init_db()


# 数据维护任务

clean_duplicate_daily_metrics()

ensure_refresh_token()


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


        # Recovery 颜色判断
        recovery = metrics.get("recovery_score") or 0

        if recovery >= 67:
            recovery_color = "🟢 绿色 - 恢复良好"
        elif recovery >= 34:
            recovery_color = "🟡 黄色 - 需要控制训练"
        else:
            recovery_color = "🔴 红色 - 优先恢复"


        ai_prompt = f"""


        WHOOP 数据:


        今日健康评分:
        {health_score}/100

        Recovery:
        {metrics.get("recovery_score")}%

        Recovery状态:
        {recovery_color}

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


请严格按照以下结构输出：

🟡 今日教练总结

用1-2句话总结今天身体状态。
告诉用户今天最重要的一件事。


🧠 今日身体状态

解释身体趋势。
不要简单重复数字。


❤️ 恢复分析

分析Recovery、HRV、静息心率代表的身体信号。


😴 睡眠分析

分析睡眠时间、效率、深睡和REM。
给改善建议。


🏋️ 今日训练建议

明确：

✅ 推荐：
今天适合做什么。

❌ 避免：
今天不建议做什么。


📈 明日恢复预测

根据今天和最近趋势预测未来1-3天。

要求：

中文简体
使用emoji
不要像数据报告
不要重复大量数字
重点解释身体信号
给明确行动建议
像WHOOP私人教练
500字以内

        """

        print("===== AI PROMPT CHECK =====")
        print(ai_prompt)
        print("==========================")

        ai_summary = generate_ai_summary(
            ai_prompt
        )
        ai_summary = ai_summary.strip()


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
            font-size:21px;
            line-height:1.9;
            max-width:900px;
            padding-top:0;
            margin:auto;
            letter-spacing:0.5px;
        }}
        

        .ai-text::first-line {{

            font-size:28px;
            font-weight:bold;
            margin-top:35px;
            margin-bottom:15px;

        }}
        

        .ai-text strong {{

            display:block;
            font-size:28px;
            font-weight:bold;
            margin-top:35px;
            margin-bottom:20px;

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


@app.route("/api/whoop/profile", methods=["GET"])
@require_chatgpt_api_key
def api_whoop_profile():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT
                AVG(recovery_score),
                AVG(hrv),
                AVG(resting_heart_rate),
                AVG(sleep_duration),
                AVG(cycle_strain)

            FROM (
                SELECT *
                FROM daily_metrics
                ORDER BY report_date DESC
                LIMIT 7
            )
            """
        )


        row = cur.fetchone()


        if not row:
            return jsonify({
                "success": False,
                "message": "暂无历史数据"
            })


        return jsonify({

            "success": True,

            "baseline": {

                "avg_recovery_7d":
                    round(row[0] or 0,1),

                "avg_hrv_7d":
                    round(row[1] or 0,1),

                "avg_rhr_7d":
                    round(row[2] or 0,1),

                "avg_sleep_hours":
                    round(row[3] or 0,2),

                "avg_strain":
                    round(row[4] or 0,1)
            }

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }),500


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


@app.route("/api/whoop/training-advice", methods=["GET"])
@require_chatgpt_api_key
def api_whoop_training_advice():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT

                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
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

                "message": "暂无今日数据"

            })


        recovery = row[0] or 0
        hrv = row[1] or 0
        rhr = row[2] or 0
        sleep = row[3] or 0
        strain = row[4] or 0



        # =====================
        # 训练决策逻辑
        # =====================


        if recovery >= 67:


            level = "high"

            recommendation = [
                "正常训练",
                "力量训练",
                "间歇训练"
            ]

            target_strain = "10-14"


            avoid = []


        elif recovery >= 45:


            level = "medium"


            recommendation = [
                "中低强度训练",
                "Zone2有氧",
                "技术训练"
            ]


            target_strain = "6-10"


            avoid = [
                "极限冲刺",
                "连续高负荷训练"
            ]


        else:


            level = "low"


            recommendation = [
                "主动恢复",
                "散步",
                "拉伸",
                "轻Zone2"
            ]


            target_strain = "3-6"


            avoid = [
                "HIIT",
                "大重量训练",
                "力竭训练"
            ]



        # HRV额外修正

        if hrv < 45:

            avoid.append(
                "高神经压力训练"
            )


        return jsonify({

            "success": True,


            "training_advice": {


                "recovery": recovery,

                "hrv": hrv,

                "resting_heart_rate": rhr,

                "sleep_hours": sleep,

                "strain": strain,


                "training_level": level,


                "recommended_training":
                    recommendation,


                "avoid":
                    avoid,


                "target_strain":
                    target_strain

            }

        })


    except Exception as e:


        return jsonify({

            "success": False,

            "error": str(e)

        }),500


    finally:


        if cur:
            cur.close()


        if conn:
            conn.close()
            

@app.route("/api/whoop/coach-report", methods=["GET"])
@require_chatgpt_api_key
def api_whoop_coach_report():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()


        # =========================
        # 1. 今日 WHOOP 数据
        # =========================

        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                sleep_efficiency,
                deep_sleep_duration,
                rem_sleep_duration,
                cycle_strain,
                skin_temperature,
                temperature_deviation,
                temperature_status
            FROM daily_metrics
            ORDER BY report_date DESC
            LIMIT 1
            """
        )

        today = cur.fetchone()


        if not today:

            return jsonify({
                "success": False,
                "message": "暂无今日数据"
            })


        # =========================
        # 2. 7天基线
        # =========================

        cur.execute(
            """
            SELECT
                AVG(recovery_score),
                AVG(hrv),
                AVG(resting_heart_rate),
                AVG(sleep_duration),
                AVG(cycle_strain)

            FROM (
                SELECT
                    recovery_score,
                    hrv,
                    resting_heart_rate,
                    sleep_duration,
                    cycle_strain

                FROM daily_metrics

                ORDER BY report_date DESC

                LIMIT 7
            ) AS recent_metrics
            """
        )

        baseline = cur.fetchone()


        # =========================
        # 3. 最新 AI Coach 报告
        # =========================

        cur.execute(
            """
            SELECT
                ai_report,
                training_advice,
                risk_warning,
                menstrual_data,
                temperature_data,
                injury_data

            FROM daily_coach_reports

            ORDER BY report_date DESC

            LIMIT 1
            """
        )

        saved_coach = cur.fetchone()


        # =========================
        # 4. 基础指标
        # =========================

        recovery = float(today[1] or 0)
        hrv = float(today[2] or 0)
        rhr = float(today[3] or 0)

        sleep_hours = float(today[4] or 0)
        sleep_score = float(today[5] or 0)
        sleep_efficiency = float(today[6] or 0)

        deep_sleep_hours = float(today[7] or 0)
        rem_sleep_hours = float(today[8] or 0)

        current_strain = float(today[9] or 0)


        avg_recovery = float(
            baseline[0] or 0
        )

        avg_hrv = float(
            baseline[1] or 0
        )

        avg_rhr = float(
            baseline[2] or 0
        )

        avg_sleep = float(
            baseline[3] or 0
        )

        avg_strain = float(
            baseline[4] or 0
        )


        # =========================
        # 5. 睡眠结构
        # =========================

        deep_sleep_ratio = (
            round(
                deep_sleep_hours
                / sleep_hours
                * 100,
                1
            )
            if sleep_hours > 0
            else 0
        )


        rem_sleep_ratio = (
            round(
                rem_sleep_hours
                / sleep_hours
                * 100,
                1
            )
            if sleep_hours > 0
            else 0
        )


        light_sleep_ratio = (
            round(
                max(
                    100
                    - deep_sleep_ratio
                    - rem_sleep_ratio,
                    0
                ),
                1
            )
            if sleep_hours > 0
            else 0
        )


        # =========================
        # 6. Recovery颜色等级
        # =========================

        if recovery >= 67:

            recovery_status = (
                "🟢 绿色 - 恢复良好"
            )

        elif recovery >= 34:

            recovery_status = (
                "🟡 黄色 - 需要控制训练"
            )

        else:

            recovery_status = (
                "🔴 红色 - 优先恢复"
            )


        # =========================
        # 7. 基础训练决策
        # =========================

        if recovery >= 67:

            if (
                sleep_efficiency >= 90
                and deep_sleep_ratio >= 20
            ):

                training_level = (
                    "高强度训练"
                )

                calculated_training_advice = (
                    "恢复状态良好，睡眠结构支持训练。"
                    "可以安排力量训练、间歇训练"
                    "或较高强度训练。"
                )

            else:

                training_level = (
                    "中高强度训练"
                )

                calculated_training_advice = (
                    "Recovery良好，"
                    "但睡眠结构仍有提升空间。"
                    "建议控制总训练量，"
                    "避免连续冲击极限。"
                )


        elif recovery >= 34:

            training_level = (
                "中等强度训练"
            )

            calculated_training_advice = (
                "身体处于可训练状态，"
                "但恢复未达到最佳。"
                "建议中等强度训练，"
                "如Zone 2、技术训练"
                "或正常力量训练。"
            )


        else:

            training_level = (
                "恢复训练"
            )

            calculated_training_advice = (
                "Recovery偏低，"
                "身体可能存在恢复压力。"
                "建议降低训练强度，"
                "以恢复、拉伸和低强度活动为主。"
            )


        # HRV修正

        if (
            avg_hrv > 0
            and hrv < avg_hrv * 0.85
        ):

            calculated_training_advice += (
                " HRV明显低于个人平均，"
                "今天应避免高强度刺激。"
            )


        # RHR修正

        if (
            avg_rhr > 0
            and rhr > avg_rhr + 5
        ):

            calculated_training_advice += (
                " 静息心率偏高，"
                "提示恢复压力，"
                "建议进一步降低负荷。"
            )


        # =========================
        # 8. Strain目标
        # =========================

        if recovery >= 67:

            recommended_strain = "12-15"
            target_min = 12

        elif recovery >= 34:

            recommended_strain = "8-12"
            target_min = 8

        else:

            recommended_strain = "0-6"
            target_min = 0


        if target_min > 0:

            strain_completion = round(
                current_strain
                / target_min
                * 100,
                1
            )

        else:

            strain_completion = 100


        remaining_strain = round(
            max(
                target_min
                - current_strain,
                0
            ),
            1
        )


        # =========================
        # 9. 疲劳趋势
        # =========================

        fatigue_warning = "正常"


        if (
            avg_recovery > 0
            and recovery < avg_recovery * 0.85
        ):

            fatigue_warning = (
                "Recovery明显下降，"
                "建议降低训练强度"
            )


        elif (
            avg_recovery > 0
            and avg_hrv > 0
            and avg_rhr > 0
            and recovery < avg_recovery
            and hrv < avg_hrv
            and rhr > avg_rhr
        ):

            fatigue_warning = (
                "恢复压力升高，"
                "可能存在疲劳累积"
            )


        elif (
            avg_recovery > 0
            and avg_hrv > 0
            and recovery < avg_recovery
            and hrv < avg_hrv
        ):

            fatigue_warning = (
                "恢复指标下降，"
                "需要关注训练负荷"
            )


        # =========================
        # 10. 连续3天疲劳
        # =========================

        continuous_fatigue = False


        cur.execute(
            """
            SELECT
                recovery_score,
                hrv,
                resting_heart_rate

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 3
            """
        )

        recent_days = cur.fetchall()


        if (
            len(recent_days) == 3
            and avg_recovery > 0
            and avg_hrv > 0
            and avg_rhr > 0
        ):

            fatigue_days = 0


            for day in recent_days:

                day_recovery = float(
                    day[0] or 0
                )

                day_hrv = float(
                    day[1] or 0
                )

                day_rhr = float(
                    day[2] or 0
                )


                if (
                    day_recovery < avg_recovery
                    and day_hrv < avg_hrv
                    and day_rhr > avg_rhr
                ):

                    fatigue_days += 1


            if fatigue_days >= 3:

                continuous_fatigue = True

                fatigue_warning = (
                    "连续3天恢复压力升高，"
                    "建议安排恢复日"
                )


        # =========================
        # 11. 已保存AI结果
        # =========================

        saved_ai_report = ""
        saved_training_advice = ""
        saved_risk_warning = ""

        menstrual_data = None
        temperature_data = None
        injury_data = None


        if saved_coach:

            saved_ai_report = (
                saved_coach[0] or ""
            )

            saved_training_advice = (
                saved_coach[1] or ""
            )

            saved_risk_warning = (
                saved_coach[2] or ""
            )

            menstrual_data = saved_coach[3]
            temperature_data = saved_coach[4]
            injury_data = saved_coach[5]


        # 优先使用AI已生成建议
        if saved_training_advice:

            final_training_advice = (
                saved_training_advice
            )

        else:

            final_training_advice = (
                calculated_training_advice
            )


        if saved_risk_warning:

            final_risk_warning = (
                saved_risk_warning
            )

        else:

            final_risk_warning = (
                fatigue_warning
            )

     

        print(
            "COACH REPORT READY:",
            today[0],
            strain_completion,
            remaining_strain
        )


        # =========================
        # 12. 返回给GPT
        # =========================

        return jsonify({

            "success": True,

            "coach_report": {

                "today": {

                    "date": today[0],

                    "recovery": round(
                        recovery,
                        1
                    ),

                    "recovery_status":
                    recovery_status,

                    "hrv": round(
                        hrv,
                        1
                    ),

                    "resting_heart_rate":
                    round(
                        rhr,
                        1
                    ),

                    "sleep_hours":
                    round(
                        sleep_hours,
                        2
                    ),

                    "sleep_score":
                    round(
                        sleep_score,
                        1
                    ),

                    "sleep_efficiency":
                    round(
                        sleep_efficiency,
                        1
                    ),

                    "deep_sleep_hours":
                    round(
                        deep_sleep_hours,
                        2
                    ),

                    "rem_sleep_hours":
                    round(
                        rem_sleep_hours,
                        2
                    ),

                    "deep_sleep_ratio":
                    deep_sleep_ratio,

                    "rem_sleep_ratio":
                    rem_sleep_ratio,

                    "light_sleep_ratio":
                    light_sleep_ratio,

                    "strain":
                    round(
                        current_strain,
                        1
                    ),

                    "training_level":
                    training_level,

                    "training_advice":
                    final_training_advice,

                    "risk_warning":
                    final_risk_warning,

                    "strain_completion":
                    strain_completion,

                    "remaining_strain":
                    remaining_strain,

                    "fatigue_warning":
                    fatigue_warning

                },


                "baseline": {

                    "recovery_avg":
                    round(
                        avg_recovery,
                        1
                    ),

                    "hrv_avg":
                    round(
                        avg_hrv,
                        1
                    ),

                    "rhr_avg":
                    round(
                        avg_rhr,
                        1
                    ),

                    "sleep_avg":
                    round(
                        avg_sleep,
                        2
                    ),

                    "strain_avg":
                    round(
                        avg_strain,
                        1
                    )

                },


                "temperature": {

                    "skin_temperature":
                    today[10],

                    "temperature_deviation":
                    today[11],

                    "temperature_status":
                    today[12],

                    "saved_temperature_data":
                    temperature_data

                },


                "menstrual":
                menstrual_data,


                "injury":
                injury_data,


                "coach": {

                    "training_level":
                    training_level,

                    "coach_report_text":
                    saved_ai_report,

                    "training_recommendation":
                    final_training_advice,

                    "risk_warning":
                    final_risk_warning,

                    "current_strain":
                    round(
                        current_strain,
                        1
                    ),

                    "recommended_strain":
                    recommended_strain,

                    "strain_completion":
                    strain_completion,

                    "remaining_strain":
                    remaining_strain,

                    "fatigue_warning":
                    fatigue_warning,

                    "continuous_fatigue":
                    continuous_fatigue

                }

            }

        })


    except Exception as e:

        print(
            "COACH REPORT ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


@app.route("/training/log", methods=["POST"])
def add_training_log():

    data = request.json

    conn = get_db_connection()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO climbing_training_log
        (
        training_date,
        training_type,
        duration,
        intensity,
        climbing_grade,
        boulder_count,
        hangboard_seconds,
        hangboard_weight,
        finger_fatigue,
        forearm_fatigue,
        notes
        )

        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)

        """,

        (
        data.get("training_date"),
        data.get("training_type"),
        data.get("duration"),
        data.get("intensity"),
        data.get("climbing_grade"),
        data.get("boulder_count"),
        data.get("hangboard_seconds"),
        data.get("hangboard_weight"),
        data.get("finger_fatigue"),
        data.get("forearm_fatigue"),
        data.get("notes")
        )
    )


    conn.commit()

    cur.close()
    conn.close()


    return jsonify({
        "success": True,
        "message": "训练记录已保存"
    })


@app.route("/training/history")
def get_training_history():

    conn = get_db_connection()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
        training_date,
        training_type,
        duration,
        intensity,
        climbing_grade,
        finger_fatigue,
        forearm_fatigue,
        notes

        FROM climbing_training_log

        ORDER BY training_date DESC

        LIMIT 30
        """
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()


    return jsonify(rows)


@app.route("/training/hangboard", methods=["POST"])
def training_hangboard():

    data=request.json


    save_hangboard_training(data)


    return jsonify({

        "success":True,

        "message":"指力板训练已保存",

    })


@app.route("/training/hangboard/history")
def hangboard_history():

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cursor.execute(
    """
    SELECT
        training_date,
        protocol,
        session_type,
        edge_size,
        grip_type,
        added_weight,
        hold_seconds,
        duration,
        sets,
        total_hang_time,
        intensity,
        finger_fatigue,
        elbow_fatigue,
        recovery_after,
        notes

    FROM hangboard_training_log

    ORDER BY training_date DESC

    LIMIT 30

    """
    )

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(rows)




import re
import json


@app.route("/whoop/weekly")
def weekly():


    if not check_api_key():

        return jsonify({
            "error": "unauthorized"
        }), 401

 
    try:

        print(
            "========== WEEKLY PAGE START =========="
        )


        # ==========================
        # 1. 获取 Weekly 数据
        # ==========================

        weekly_data = generate_weekly_analysis()


        if not isinstance(
            weekly_data,
            dict
        ):

            raise ValueError(
                "generate_weekly_analysis 返回类型错误"
            )
        
        
        print(
            "WEEKLY DATA READY:",
            weekly_data.get(
                "valid_days",
                0
            )
        )


        if not weekly_data.get(
            "success",
            False
        ):

            error_message = weekly_data.get(
                "error",
                "暂无足够的 WHOOP 周数据"
            )

            return f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <meta
                    name="viewport"
                    content="width=device-width, initial-scale=1.0"
                >
            </head>

            <body
                style="
                    font-family:Arial;
                    padding:30px;
                "
            >
                <h2>
                    ⚠️ WHOOP 周报告暂时无法生成
                </h2>

                <p>
                    {error_message}
                </p>

            </body>
            </html>
            """


        # ==========================
        # 3. 获取 AI Prompt
        # ==========================

        weekly_prompt = weekly_data.get(
            "prompt_text",
            ""
        )


        if not weekly_prompt:

            raise ValueError(
                "Weekly prompt 为空"
            )


        print(
            "WEEKLY PROMPT READY"
        )


        # ==========================
        # 4. 调用 Weekly AI
        # ==========================

        weekly_result = generate_weekly_ai_summary(
            weekly_prompt
        )


        print(
            "WEEKLY AI RESULT:",
            weekly_result
        )


        # ==========================
        # 5. 检查 AI 返回
        # ==========================

        if not isinstance(
            weekly_result,
            dict
        ):

            raise ValueError(
                "generate_weekly_ai_summary 返回类型错误"
            )


        # ==========================
        # 6. 获取 AI 三个字段
        # ==========================

        weekly_report = weekly_result.get(
            "weekly_report",
            ""
        )


        weekly_training_advice = weekly_result.get(
            "weekly_training_advice",
            ""
        )


        weekly_risk_warning = weekly_result.get(
            "weekly_risk_warning",
            "暂无明显风险"
        )


        # ==========================
        # 7. 清理报告格式
        # ==========================

        weekly_report = re.sub(
            r'\n\s*\n+',
            '\n',
            weekly_report
        )


        weekly_report = format_weekly_report(
            weekly_report
        )


        print(
            "WEEKLY REPORT READY"
        )


        # ==========================
        # 8. 直接使用 weekly_data
        # ==========================

        records = weekly_data.get(
            "records",
            []
        )


        valid_days = weekly_data.get(
            "valid_days",
            len(records)
        )


        if valid_days < 7:

            score_period_text = (
                f"{valid_days}天阶段性综合状态"
            )

        else:

            score_period_text = (
                "近7天综合状态"
            )


        start_date = weekly_data.get(
            "start_date"
        )


        end_date = weekly_data.get(
            "end_date"
        )


        if start_date and end_date:

            report_period = (
                f"{start_date} 至 {end_date}"
            )

        else:

            report_period = (
                "暂无数据"
            )


        dates = [
            record.get(
                "report_date"
            )
            for record in records
        ]


        recovery_values = [
            record.get(
                "recovery_score"
            )
            for record in records
                ]


        hrv_values = [
            record.get(
                "hrv"
            )
            for record in records
        ]


        sleep_values = [
            record.get(
                "sleep_duration"
            )
            for record in records
        ]


        strain_values = [
            record.get(
                "cycle_strain"
            )
            for record in records
                ]


        sleep_valid_days = sum(
            1
            for value in sleep_values
            if value is not None
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
    
    
        avg_recovery = weekly_data.get(
            "avg_recovery",
            0
        )

        avg_hrv = weekly_data.get(
            "avg_hrv",
            0
        )


        hrv_color = hrv_status(
            avg_hrv
        )


        if not avg_hrv:

            hrv_text = "暂无数据"

        else:

            hrv_text = "近7天平均 HRV"


        avg_sleep = weekly_data.get(
            "avg_sleep",
            0
        )

        avg_strain = weekly_data.get(
            "avg_strain",
            0
        )

        
        # 综合健康评分

        health_score = 0


        # Recovery 50%
        if avg_recovery is not None:

            health_score += (
                avg_recovery * 0.5
            )


        # HRV 30%
        if avg_hrv is not None:

            health_score += (
                min(
                    avg_hrv,
                    100
                )
                * 0.3
            )


        # 睡眠 20%
        if avg_sleep is not None:
        
            sleep_component = min(
                avg_sleep / 8 * 100,
                100
            )

            health_score += (
                sleep_component * 0.2
            )

        
        health_score = round(
            health_score
        )


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


.ai-risk-box {{

background:#fafafa;

border-radius:16px;

padding:14px 18px;

margin-bottom:12px;

}}


.ai-risk-title {{

font-size:22px;

font-weight:bold;

margin-bottom:8px;

color:#dc2626;

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



<!-- Weekly 主报告 -->

<div class="ai-item">

<div class="ai-content">

{weekly_report}

</div>

</div>



<!-- 未来7天训练建议 -->

<div class="ai-item">

<div class="ai-item-title">

🏋️ 未来7天训练建议

</div>

<div class="ai-content">

{weekly_training_advice}

</div>

</div>



<!-- 风险提醒 -->

<div class="ai-risk-box">

<div class="ai-risk-title">

⚠️ 未来7天风险提醒

</div>

<div class="ai-content">

{weekly_risk_warning}

</div>

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


# ==============================
# 训练负荷分析
# ==============================

def get_training_load_summary():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(duration),0),
        COALESCE(AVG(finger_fatigue),0),
        COALESCE(AVG(forearm_fatigue),0)

    FROM climbing_training_log

    WHERE training_date::date >= CURRENT_DATE - INTERVAL '7 days'
    """)

    climbing = cursor.fetchone()

    if climbing is None:
        climbing = {
            "sessions": 0,
            "total_duration": 0
        }


    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(total_hang_time),0),
        COALESCE(AVG(finger_fatigue),0),
        COALESCE(AVG(elbow_fatigue),0)

    FROM hangboard_training_log

    WHERE training_date::date >= CURRENT_DATE - INTERVAL '7 days'
    """)

    hangboard = cursor.fetchone()


    cursor.close()
    conn.close()


    return {

        "climbing_sessions": climbing[0],
        "climbing_duration": climbing[1],
        "avg_finger_fatigue": round(climbing[2],1),
        "avg_forearm_fatigue": round(climbing[3],1),

        "hangboard_sessions": hangboard[0],
        "hang_time": hangboard[1],
        "hangboard_finger_fatigue": round(hangboard[2],1),
        "elbow_fatigue": round(hangboard[3],1)

    }


def analyze_climbing_fatigue(training_load):

    # =========================
    # 1. 读取最新局部疲劳
    # =========================

    finger = float(
        training_load.get(
            "latest_finger_fatigue",
            training_load.get(
                "finger_fatigue",
                0
            )
        ) or 0
    )


    elbow = float(
        training_load.get(
            "latest_elbow_fatigue",
            training_load.get(
                "elbow_fatigue",
                0
            )
        ) or 0
    )


    # =========================
    # 2. 最近7天训练频率
    # =========================

    hang_sessions = int(
        training_load.get(
            "hangboard_sessions_7d",
            training_load.get(
                "hangboard_sessions",
                0
            )
        ) or 0
    )


    # =========================
    # 3. 距最近一次指力板时间
    # =========================

    days_since = training_load.get(
        "days_since_hangboard"
    )


    if days_since is not None:

        try:
            days_since = int(days_since)

        except Exception:
            days_since = None


    # =========================
    # 4. 最近一次恢复评分
    # =========================

    recovery_after = training_load.get(
        "latest_recovery_after"
    )


    if recovery_after is not None:

        try:
            recovery_after = float(
                recovery_after
            )

        except Exception:
            recovery_after = None


    # =========================
    # 5. 最近7天平均疲劳
    # 仅用于背景，不当作当前疲劳
    # =========================

    avg_finger_7d = float(
        training_load.get(
            "avg_finger_fatigue_7d",
            0
        ) or 0
    )


    avg_elbow_7d = float(
        training_load.get(
            "avg_elbow_fatigue_7d",
            0
        ) or 0
    )


    risk = "正常"

    advice = []


    # =========================
    # 6. 手指当前局部疲劳
    # =========================

    if finger >= 7:

        risk = "手指专项疲劳较高"

        advice.append(
            "避免 Max Hang 和高强度 Repeaters"
        )

        advice.append(
            "避免极限抱石和高负荷抓握"
        )


    elif finger >= 5:

        risk = "手指局部疲劳需要关注"

        advice.append(
            "今天不建议最大力量指力训练"
        )

        advice.append(
            "攀岩以技术或中低强度为主"
        )


    # =========================
    # 7. 肘部疲劳
    # =========================

    if elbow >= 6:

        risk = "肘部局部疲劳风险较高"

        advice.append(
            "降低拉力训练和高强度锁定动作"
        )


    elif elbow >= 4:

        if risk == "正常":
            risk = "肘部轻度疲劳"

        advice.append(
            "控制拉力训练量，观察肘部反应"
        )


    # =========================
    # 8. 指力板频率判断
    # 频率高 ≠ 当前一定疲劳
    # =========================

    if hang_sessions >= 4:

        if days_since is not None and days_since <= 1:

            advice.append(
                "最近7天指力板频率较高，且最近一次训练距今不足48小时"
            )

        else:

            advice.append(
                "最近7天指力板频率较高，但需结合当前手指状态判断"
            )


    elif hang_sessions == 3:

        advice.append(
            "最近7天指力板训练频率偏高，今天不建议额外叠加高强度指力训练"
        )


    # =========================
    # 9. 距最近一次训练时间修正
    # =========================

    if days_since is not None:

        if days_since == 0:

            advice.append(
                "今天已有指力板负荷，不建议再次安排高强度指力训练"
            )


        elif days_since == 1:

            if finger >= 5:

                advice.append(
                    "距上次指力板仅1天且手指疲劳仍存在，建议继续恢复"
                )


        elif days_since >= 3:

            if (
                finger < 5
                and elbow < 4
            ):

                advice.append(
                    "距最近一次指力板已至少3天，若热身后无不适，可重新评估指力训练"
                )


    # =========================
    # 10. 恢复后评分修正
    # =========================

    if recovery_after is not None:

        if recovery_after < 60:

            if risk == "正常":
                risk = "最近一次指力训练恢复不足"

            advice.append(
                "最近一次指力训练恢复评分偏低，建议延长恢复"
            )


        elif recovery_after >= 80:

            if (
                finger < 5
                and elbow < 4
                and days_since is not None
                and days_since >= 2
            ):

                advice.append(
                    "最近一次训练后恢复良好，可根据热身状态决定是否恢复指力训练"
                )


    # =========================
    # 11. 默认建议
    # =========================

    if not advice:

        advice.append(
            "近期局部疲劳信号不明显，可以正常技术训练"
        )


    return {

        "fatigue_level":
        risk,


        "recommendations":
        advice,


        # 提供给AI解释，不把7天平均当当前疲劳
        "latest_finger_fatigue":
        finger,


        "latest_elbow_fatigue":
        elbow,


        "hangboard_sessions_7d":
        hang_sessions,


        "days_since_hangboard":
        days_since,


        "latest_recovery_after":
        recovery_after,


        "avg_finger_fatigue_7d":
        avg_finger_7d,


        "avg_elbow_fatigue_7d":
        avg_elbow_7d

    }


# ==============================
# AI 教练总结
# ==============================

def generate_ai_summary(ai_prompt):

    import json


    try:

        response = client.chat.completions.create(

            model="deepseek-chat",

            messages=[

                {
                    "role": "system",
                    "content": """

你是一名 WHOOP 风格私人健康教练。

你的任务：
根据用户提供的 WHOOP 数据、训练记录、睡眠、恢复、经期、体温、伤病信息，
生成简洁、专业、可执行的私人教练建议。


重要规则：

1. 只能使用提供的数据。
2. 不允许编造不存在的信息。
3. 数据缺失必须说明“数据缺失，无法判断”。
4. 不做医学诊断。
5. 使用谨慎表达，例如：
   “可能”
   “建议关注”
   “建议调整”。


你的分析必须包含：


🟡 今日教练总结

总结今天身体状态。
告诉用户今天最重要的一件事。


🧠 今日身体状态

结合 Recovery、HRV、静息心率、
近期趋势判断身体状态。


❤️ 恢复分析

分析：
Recovery
HRV
静息心率

解释身体信号。


😴 睡眠分析

分析：
睡眠时间
睡眠效率
深睡
REM

给出睡眠改善建议。


🏋️ 今日训练建议

必须包含：

推荐：
今天适合进行的训练。

避免：
今天不建议进行的训练。

训练负荷：

当前 Strain：
目标 Strain：
训练完成度：
剩余建议负荷：
疲劳趋势：


📈 明日恢复预测

预测未来趋势。

说明如果今晚恢复良好，
明天可能出现什么变化。



语言要求：

- 中文简体
- 使用emoji
- 第二人称“你”
- 像私人WHOOP Coach
- 不像医学报告
- 不输出代码
- 不使用Markdown
- 总长度500字以内



==============================
最终输出格式
==============================


必须只输出JSON。

禁止输出JSON以外任何内容。


严格返回：

{
  "ai_report": "",
  "training_advice": "",
  "risk_warning": ""
}


字段说明：


ai_report：

填写完整WHOOP教练报告。

必须包含：

🟡 今日教练总结
🧠 今日身体状态
❤️ 恢复分析
😴 睡眠分析
🏋️ 今日训练建议
📈 明日恢复预测


training_advice：

只填写行动建议。

必须包含：

推荐训练：
避免训练：
当前 Strain：
目标 Strain：
训练完成度：
剩余建议负荷：


risk_warning：

填写风险提醒。

例如：

恢复不足
疲劳累积
睡眠不足
手指疲劳
肘部风险

如果没有明显风险：

填写：

暂无明显风险

"""

                },


                {
                    "role": "user",
                    "content": json.dumps(
                        ai_prompt,
                        ensure_ascii=False
                    )
                }

            ],

            temperature=0.4,

            max_tokens=900

        )


        content = response.choices[0].message.content


        print(
            "DEBUG AI RAW:",
            repr(content)
        )


        # 去除markdown代码块

        content = content.strip()


        if content.startswith("```"):

            content = content.replace(
                "```json",
                ""
            )

            content = content.replace(
                "```",
                ""
            )

            content = content.strip()



        try:

            result = json.loads(
                content
            )


            return result



        except Exception as e:


            print(
                "JSON LOAD ERROR:",
                e
            )


            return {

                "ai_report": content,

                "training_advice": "",

                "risk_warning": ""

            }



    except Exception as e:


        print(
            "AI SUMMARY ERROR:",
            e
        )


        return {

            "ai_report":
            "⚠️ AI教练暂时无法生成建议",

            "training_advice":
            "",

            "risk_warning":
            ""

        }



def calculate_training_load():

    conn = get_db_connection()

    cursor = conn.cursor(
        cursor_factory=RealDictCursor
    )


    # =========================
    # 最近7天指力板负荷
    # =========================

    cursor.execute("""
        SELECT
            COUNT(*) AS sessions,

            COALESCE(
                SUM(duration),
                0
            ) AS total_duration,

            COALESCE(
                SUM(total_hang_time),
                0
            ) AS total_hang_time,

            COALESCE(
                AVG(finger_fatigue),
                0
            ) AS avg_fatigue,

            COALESCE(
                AVG(elbow_fatigue),
                0
            ) AS avg_elbow_fatigue

        FROM hangboard_training_log

        WHERE training_date::date
        >= CURRENT_DATE - INTERVAL '7 days'
    """)

    hangboard = cursor.fetchone()


    if hangboard is None:

        hangboard = {
            "sessions": 0,
            "total_duration": 0,
            "total_hang_time": 0,
            "avg_fatigue": 0,
            "avg_elbow_fatigue": 0
        }

    elif not isinstance(hangboard, dict):

        hangboard = dict(hangboard)


    # =========================
    # 最近一次指力板训练
    # =========================

    cursor.execute("""
        SELECT
            training_date,
            protocol,
            session_type,
            finger_fatigue,
            elbow_fatigue,
            recovery_after

        FROM hangboard_training_log

        ORDER BY training_date::date DESC,
                 created_at DESC

        LIMIT 1
    """)

    latest_hangboard = cursor.fetchone()


    if latest_hangboard is None:

        latest_hangboard = {
            "training_date": None,
            "protocol": None,
            "session_type": None,
            "finger_fatigue": 0,
            "elbow_fatigue": 0,
            "recovery_after": None
        }

    elif not isinstance(latest_hangboard, dict):

        latest_hangboard = dict(
            latest_hangboard
        )


    # =========================
    # 距离最近一次训练天数
    # =========================

    days_since_hangboard = None

    latest_training_date = (
        latest_hangboard.get(
            "training_date"
        )
    )


    if latest_training_date:

        cursor.execute(
            """
            SELECT
                CURRENT_DATE
                - %s::date
                AS days_since
            """,
            (
                latest_training_date,
            )
        )

        days_row = cursor.fetchone()

        if days_row:

            days_since_hangboard = (
                days_row["days_since"]
            )


    # =========================
    # 最近7天攀岩负荷
    # =========================

    cursor.execute("""
        SELECT
            COUNT(*) AS sessions,

            COALESCE(
                SUM(duration),
                0
            ) AS total_duration

        FROM climbing_training_log

        WHERE training_date::date
        >= CURRENT_DATE - INTERVAL '7 days'
    """)

    climbing = cursor.fetchone()


    if climbing is None:

        climbing = {
            "sessions": 0,
            "total_duration": 0
        }

    elif not isinstance(climbing, dict):

        climbing = dict(
            climbing
        )


    print(
        "DEBUG HANGBOARD VALUE:",
        hangboard
    )

    print(
        "DEBUG LATEST HANGBOARD:",
        latest_hangboard
    )

    print(
        "DEBUG DAYS SINCE HANGBOARD:",
        days_since_hangboard
    )

    print(
        "DEBUG CLIMBING VALUE:",
        climbing
    )


    cursor.close()
    conn.close()


    return {

        # ======================
        # 最近7天指力板负荷
        # ======================

        "hangboard_sessions_7d":
            hangboard.get(
                "sessions",
                0
            ),

        "hangboard_duration_7d":
            hangboard.get(
                "total_duration",
                0
            ),

        "hang_time_7d":
            hangboard.get(
                "total_hang_time",
                0
            ),

        "avg_finger_fatigue_7d":
            float(
                hangboard.get(
                    "avg_fatigue",
                    0
                ) or 0
            ),

        "avg_elbow_fatigue_7d":
            float(
                hangboard.get(
                    "avg_elbow_fatigue",
                    0
                ) or 0
            ),


        # ======================
        # 最近一次指力板状态
        # ======================

        "latest_hangboard_date":
            latest_hangboard.get(
                "training_date"
            ),

        "latest_hangboard_protocol":
            latest_hangboard.get(
                "protocol"
            ),

        "latest_hangboard_session_type":
            latest_hangboard.get(
                "session_type"
            ),

        "latest_finger_fatigue":
            latest_hangboard.get(
                "finger_fatigue",
                0
            ) or 0,

        "latest_elbow_fatigue":
            latest_hangboard.get(
                "elbow_fatigue",
                0
            ) or 0,

        "latest_recovery_after":
            latest_hangboard.get(
                "recovery_after"
            ),

        "days_since_hangboard":
            days_since_hangboard,


        # ======================
        # 攀岩7天负荷
        # ======================

        "climbing_sessions_7d":
            climbing.get(
                "sessions",
                0
            ),

        "climbing_duration_7d":
            climbing.get(
                "total_duration",
                0
            ),


        # ======================
        # 旧字段兼容
        # ======================

        "hangboard_sessions":
            hangboard.get(
                "sessions",
                0
            ),

        "hangboard_duration":
            hangboard.get(
                "total_duration",
                0
            ),

        "finger_fatigue":
            latest_hangboard.get(
                "finger_fatigue",
                0
            ) or 0,

        "elbow_fatigue":
            latest_hangboard.get(
                "elbow_fatigue",
                0
            ) or 0,

        "climbing_sessions":
            climbing.get(
                "sessions",
                0
            ),

        "climbing_duration":
            climbing.get(
                "total_duration",
                0
            ),

        "weekly_total_duration":
            climbing.get(
                "total_duration",
                0
            ),

        "hard_session_count":
            hangboard.get(
                "sessions",
                0
            )
    }

def get_latest_menstrual_data():

    conn=get_db_connection()

    cur=conn.cursor(
        cursor_factory=RealDictCursor
    )


    cur.execute("""
        SELECT *
        FROM menstrual_cycle_log
        ORDER BY cycle_date DESC
        LIMIT 1
    """)


    data=cur.fetchone()

    print(
        "DEBUG DB MENSTRUAL ROW:",
        data
    )

    cur.close()
    conn.close()


    return data



def get_latest_temperature_data():

    conn=get_db_connection()

    cur=conn.cursor(
        cursor_factory=RealDictCursor
    )


    cur.execute("""
    SELECT 
        report_date,
        skin_temperature,
        temperature_deviation,
        temperature_status
    FROM daily_metrics
    ORDER BY report_date DESC
    LIMIT 1
    """)


    data=cur.fetchone()


    cur.close()
    conn.close()


    return data



def get_latest_injury_data():

    conn=get_db_connection()

    cur=conn.cursor(
        cursor_factory=RealDictCursor
    )


    cur.execute("""
    SELECT *
    FROM injury_log
    ORDER BY injury_date DESC
    LIMIT 3
    """)


    data=cur.fetchall()


    cur.close()
    conn.close()


    return data



def save_daily_coach_report(
    metrics,
    training_load,
    ai_report,
    menstrual_data,
    temperature_data,
    injury_data,
    training_advice,
    risk_warning
):

    conn = None
    cursor = None


    try:


        conn = get_db_connection()

        cursor = conn.cursor()



        report_date = datetime.now().strftime(
            "%Y-%m-%d"
        )


        # 防止 None

        ai_report = ai_report or ""

        training_advice = training_advice or ""

        risk_warning = risk_warning or ""



        print(
            "SAVE DATE:",
            report_date
        )


        print(
            "SAVE AI LENGTH:",
            len(ai_report)
        )


        print(
            "SAVE TRAINING ADVICE:",
            training_advice
        )


        print(
            "SAVE RISK WARNING:",
            risk_warning
        )



        cursor.execute(
            """

            INSERT INTO daily_coach_reports

            (
                report_date,

                recovery,

                whoop_strain,

                climbing_load,

                hangboard_load,

                fatigue_score,

                training_advice,

                risk_warning,

                ai_report,

                menstrual_data,

                temperature_data,

                injury_data
            )


            VALUES

            (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s
            )


            ON CONFLICT(report_date)

            DO UPDATE SET


                recovery =
                EXCLUDED.recovery,


                whoop_strain =
                EXCLUDED.whoop_strain,


                climbing_load =
                EXCLUDED.climbing_load,


                hangboard_load =
                EXCLUDED.hangboard_load,


                fatigue_score =
                EXCLUDED.fatigue_score,


                training_advice =
                EXCLUDED.training_advice,


                risk_warning =
                EXCLUDED.risk_warning,


                ai_report =
                EXCLUDED.ai_report,


                menstrual_data =
                EXCLUDED.menstrual_data,


                temperature_data =
                EXCLUDED.temperature_data,


                injury_data =
                EXCLUDED.injury_data

            """,

            (

                report_date,


                metrics.get(
                    "recovery_score",
                    0
                ),


                metrics.get(
                    "cycle_strain",
                    0
                ),


                training_load.get(
                    "climbing_duration",
                    0
                ),


                training_load.get(
                    "hangboard_duration",
                    0
                ),


                training_load.get(
                    "finger_fatigue",
                    0
                ),


                training_advice,


                risk_warning,


                ai_report,


                str(
                    menstrual_data
                ),


                str(
                    temperature_data
                ),


                str(
                    injury_data
                )

            )

        )


        conn.commit()


        print(
            "DAILY COACH REPORT SAVED"
        )



    except Exception as e:


        print(
            "SAVE DAILY COACH REPORT ERROR:",
            e
        )


        if conn:

            conn.rollback()



    finally:


        if cursor:

            cursor.close()


        if conn:

            conn.close()



def generate_coach_prompt(
    metrics,
    training_load,
    weekly,
    climbing_fatigue,
    menstrual_data,
    temperature_data,
    injury_data
):

    if not isinstance(metrics, dict):
        metrics = {}

    if not isinstance(training_load, dict):
        training_load = {}

    if not isinstance(weekly, dict):
        weekly = {}

    if not isinstance(climbing_fatigue, dict):
        climbing_fatigue = {}


    return f"""

你是一名专业的 WHOOP 攀岩训练教练。

请根据以下最新数据，制定今天的训练和恢复建议。

重要判断原则：

1. 不得只根据 Recovery 判断训练。
2. 最近7天训练频率较高，不等于今天一定存在疲劳累积。
3. 最近7天平均疲劳只是历史负荷背景，不能当作今天当前疲劳。
4. 判断手指和肘部风险时，优先参考：
   - 最近一次指力板训练的疲劳评分
   - 距离最近一次指力板训练的天数
   - 最近一次训练后的恢复评分
   - 最近7天指力板频率
   - 当前 WHOOP Recovery、HRV、睡眠和 Strain
   - 当前是否有伤病或不适记录
5. 不得仅因为最近7天指力板次数较多，就判断“过度使用”“恢复不足”或“必须完全休息”。
6. 如果没有当前疼痛、僵硬、肌腱敏感或功能受限记录，不要假设这些症状存在。
7. 如果最近一次训练已过去数天、局部疲劳较低、恢复评分良好，应相应降低局部风险判断。
8. 使用谨慎表达，不做医学诊断。

==============================
WHOOP 今日状态
==============================

Recovery:
{metrics.get("recovery_score", 0)}%

HRV:
{metrics.get("hrv", 0)} ms

静息心率:
{metrics.get("resting_heart_rate", 0)} bpm

睡眠:
{metrics.get("sleep_duration", 0)} 小时

睡眠评分:
{metrics.get("sleep_score", 0)}%

Strain:
{metrics.get("cycle_strain", 0)}


==============================
最近7天攀岩负荷
==============================

攀岩次数:
{training_load.get("climbing_sessions_7d",
training_load.get("climbing_sessions", 0))}

攀岩总时长:
{training_load.get("climbing_duration_7d",
training_load.get("climbing_duration", 0))} 分钟


==============================
最近7天指力板负荷
==============================

指力板次数:
{training_load.get("hangboard_sessions_7d",
training_load.get("hangboard_sessions", 0))}

指力板总时长:
{training_load.get("hangboard_duration_7d",
training_load.get("hangboard_duration", 0))} 分钟

总悬挂时间:
{training_load.get("hang_time_7d", 0)} 秒

最近7天平均手指疲劳:
{training_load.get("avg_finger_fatigue_7d", 0)}/10

最近7天平均肘部疲劳:
{training_load.get("avg_elbow_fatigue_7d", 0)}/10

注意：
以上两个“7天平均疲劳”只代表历史训练记录平均值，
不能直接解释为今天当前疲劳。


==============================
最近一次指力板训练
==============================

日期:
{training_load.get("latest_hangboard_date")}

训练协议:
{training_load.get("latest_hangboard_protocol")}

训练类型:
{training_load.get("latest_hangboard_session_type")}

最近一次手指疲劳:
{training_load.get("latest_finger_fatigue", 0)}/10

最近一次肘部疲劳:
{training_load.get("latest_elbow_fatigue", 0)}/10

训练后恢复评分:
{training_load.get("latest_recovery_after")}

距最近一次指力板训练:
{training_load.get("days_since_hangboard")} 天


==============================
攀岩专项疲劳分析
==============================

疲劳等级:
{climbing_fatigue.get("fatigue_level", "正常")}

建议:
{climbing_fatigue.get("recommendations", [])}


==============================
身体附加信息
==============================

经期状态:
{menstrual_data}

身体温度:
{temperature_data}

最近伤病记录:
{injury_data}


==============================
最近7天 WHOOP 趋势
==============================

平均 Recovery:
{weekly.get("avg_recovery", 0)}

平均 HRV:
{weekly.get("avg_hrv", 0)}

平均静息心率:
{weekly.get("avg_resting_hr", 0)}

平均睡眠:
{weekly.get("avg_sleep", 0)} 小时


==============================
输出要求
==============================

请结合所有数据判断：

1. 今日训练等级
2. 推荐训练类型
3. 是否需要恢复
4. 手指和肘部风险
5. 是否适合 Max Hang / Repeaters / 技术攀岩 / 极限抱石
6. 明日训练条件

风险判断要求：

- 如果只是“最近7天频率较高”，但最近一次局部疲劳较低、已经休息数天、恢复评分良好，不要直接判断过度使用。
- 如果最近一次手指疲劳 >= 7，或肘部疲劳 >= 6，或训练间隔很短且疲劳仍高，应明显降低指力训练强度。
- 如果没有明确疼痛或伤病记录，不要写“酸痛”“肌腱敏感”等未提供症状。
- “恢复不足”必须有 Recovery、HRV、睡眠、训练间隔或 recovery_after 的数据依据。

使用中文。
"""
    

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

🟢【今日状态】

❤️【Recovery分析】

😴【睡眠分析】

🔥【训练睡眠分析】

🩸【经期状态】

🌡️【身体温度】

🩹【伤病风险】

⚠️【疲劳风险】

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


==============================
强制局部疲劳判定规则
==============================

以下规则优先级高于其他训练风险判断。

【手指疲劳 0-3/10】
属于低疲劳。
没有明确疼痛或伤病记录时，不得判断为恢复不足、疲劳累积或过度使用。

【手指疲劳 4-6/10】
属于中等局部疲劳。

必须使用：
“中等局部疲劳”
“建议关注恢复”
“建议控制高强度手指刺激”

不得使用：
“疲劳累积”
“恢复不足”
“过度使用”
“高风险”
“肌腱损伤风险”

即使距离上次指力板训练只有1天，
只要疲劳评分没有达到7/10，
且没有明确疼痛、伤病、动作受限记录，
也不得判断为“疲劳累积”或“恢复不足”。

如果距离上次指力板训练不足48小时，
可以建议：
“今天控制或避免 Max Hang、极限抱石等高强度手指刺激。”

但不能因此要求完全停止攀岩。

【手指疲劳 7-8/10】
属于明显局部疲劳。
可以判断需要降低指力训练负荷，
建议避免 Max Hang 和极限抱石。

【手指疲劳 9-10/10】
属于高局部疲劳。
建议暂停高强度手指训练并优先恢复。


==============================
“疲劳累积”使用条件
==============================

只有存在明确证据时才能使用“疲劳累积”。

至少满足以下之一：

1. 连续多次手指疲劳评分 >= 7；
2. 最近一次手指疲劳 >= 7；
3. recovery_after 明显偏低；
4. 存在明确疼痛、僵硬、肌腱敏感或动作受限记录；
5. 多个恢复指标连续恶化，并同时存在较高局部疲劳。

仅仅因为：
- 最近7天指力板次数较多；
- 距上次训练1天；
- 手指疲劳4-6/10；

不得判断为“疲劳累积”。


==============================
“恢复不足”使用条件
==============================

只有存在明确恢复证据时才能使用“恢复不足”。

例如：
- Recovery明显偏低；
- HRV明显低于个人基线；
- 睡眠明显不足；
- recovery_after明显偏低；
- 或上述多个指标同时异常。

手指疲劳4-6/10本身不能证明全身恢复不足。


==============================
禁止推测症状
==============================

如果数据没有明确记录：

疼痛
酸痛
僵硬
肌腱敏感
动作受限

禁止自行推测这些症状存在。


风险表达规则：

- 使用“可能”“建议关注”等谨慎表达。
- 不得诊断疾病。
- 不得声称一定会受伤或生病。
- 如出现持续异常，建议咨询医疗专业人员。


额外分析：

如果存在：

- 经期阶段影响
- 体温异常变化
- 疼痛记录
- 动作限制

请分析：

🩸 生理状态影响
🌡️ 身体恢复信号
🩹 伤病风险

给出训练调整建议。

不要医学诊断。


输出要求：

- 中文简体
- 使用emoji
- 500字以内
- 不输出代码
- 不使用Markdown表格
- 像谨慎、专业的WHOOP私人教练

==============================
最终输出格式
==============================

必须只输出JSON。

禁止输出JSON以外任何文字。

格式：

{
 "weekly_report":"完整7天趋势分析",
 "weekly_training_advice":"未来7天训练建议",
 "weekly_risk_warning":"未来7天风险提醒"
}

要求：

weekly_report:
包含：
🟢【今日状态】
❤️【Recovery分析】
😴【睡眠分析】
🔥【训练睡眠分析】
🩸【经期状态】
🌡️【身体温度】
🩹【伤病风险】
⚠️【疲劳风险】
📅【未来7天建议】

weekly_training_advice:
填写未来训练行动建议。

weekly_risk_warning:
填写需要关注的问题。
如果没有：
填写“暂无明显风险”。
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

        content = response.choices[0].message.content

        print(
            "DEBUG AI RAW:",
            repr(content)
        )

        return content
 

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

        print(
            "WEEKLY DATA:",
            rows
        )


        # =========================
        # 没有数据
        # =========================

        if not rows:

            return {
                "success": False,
                "valid_days": 0,
                "is_complete": False,
                "start_date": None,
                "end_date": None,
                "avg_recovery": 0,
                "avg_hrv": 0,
                "avg_resting_hr": 0,
                "avg_sleep": 0,
                "avg_sleep_score": 0,
                "avg_strain": 0,
                "records": [],
                "prompt_text": "暂无 WHOOP 历史数据"
            }


        # 数据库是 DESC
        # 转换成日期正序

        rows = list(
            reversed(rows)
        )


        # =========================
        # 工具函数
        # =========================

        def safe_float(value):

            if value is None:
                return None

            try:
                return float(value)

            except Exception:
                return None


        def safe_avg(values):

            valid = [
                safe_float(v)
                for v in values
                if safe_float(v) is not None
            ]

            if not valid:
                return 0

            return round(
                sum(valid) / len(valid),
                2
            )


        def show_value(
            value,
            suffix=""
        ):

            if value is None:
                return "数据缺失"

            return f"{value}{suffix}"


        # =========================
        # 整理每天数据
        # =========================

        records = []

        data_lines = []


        for row in rows:

            (
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                sleep_score,
                cycle_strain
            ) = row


            record = {

                "report_date":
                    str(report_date),

                "recovery_score":
                    safe_float(recovery_score),

                "hrv":
                    safe_float(hrv),

                "resting_heart_rate":
                    safe_float(resting_heart_rate),

                "sleep_duration":
                    safe_float(sleep_duration),

                "sleep_score":
                    safe_float(sleep_score),

                "cycle_strain":
                    safe_float(cycle_strain)

            }


            records.append(
                record
            )


            data_lines.append(
                f"""
日期：{report_date}
Recovery：{show_value(recovery_score, "%")}
HRV：{show_value(hrv, " ms")}
静息心率：{show_value(resting_heart_rate, " bpm")}
睡眠时长：{show_value(sleep_duration, " 小时")}
睡眠评分：{show_value(sleep_score, " 分")}
Strain：{show_value(cycle_strain)}
""".strip()
            )


        # =========================
        # 周期信息
        # =========================

        valid_days = len(records)

        start_date = records[0][
            "report_date"
        ]

        end_date = records[-1][
            "report_date"
        ]


        # =========================
        # 平均数据
        # =========================

        avg_recovery = safe_avg([
            r["recovery_score"]
            for r in records
        ])


        avg_hrv = safe_avg([
            r["hrv"]
            for r in records
        ])


        avg_resting_hr = safe_avg([
            r["resting_heart_rate"]
            for r in records
        ])


        avg_sleep = safe_avg([
            r["sleep_duration"]
            for r in records
        ])


        avg_sleep_score = safe_avg([
            r["sleep_score"]
            for r in records
        ])


        avg_strain = safe_avg([
            r["cycle_strain"]
            for r in records
        ])


        # =========================
        # 给 Weekly AI 的数据文本
        # =========================

        weekly_data_text = "\n\n".join(
            data_lines
        )


        prompt_text = f"""
统计周期：{start_date} 至 {end_date}

有效记录：
{valid_days}/7天

数据完整性：
{"完整7天数据" if valid_days >= 7 else "不足7天，仅代表阶段性趋势"}

以下是按日期正序排列的 WHOOP 数据：

{weekly_data_text}


最近阶段平均值：

平均 Recovery：
{avg_recovery}%

平均 HRV：
{avg_hrv} ms

平均静息心率：
{avg_resting_hr} bpm

平均睡眠：
{avg_sleep} 小时

平均睡眠评分：
{avg_sleep_score}

平均 Strain：
{avg_strain}


分析要求：

1. 只能根据以上实际数据分析。

2. 如果不足7天，
必须明确说明这是阶段性趋势。

3. 不得推测缺失日期的数据。

4. 不得把没有训练记录解释为休息日。

5. Recovery 必须结合 HRV、
静息心率和睡眠判断。

6. Strain 必须结合 Recovery
和睡眠判断是否匹配。

7. 单日变化不能直接定义为
长期疲劳或恢复异常。

8. 必须区分：
短期波动
和
连续趋势。

9. 未来训练建议必须采用条件式建议，
不得提前假设未来 Recovery。

10. 不进行医学诊断。
"""


        # =========================
        # 返回统一 dict
        # =========================

        return {

            "success": True,

            "valid_days":
                valid_days,

            "is_complete":
                valid_days >= 7,

            "start_date":
                start_date,

            "end_date":
                end_date,

            "avg_recovery":
                avg_recovery,

            "avg_hrv":
                avg_hrv,

            "avg_resting_hr":
                avg_resting_hr,

            "avg_sleep":
                avg_sleep,

            "avg_sleep_score":
                avg_sleep_score,

            "avg_strain":
                avg_strain,

            "records":
                records,

            "prompt_text":
                prompt_text

        }


    except Exception as e:

        print(
            "WEEKLY ANALYSIS ERROR:",
            e
        )

        return {

            "success": False,

            "valid_days": 0,

            "is_complete": False,

            "start_date": None,

            "end_date": None,

            "avg_recovery": 0,

            "avg_hrv": 0,

            "avg_resting_hr": 0,

            "avg_sleep": 0,

            "avg_sleep_score": 0,

            "avg_strain": 0,

            "records": [],

            "prompt_text": "",

            "error": str(e)

        }


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

    if key and key.startswith("Bearer "):
        key = key.replace("Bearer ", "")

    api_secret = os.getenv(
        "CHATGPT_ACTION_API_KEY"
    )

    print(
        "HEADER START:",
        key[:5] if key else None
    )

    print(
        "ENV START:",
        api_secret[:5] if api_secret else None
    )

    print(
        "COMPARE:",
        key == api_secret
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

        print(
            "SLEEP SCORE RAW:",
            sleep_score_data
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


def save_hangboard_training(data):

    conn = get_db_connection()

    cursor = conn.cursor()


    cursor.execute("""
    INSERT INTO hangboard_training_log (

        training_date,
        protocol,
        session_type,
        edge_size,
        grip_type,
        added_weight,
        hold_seconds,
        duration,
        sets,
        total_hang_time,
        intensity,
        finger_fatigue,
        elbow_fatigue,
        recovery_after,
        notes

    )

    VALUES (

        %s,%s,%s,%s,%s,
        %s,%s,%s,%s,%s,
        %s,%s,%s,%s,%s

    )

    """,

    (

        data.get("training_date"),
        data.get("protocol"),
        data.get("session_type"),
        data.get("edge_size"),
        data.get("grip_type"),
        data.get("added_weight"),
        data.get("hold_seconds"),
        data.get("duration"),
        data.get("sets"),
        data.get("total_hang_time"),
        data.get("intensity"),
        data.get("finger_fatigue"),
        data.get("elbow_fatigue"),
        data.get("recovery_after"),
        data.get("notes")
    )
    )


    conn.commit()

    cursor.close()

    conn.close()


    return True
    

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


    # =========================
    # 额外健康数据
    # =========================

    menstrual_data = data.get(
        "menstrual_data",
        None
    )


    temperature_data = data.get(
        "temperature_data",
        None
    )


    injury_data = data.get(
        "injury_data",
        []
    )

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

        "training_advice": training_advice,

        "menstrual_data": menstrual_data,

        "temperature_data": temperature_data,

        "injury_data": injury_data

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

训练负荷分析：

当前 Strain:
{current_strain}

目标 Strain:
{target_min}
        
训练完成度:
{strain_completion}%

剩余建议负荷:
{remaining_strain}

疲劳趋势:
{fatigue_warning}


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


🧗🏻‍♀️ 攀岩专项训练判断：

1. 攀岩训练不能只根据WHOOP Recovery判断。
2. 必须结合手指疲劳、肘部疲劳、指力板训练历史。
3. Max Hang属于高强度力量训练，需要更长恢复时间。
4. 如果手指疲劳较高，即使Recovery正常，也降低最大力量训练。
5. 优先保护手指肌腱和肘部健康。
6. 如果Recovery正常，但最近7天存在高强度指力板训练：
   优先安排技术攀岩、线路熟悉、低强度训练。
7. 如果手指疲劳 >=7/10：
   禁止Max Hang、极限抱石、极限项目冲刺。
8. 如果肘部疲劳 >=6/10：
   降低大幅度拉力动作和高强度抱石。
9. 攀岩训练建议优先级：
   技术训练 > 容量训练 > 力量训练 > 极限训练。



⚠️ 【未来3天行动计划】

未来训练安排必须考虑：
1. WHOOP恢复状态
2. 最近7天训练负荷
3. 手指疲劳趋势
4. 肘部疲劳趋势

第1天：
训练建议

第2天：
恢复建议

第3天：
训练调整建议



训练建议部分必须明确包含以下内容：

1. 当前 Strain 和目标 Strain
2. 已完成训练比例（百分比）
3. 剩余建议训练负荷
4. 疲劳趋势判断

不要只描述训练建议，必须引用上述指标。


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

    print(
        "DEBUG RAW AI:",
        repr(coach_advice)
    )

    import json

    try:

        raw = coach_advice.strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()


        coach_json = json.loads(raw)


        ai_report = coach_json.get(
            "ai_report",
            ""
        )

        training_advice = coach_json.get(
            "training_advice",
            ""
        )

        risk_warning = coach_json.get(
            "risk_warning",
            ""
        )


    except Exception as e:

        print(
            "JSON PARSE ERROR:",
            e
        )

        ai_report = coach_advice
        training_advice = ""
        risk_warning = ""

 
    ai_report = ai_report[:4000]

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


    print("ENTER AUTO REPORT FUNCTION")
    
    if not check_api_key():

        print("API KEY FAILED")

        return jsonify({

            "error":
            "unauthorized"

        }),401

    print("API KEY PASSED")


    try:

        print("TRY BLOCK ENTERED")

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
        # 5. 准备数据
        # =========================

   
        metrics = extract_daily_metrics(data)

        weekly_data = generate_weekly_analysis()

        training_load = calculate_training_load()

        climbing_fatigue = analyze_climbing_fatigue(training_load)

        menstrual_data = get_latest_menstrual_data()

        temperature_data = get_latest_temperature_data()

        injury_data = get_latest_injury_data()

        data["menstrual_data"] = menstrual_data

        data["temperature_data"] = temperature_data

        data["injury_data"] = injury_data


        # =========================
        # 6. 生成基础报告
        # =========================

        report = generate_ai_summary(data)


        # =========================
        # 7. AI健康教练
        # =========================


        print(
            "DEBUG CLIMBING FATIGUE:",
            climbing_fatigue
        )

        print(
            "DEBUG MENSTRUAL:",
            menstrual_data
        )

        print(
            "DEBUG TEMPERATURE:",
            temperature_data
        )

        print(
            "DEBUG INJURY:",
            injury_data
        )

        print(
            "DEBUG DATA EXISTS:",
            type(data)
        )

        ai_prompt = generate_coach_prompt(
            metrics,
            training_load,
            weekly_data,
            climbing_fatigue,
            menstrual_data,
            temperature_data,
            injury_data
        )

        print(
            "DEBUG PROMPT READY"
        )

        print(
            "DEBUG PROMPT TYPE:",
            type(ai_prompt)
        )

        ai_result = generate_ai_summary(
            ai_prompt
        )

        print(
            "DEBUG RAW AI:",
            repr(ai_result)
        )


        import json

        # 默认值
        ai_report = ""
        training_advice = ""
        risk_warning = ""

        try:

            # =====================
            # AI返回dict
            # =====================

            if isinstance(ai_result, dict):

                coach_json = ai_result


            # =====================
            # AI返回字符串
            # =====================

            else:

                raw = str(ai_result).strip()

                # 去除markdown代码块

                if raw.startswith("```"):

                    raw = raw.replace(
                        "```json",
                        ""
                    )

                    raw = raw.replace(
                        "```",
                        ""
                    )

                    raw = raw.strip()

                coach_json = json.loads(
                    raw
                )

            ai_report = coach_json.get(
                "ai_report",
                ""
            )

            training_advice = coach_json.get(
                "training_advice",
                ""
            )

            risk_warning = coach_json.get(
                "risk_warning",
                ""
            )


        except Exception as e:

            print(
                "JSON PARSE ERROR:",
                e
            )

            print(
                "FAILED AI:",
                repr(ai_result)
            )

            # 如果AI不是JSON
            # 整体作为报告保存

            ai_report = str(ai_result)


        print(
            "SAVE AI REPORT LENGTH:",
            len(ai_report)
        )

        print(
            "SAVE TRAINING ADVICE:",
            training_advice
        )

        print(
            "SAVE RISK WARNING:",
            risk_warning
        )

        save_daily_coach_report(

            metrics,

            training_load,

            ai_report,

            menstrual_data,

            temperature_data,

            injury_data,

            training_advice,

            risk_warning

        )

        print(
            "AI COACH GENERATED"
        )

        print(
            "========== DAILY REPORT SUCCESS =========="
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
            ai_report,


            "training_advice":
            training_advice,


            "risk_warning":
            risk_warning,


            "metrics":
            metrics,

            "menstrual":
            menstrual_data,

            "temperature":
            temperature_data,

            "injury":
            injury_data

        })


    except Exception as e:


        import traceback
        
        print(
            "AUTO REPORT ERROR:",
            e
        )

        traceback.print_exc()

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


def get_weekly_trend():

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
        return {}


    rows = list(reversed(rows))


    recovery_values = []
    hrv_values = []
    resting_hr_values = []
    sleep_values = []


    for r in rows:

        if r[1] is not None:
            recovery_values.append(float(r[1]))

        if r[2] is not None:
            hrv_values.append(float(r[2]))

        if r[3] is not None:
            resting_hr_values.append(float(r[3]))

        if r[4] is not None:
            sleep_values.append(float(r[4]))



    def avg(values):

        if not values:
            return 0

        return round(
            sum(values)/len(values),
            2
        )


    return {

        "days": len(rows),

        "avg_recovery":
            avg(recovery_values),

        "avg_hrv":
            avg(hrv_values),

        "avg_resting_hr":
            avg(resting_hr_values),

        "avg_sleep":
            avg(sleep_values),

    }




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
