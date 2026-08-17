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
总长度控制在800字以内。
weekly_report 控制在500字以内。
weekly_training_advice 控制在180字以内。
weekly_risk_warning 控制在120字以内。

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

    import html
    import re

    if not report:
        return "暂无 AI 健康分析"


    # =========================
    # Weekly AI 当前正式标题
    # =========================

    sections = {

        "🟢【今日状态】":
            "ai-green",

        "❤️【Recovery分析】":
            "ai-heart",

        "😴【睡眠分析】":
            "ai-sleep",

        "🔥【训练与负荷分析】":
            "ai-fire",

        "🩸【经期状态】":
            "ai-period",

        "🌡️【身体温度】":
            "ai-temperature",

        "🩹【伤病风险】":
            "ai-injury",

        "⚠️【疲劳风险】":
            "ai-warning",

        "📅【未来7天建议】":
            "ai-plan"
    }


    # =========================
    # 兼容旧标题
    # =========================

    aliases = {

        "🟢【恢复趋势】":
            "🟢【今日状态】",

        "❤️【HRV趋势】":
            "❤️【Recovery分析】",

        "😴【睡眠趋势】":
            "😴【睡眠分析】",

        "🔥【训练负荷】":
            "🔥【训练与负荷分析】",

        "🔥【训练睡眠分析】":
            "🔥【训练与负荷分析】",

        "⚠️【风险提醒】":
            "⚠️【疲劳风险】"
    }


    # =========================
    # 清理 AI Markdown
    # =========================

    report = str(report)

    report = report.replace(
        "**",
        ""
    )

    report = report.replace(
        "```",
        ""
    )


    # 删除过多空行
    report = re.sub(
        r'\n\s*\n+',
        '\n',
        report
    )


    lines = [
        line.strip()
        for line in report.splitlines()
        if line.strip()
    ]


    html_parts = []

    current_content = []

    current_title = None

    current_css = None


    # =========================
    # 输出一个完整 section
    # =========================

    def flush_section():

        nonlocal current_content
        nonlocal current_title
        nonlocal current_css


        if current_title is None:

            return


        content_html = "".join(
            f"""
            <div class="ai-item-content">
                {html.escape(text)}
            </div>
            """
            for text in current_content
        )


        html_parts.append(
            f"""
            <div class="ai-item">

                <div class="ai-item-title {current_css}">
                    {html.escape(current_title)}
                </div>

                <div class="ai-section-content">
                    {content_html}
                </div>

            </div>
            """
        )


        current_content = []


    # =========================
    # 逐行解析
    # =========================

    for line in lines:

        matched_title = None

        display_title = None

        css_class = None


        # 正式标题
        for title, css in sections.items():

            if line.startswith(title):

                matched_title = title
                display_title = title
                css_class = css
                break


        # 兼容旧标题
        if matched_title is None:

            for old_title, new_title in aliases.items():

                if line.startswith(old_title):

                    matched_title = old_title
                    display_title = new_title
                    css_class = sections[
                        new_title
                    ]
                    break


        # =========================
        # 找到新标题
        # =========================

        if matched_title:

            flush_section()


            current_title = (
                display_title
            )

            current_css = (
                css_class
            )

            current_content = []


            # 标题同行后面的正文
            remaining_text = (
                line[
                    len(matched_title):
                ].strip()
            )


            if remaining_text:

                current_content.append(
                    remaining_text
                )


        # =========================
        # 普通正文
        # =========================

        else:

            # 如果 AI 开头没有标题
            if current_title is None:

                current_title = (
                    "📊 周期分析"
                )

                current_css = (
                    "ai-default"
                )


            current_content.append(
                line
            )


    # 最后一段
    flush_section()


    return "".join(
        html_parts
    )


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
            

@app.route(
    "/api/whoop/coach-report",
    methods=["GET"]
)
def get_whoop_coach_report():

    import json

    conn = None
    cur = None


    try:

        conn = get_db_connection()
        cur = conn.cursor()


        # =========================
        # 1. 获取今日 WHOOP 数据
        # =========================

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
                skin_temperature,
                spo2_percentage

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 1
            """
        )


        today_row = cur.fetchone()


        if not today_row:

            return jsonify({

                "success": False,

                "error":
                    "暂无 WHOOP 每日数据"

            }), 404


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
            skin_temperature,
            spo2_percentage

        ) = today_row


        # =========================
        # 2. 最近7天 WHOOP
        # =========================

        cur.execute(
            """
            SELECT
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                cycle_strain,
                skin_temperature,
                spo2_percentage

            FROM daily_metrics

            ORDER BY report_date DESC

            LIMIT 7
            """
        )


        weekly_rows = cur.fetchall()


        # =========================
        # 3. 安全平均
        # =========================

        def safe_avg(values):

            valid = []

            for value in values:

                if value is None:
                    continue

                try:

                    valid.append(
                        float(value)
                    )

                except Exception:

                    continue


            if not valid:

                return None


            return round(
                sum(valid)
                / len(valid),
                2
            )


        recovery_avg = safe_avg([
            row[0]
            for row in weekly_rows
        ])


        hrv_avg = safe_avg([
            row[1]
            for row in weekly_rows
        ])


        rhr_avg = safe_avg([
            row[2]
            for row in weekly_rows
        ])


        sleep_avg = safe_avg([
            row[3]
            for row in weekly_rows
        ])


        strain_avg = safe_avg([
            row[4]
            for row in weekly_rows
        ])


        skin_temperature_avg = safe_avg([
            row[5]
            for row in weekly_rows
        ])


        spo2_avg = safe_avg([
            row[6]
            for row in weekly_rows
        ])


        skin_temperature_valid_days = sum(
            1
            for row in weekly_rows
            if row[5] is not None
        )


        spo2_valid_days = sum(
            1
            for row in weekly_rows
            if row[6] is not None
        )


        # =========================
        # 4. 温度 / SpO₂ 偏差
        # =========================

        temperature_deviation = None


        if (
            skin_temperature is not None
            and skin_temperature_avg is not None
            and skin_temperature_valid_days >= 3
        ):

            temperature_deviation = round(
                float(skin_temperature)
                - float(skin_temperature_avg),
                2
            )


        spo2_deviation = None


        if (
            spo2_percentage is not None
            and spo2_avg is not None
            and spo2_valid_days >= 3
        ):

            spo2_deviation = round(
                float(spo2_percentage)
                - float(spo2_avg),
                2
            )


        # =========================
        # 5. 睡眠结构比例
        # =========================

        deep_sleep_ratio = None
        rem_sleep_ratio = None
        light_sleep_ratio = None


        if (
            sleep_duration is not None
            and float(sleep_duration) > 0
        ):

            if deep_sleep_duration is not None:

                deep_sleep_ratio = round(
                    float(deep_sleep_duration)
                    / float(sleep_duration)
                    * 100,
                    1
                )


            if rem_sleep_duration is not None:

                rem_sleep_ratio = round(
                    float(rem_sleep_duration)
                    / float(sleep_duration)
                    * 100,
                    1
                )


            if (
                deep_sleep_ratio is not None
                and rem_sleep_ratio is not None
            ):

                light_sleep_ratio = round(
                    max(
                        0,
                        100
                        - deep_sleep_ratio
                        - rem_sleep_ratio
                    ),
                    1
                )


        # =========================
        # 6. Recovery状态
        # =========================
        #
        # 注意：
        # 这里只负责 Recovery 颜色状态。
        #
        # training_level 不在这里计算。
        # training_level 统一来自 strain_plan。
        # =========================

        if recovery_score is None:

            recovery_status = (
                "数据缺失"
            )

            training_advice = (
                "Recovery数据缺失，"
                "暂无法判断整体训练准备度。"
            )


        elif float(recovery_score) >= 67:

            recovery_status = (
                "🟢 绿色 - 恢复良好"
            )

            training_advice = (
                "整体恢复条件较好，"
                "但最终训练强度仍需结合HRV、睡眠、"
                "训练负荷和局部疲劳判断。"
            )


        elif float(recovery_score) >= 34:

            recovery_status = (
                "🟡 黄色 - 需要控制训练"
            )

            training_advice = (
                "整体恢复处于黄色区间，"
                "训练建议结合Strain Plan、HRV、睡眠"
                "和局部手指状态执行。"
            )


        else:

            recovery_status = (
                "🔴 红色 - 优先恢复"
            )

            training_advice = (
                "整体恢复偏低，"
                "优先控制训练负荷并关注恢复。"
            )


        # =========================
        # 7. 基础疲劳趋势
        # =========================

        fatigue_warning = (
            "正常"
        )

        continuous_fatigue = False


        if (
            recovery_score is not None
            and recovery_avg is not None
            and hrv is not None
            and hrv_avg is not None
            and resting_heart_rate is not None
            and rhr_avg is not None
        ):

            if (
                float(recovery_score) < recovery_avg
                and float(hrv) < hrv_avg
                and float(resting_heart_rate) > rhr_avg
            ):

                fatigue_warning = (
                    "恢复压力升高，"
                    "建议关注近期恢复趋势"
                )


            elif (
                float(recovery_score) < recovery_avg
                and float(hrv) < hrv_avg
            ):

                fatigue_warning = (
                    "恢复指标下降，"
                    "建议关注训练负荷"
                )


            elif (
                recovery_avg > 0
                and float(recovery_score)
                < recovery_avg * 0.85
            ):

                fatigue_warning = (
                    "Recovery明显低于近期平均，"
                    "建议降低训练强度"
                )


        # =========================
        # 8. 读取保存的 Coach Report
        # =========================

        coach_report_text = ""

        training_recommendation = ""

        risk_warning = (
            "暂无明显风险"
        )

        menstrual_data = None

        saved_temperature_data = None

        injury_data = None


        max_hang_status = None

        max_hang_decision = None

        strain_plan = None

        training_readiness = None


        cur.execute(
            """
            SELECT
                ai_report,
                training_advice,
                risk_warning,
                menstrual_data,
                temperature_data,
                injury_data,
                max_hang_status,
                max_hang_decision,
                strain_plan,
                training_readiness

            FROM daily_coach_reports

            ORDER BY report_date DESC

            LIMIT 1
            """
        )


        coach_row = cur.fetchone()


        if coach_row:

            coach_report_text = (
                coach_row[0]
                or ""
            )


            training_recommendation = (
                coach_row[1]
                or ""
            )


            risk_warning = (
                coach_row[2]
                or "暂无明显风险"
            )


            menstrual_data = (
                coach_row[3]
            )


            saved_temperature_data = (
                coach_row[4]
            )


            injury_data = (
                coach_row[5]
            )


            max_hang_status = (
                coach_row[6]
                or None
            )


            max_hang_decision = (
                coach_row[7]
            )


            strain_plan = (
                coach_row[8]
            )

         
            training_readiness = (
                coach_row[9]
            )

        # =========================
        # 9. JSONB / 字符串兼容
        # =========================

        if isinstance(
            max_hang_decision,
            str
        ):

            try:

                max_hang_decision = json.loads(
                    max_hang_decision
                )

            except Exception:

                max_hang_decision = None


        if isinstance(
            strain_plan,
            str
        ):

            try:

                strain_plan = json.loads(
                    strain_plan
                )

            except Exception:

                strain_plan = None
             

        if isinstance(
            training_readiness,
            str
        ):

            try:

                training_readiness = json.loads(
                    training_readiness
                )

            except Exception:

                training_readiness = None
     

        # =========================
        # 10. 旧 Max Hang 日报兼容
        # =========================

        if not isinstance(
            max_hang_decision,
            dict
        ):

            max_hang_decision = {

                "status":
                    max_hang_status,

                "status_label":
                    (
                        "条件式评估Max Hang"
                        if max_hang_status == "conditional"

                        else
                        "当前数据支持暂缓Max Hang"
                        if max_hang_status == "avoid"

                        else
                        "当前数据支持进行Max Hang"
                        if max_hang_status == "allowed"

                        else
                        "暂无Max Hang决策"
                    ),

                "instruction":
                    (
                        "旧日报没有完整结构化Max Hang决策，"
                        "当前仅返回已保存状态。"
                    )

            }


        # =========================
        # 11. Strain Plan 唯一真源
        # =========================
        #
        # 正常情况：
        # 直接使用数据库保存的 strain_plan
        #
        # 只有旧日报没有 strain_plan 时，
        # 才调用 calculate_strain_plan() fallback
        # =========================

        if not isinstance(
            strain_plan,
            dict
        ):

            strain_plan = calculate_strain_plan({

                "recovery_score":
                    recovery_score,

                "cycle_strain":
                    cycle_strain

            })


        # =========================
        # Training Readiness旧日报兼容
        # =========================

        if not isinstance(
            training_readiness,
            dict
        ):

            training_readiness = {

                "overall_status":
                    "unknown",

                "overall_label":
                    "暂无保存的Training Readiness",

                "primary_limiter":
                    "unknown",

                "systemic_recovery":
                    "unknown",

                "recovery_state":
                    "unknown",
        
                "hrv_state":
                    "unknown",

                "rhr_state":
                    "unknown",
                
                "sleep_state":
                    "unknown",

                "finger_status":
                    "unknown",

                "elbow_status":
                    "unknown",

                "recommended_training":
                    [],

                "avoid_or_limit":
                    [],
        
                "max_hang_status":
                    max_hang_status,

                "current_strain":
                    strain_plan.get(
                        "current_strain",
                        0
                    ),

                "recommended_strain":
                    strain_plan.get(
                        "recommended_strain",
                        "0-0"
                    ),

                "strain_completion":
                    strain_plan.get(
                        "strain_completion",
                        0
                    ),

                "remaining_strain":
                    strain_plan.get(
                        "remaining_strain",
                        0
                    ),

                "reason":
                    (
                        "该日报生成时尚未保存training_readiness，"
                        "因此不在coach-report接口中重新推导训练准备度。"
                    )
        
            }

 

        # =========================
        # 12. 所有 Strain 字段
        #     全部从 strain_plan 获取
        # =========================

        current_strain = (
            strain_plan.get(
                "current_strain",
                0
            )
        )


        target_min = (
            strain_plan.get(
                "target_min",
                0
            )
        )


        target_max = (
            strain_plan.get(
                "target_max",
                0
            )
        )


        recommended_strain = (
            strain_plan.get(
                "recommended_strain",
                f"{target_min}-{target_max}"
            )
        )


        strain_completion = (
            strain_plan.get(
                "strain_completion",
                0
            )
        )


        remaining_strain = (
            strain_plan.get(
                "remaining_strain",
                0
            )
        )


        training_level = (
            strain_plan.get(
                "training_level",
                "数据不足"
            )
        )


        remaining_strain_explanation = (
            strain_plan.get(
                "remaining_strain_explanation",
                (
                    "remaining_strain表示距离推荐Strain区间下限的差值，"
                    "不代表今天绝对训练上限。"
                )
            )
        )


        # =========================
        # 13. DEBUG
        # =========================

        print(
            "COACH REPORT MAX HANG STATUS:",
            max_hang_status
        )


        print(
            "COACH REPORT MAX HANG DECISION:",
            max_hang_decision
        )


        print(
            "COACH REPORT STRAIN PLAN:",
            strain_plan
        )


        print(
            "COACH REPORT TRAINING LEVEL:",
            training_level
        )


        print(
            "COACH REPORT RECOMMENDED STRAIN:",
            recommended_strain
        )


        # =========================
        # 14. 返回完整报告
        # =========================

        return jsonify({

            "success": True,


            "coach_report": {


                # =========================
                # 今日数据
                # =========================

                "today": {

                    "date":
                        str(report_date),

                    "recovery":
                        recovery_score,

                    "recovery_status":
                        recovery_status,

                    "hrv":
                        hrv,

                    "resting_heart_rate":
                        resting_heart_rate,

                    "sleep_hours":
                        sleep_duration,

                    "sleep_score":
                        sleep_score,

                    "sleep_efficiency":
                        sleep_efficiency,

                    "deep_sleep_hours":
                        deep_sleep_duration,

                    "rem_sleep_hours":
                        rem_sleep_duration,

                    "deep_sleep_ratio":
                        deep_sleep_ratio,

                    "rem_sleep_ratio":
                        rem_sleep_ratio,

                    "light_sleep_ratio":
                        light_sleep_ratio,

                    "strain":
                        current_strain,


                    # =========================
                    # Strain Plan
                    # =========================

                    "training_level":
                        training_level,

                    "recommended_strain":
                        recommended_strain,

                    "strain_completion":
                        strain_completion,

                    "remaining_strain":
                        remaining_strain,

                    "training_advice":
                        training_advice,

                    "fatigue_warning":
                        fatigue_warning,


                    # =========================
                    # WHOOP皮肤温度
                    # =========================

                    "skin_temperature":
                        (
                            round(
                                float(
                                    skin_temperature
                                ),
                                2
                            )
                            if skin_temperature is not None
                            else None
                        ),

                    "skin_temperature_unit":
                        "°C",

                    "skin_temperature_label":
                        "WHOOP夜间皮肤温度",

                    "temperature_deviation":
                        temperature_deviation,


                    # =========================
                    # WHOOP SpO₂
                    # =========================

                    "spo2_percentage":
                        (
                            round(
                                float(
                                    spo2_percentage
                                ),
                                1
                            )
                            if spo2_percentage is not None
                            else None
                        ),

                    "spo2_unit":
                        "%",

                    "spo2_label":
                        "WHOOP血氧饱和度",

                    "spo2_deviation":
                        spo2_deviation

                },


                # =========================
                # 近期基线
                # =========================

                "baseline": {

                    "valid_days":
                        len(
                            weekly_rows
                        ),

                    "recovery_avg":
                        recovery_avg,

                    "hrv_avg":
                        hrv_avg,

                    "rhr_avg":
                        rhr_avg,

                    "sleep_avg":
                        sleep_avg,

                    "strain_avg":
                        strain_avg,

                    "skin_temperature_avg":
                        skin_temperature_avg,

                    "skin_temperature_valid_days":
                        skin_temperature_valid_days,

                    "spo2_avg":
                        spo2_avg,

                    "spo2_valid_days":
                        spo2_valid_days

                },


                # =========================
                # 温度
                # =========================

                "temperature": {

                    "source":
                        "WHOOP",

                    "skin_temperature":
                        (
                            round(
                                float(
                                    skin_temperature
                                ),
                                2
                            )
                            if skin_temperature is not None
                            else None
                        ),

                    "unit":
                        "°C",

                    "label":
                        "WHOOP夜间皮肤温度",

                    "skin_temperature_avg":
                        skin_temperature_avg,

                    "temperature_deviation":
                        temperature_deviation,

                    "valid_days":
                        skin_temperature_valid_days,

                    "baseline_reliable":
                        (
                            skin_temperature_valid_days
                            >= 3
                        ),

                    "interpretation":
                        (
                            "已有至少3天有效温度数据，"
                            "可结合个人近期基线观察变化。"
                            if skin_temperature_valid_days >= 3
                            else
                            "当前温度历史数据不足3天，"
                            "只报告当前WHOOP皮肤温度，"
                            "暂不做可靠趋势判断。"
                        )

                },


                # =========================
                # SpO₂
                # =========================

                "spo2": {

                    "source":
                        "WHOOP",

                    "spo2_percentage":
                        (
                            round(
                                float(
                                    spo2_percentage
                                ),
                                1
                            )
                            if spo2_percentage is not None
                            else None
                        ),

                    "unit":
                        "%",

                    "label":
                        "WHOOP血氧饱和度",

                    "spo2_avg":
                        spo2_avg,

                    "spo2_deviation":
                        spo2_deviation,

                    "valid_days":
                        spo2_valid_days,

                    "baseline_reliable":
                        (
                            spo2_valid_days
                            >= 3
                        ),

                    "interpretation":
                        (
                            "已有至少3天有效血氧数据，"
                            "可结合个人近期趋势观察变化。"
                            if spo2_valid_days >= 3
                            else
                            "当前血氧历史数据不足3天，"
                            "只报告当前WHOOP血氧值，"
                            "不做可靠趋势判断。"
                        )

                },


                # =========================
                # AI Coach
                # =========================

                "coach": {

                    "training_level":
                        training_level,

                    "training_recommendation":
                        training_recommendation,

                    "risk_warning":
                        risk_warning,

                    "coach_report_text":
                        coach_report_text,


                    # =========================
                    # Strain兼容字段
                    # 全部来自strain_plan
                    # =========================

                    "current_strain":
                        current_strain,

                    "recommended_strain":
                        recommended_strain,

                    "strain_completion":
                        strain_completion,

                    "remaining_strain":
                        remaining_strain,

                    "remaining_strain_explanation":
                        remaining_strain_explanation,


                    # =========================
                    # Strain唯一结构
                    # =========================

                    "strain_plan":
                        strain_plan,


                    "training_readiness":
                        training_readiness,

                 
                    # =========================
                    # 疲劳
                    # =========================

                    "fatigue_warning":
                        fatigue_warning,

                    "continuous_fatigue":
                        continuous_fatigue,


                    # =========================
                    # Max Hang
                    # =========================

                    "max_hang_status":
                        max_hang_status,

                    "max_hang_decision":
                        max_hang_decision,


                    # =========================
                    # 温度 / SpO₂摘要
                    # =========================

                    "skin_temperature":
                        (
                            round(
                                float(
                                    skin_temperature
                                ),
                                2
                            )
                            if skin_temperature is not None
                            else None
                        ),

                    "skin_temperature_avg":
                        skin_temperature_avg,

                    "skin_temperature_valid_days":
                        skin_temperature_valid_days,

                    "temperature_deviation":
                        temperature_deviation,

                    "spo2_percentage":
                        (
                            round(
                                float(
                                    spo2_percentage
                                ),
                                1
                            )
                            if spo2_percentage is not None
                            else None
                        ),

                    "spo2_avg":
                        spo2_avg,

                    "spo2_valid_days":
                        spo2_valid_days,

                    "spo2_deviation":
                        spo2_deviation

                }

            }

        })


    except Exception as e:

        print(
            "WHOOP COACH REPORT ERROR:",
            e
        )


        return jsonify({

            "success": False,

            "error":
                str(e)

        }), 500


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


def validate_weekly_output(
    text
):

    import re


    if text is None:
        text = ""

    text = str(
        text
    )


    # =========================
    # 1. 明确禁止的未来日期表达
    # =========================

    forbidden_patterns = [

        r"明天",
        r"明日",
        r"后天",
        r"后日",

        r"随后\s*1\s*[-—~至]\s*2\s*天",
        r"未来\s*1\s*[-—~至]\s*2\s*天",

        r"第\s*2\s*天",
        r"第\s*3\s*天",

        r"下一天",

        r"今天.*→.*明天",
        r"今天.*->.*明天",

        r"明天.*→.*后天",
        r"明天.*->.*后天"
    ]


    # =========================
    # 2. 禁止预测未来生理指标
    # =========================

    future_prediction_patterns = [

        r"(明天|明日).{0,30}Recovery",
        r"(明天|明日).{0,30}HRV",
        r"(明天|明日).{0,30}静息心率",
        r"(明天|明日).{0,30}睡眠",

        r"(明天|明日).{0,30}恢复状态",

        r"(明天|明日).{0,30}可能.*改善",
        r"(明天|明日).{0,30}可能.*维持",

        r"(明天|明日).{0,30}恢复趋势"
    ]


    # =========================
    # 3. 禁止未来具体训练排程
    # =========================

    future_training_patterns = [

        r"(明天|明日).{0,40}休息",
        r"(明天|明日).{0,40}恢复",
        r"(明天|明日).{0,40}低负荷",

        r"(明天|明日).{0,40}技术攀岩",
        r"(明天|明日).{0,40}攀岩",

        r"(明天|明日).{0,40}Max Hang",
        r"(明天|明日).{0,40}Repeaters",

        r"(明天|明日).{0,40}高强度",
        r"(明天|明日).{0,40}质量训练",

        r"随后.{0,20}质量训练",
        r"恢复后.{0,20}质量训练",

        r"状态改善后.{0,20}质量训练"
    ]


    all_patterns = (
        forbidden_patterns
        + future_prediction_patterns
        + future_training_patterns
    )


    violations = []


    # =========================
    # 4. Regex 检查
    # =========================

    for pattern in all_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            violation = (
                match.group(0)
            )

            if violation not in violations:

                violations.append(
                    violation
                )


    # =========================
    # 5. 返回结果
    # =========================

    return {

        "valid":
            len(
                violations
            ) == 0,

        "violations":
            violations

    }


@app.route("/api/whoop/weekly-coach-report",methods=["GET"])
@require_chatgpt_api_key
def api_whoop_weekly_coach_report():

    try:

        print(
            "========== WEEKLY COACH REPORT START =========="
        )


        # =========================
        # 1. 生成 Weekly 数据
        # =========================

        weekly_data = (
            generate_weekly_analysis()
        )


        if not isinstance(
            weekly_data,
            dict
        ):

            weekly_data = {}


        if not weekly_data.get(
            "success"
        ):

            return jsonify({
                "success": False,
                "error": weekly_data.get(
                    "error",
                    "Unable to generate weekly analysis"
                ),
                "weekly_data": weekly_data
            }), 500


        # =========================
        # 2. 获取 Weekly Prompt
        # =========================

        prompt_text = (
            weekly_data.get(
                "prompt_text",
                ""
            )
        )


        if not prompt_text:

            return jsonify({
                "success": False,
                "error": "Weekly prompt is empty"
            }), 500


        # =========================
        # 3. 调用 AI
        # =========================

        print("\n")
        print("=" * 80)
        print("FINAL WEEKLY PROMPT SENT TO AI")
        print("=" * 80)
        print(prompt_text)
        print("=" * 80)
        print("\n")


        # =========================
        # 3.1 第一次生成 Weekly
        # =========================

        ai_result = (
            generate_ai_summary(
                prompt_text
            )
        )


        print(
            "WEEKLY AI FIRST RESULT:",
            repr(ai_result)
        )


        # =========================
        # 3.2 提取第一次 AI 文本
        #     用于验证
        # =========================

        if isinstance(
            ai_result,
            dict
        ):

            first_ai_text = (
                ai_result.get(
                    "ai_report"
                )
                or ai_result.get(
                    "report"
                )
                or ai_result.get(
                    "content"
                )
                or str(ai_result)
            )

        else:

            first_ai_text = str(
                ai_result
            )


        # =========================
        # 3.3 验证 Weekly 输出
        # =========================

        validation = (
            validate_weekly_output(
                first_ai_text
            )
        )


        print(
            "WEEKLY OUTPUT VALIDATION:",
            validation
        )


        # =========================
        # 3.4 如果违规
        #     自动重写一次
        # =========================

        if not validation.get(
            "valid",
            False
        ):

            violations = (
                validation.get(
                    "violations",
                    []
                )
            )


            print(
                "WEEKLY OUTPUT VIOLATIONS:",
                violations
            )


            rewrite_prompt = f"""
你正在修正一份 Weekly Coach 报告。

下面的原始报告违反了 Weekly Coach 的未来训练决策边界。

==============================
原始 Weekly Coach 报告
==============================

{first_ai_text}


==============================
检测到的违规表达
==============================

{violations}


==============================
必须遵守的重写规则
==============================

Weekly Coach 的职责是：

1. 总结最近7天趋势。
2. 分析恢复和训练负荷背景。
3. 提供未来训练的“决策条件”。
4. 不替未来某个具体日期决定训练内容。


禁止使用未来日期或顺序日期来安排训练，例如：

- 明天
- 后天
- 随后1-2天
- 未来1-2天
- 第2天
- 第3天
- 下一天


禁止输出类似：

“明天休息”
“明天恢复”
“明天低负荷”
“明天技术攀岩”
“随后1-2天安排质量训练”
“状态改善后安排一个质量日”
“今天结束负荷 → 明天恢复 → 后天质量训练”


未来训练必须表达为“条件决策”。

例如：

“下一训练日重新读取最新 Daily Coach，
根据当天 Recovery、HRV、静息心率、睡眠、
局部疲劳和 Training Readiness
决定当天训练类型和强度。”


对于质量训练：

只有当最新 Daily Coach 显示整体恢复支持，
同时局部手指、肘部和前臂状态正常时，
才考虑较高质量攀岩或力量训练。


对于降低负荷：

如果最新恢复指标下降，
或局部疲劳明显升高，
则由当天 Daily Coach 决定降低训练负荷、
进行恢复训练或休息。


对于 Max Hang：

Weekly Coach 不得指定 Max Hang 的未来执行日期。

是否执行 Max Hang，
必须由计划训练当天最新的
Max Hang Decision 决定。


最终训练框架应该表达为：

当前训练状态
→ 下一训练日重新读取 Daily Coach
→ 根据当天状态决定训练类型和强度
→ 满足质量训练条件时再考虑质量训练
→ Max Hang 由执行当天专项决策决定。


不得预测未来具体的：

- Recovery
- HRV
- 静息心率
- Sleep Score


请完整重写原报告。

==============================
输出前强制自检
==============================

在输出最终结果之前，
必须逐字检查整份报告。

最终文本中不得出现以下任何词语或表达：

明天
明日
后天
后日
随后1-2天
随后 1-2 天
未来1-2天
未来 1-2 天
第2天
第3天
下一天

明天恢复
明日恢复
明天训练
明日训练
明天低负荷
明日低负荷
明天休息
明日休息
明天技术攀岩
明日技术攀岩


如果草稿中出现以上表达，

必须在输出前改写为以下允许表达：

“下一训练日”
“后续训练”
“计划训练当天”
“执行当天”
“当天最新 Daily Coach”
“满足条件时”
“当状态支持时”
“当恢复和局部状态支持时”


例如：

不得写：

“明日恢复趋势”

应改成：

“后续恢复状态需要结合下一训练日最新数据重新评估”。


不得写：

“明天如果HRV没有改善则低负荷”

应改成：

“下一训练日如果最新HRV、睡眠或局部状态不支持训练，
则由当天Daily Coach决定降低负荷或恢复。”


不得写：

“恢复后安排一个质量日”

应改成：

“当当天Training Readiness、
恢复指标和局部状态支持质量训练时，
再考虑较高质量训练。”


不得写：

“明天重新评估”

应改成：

“下一训练日重新读取最新Daily Coach并评估。”


Max Hang不得使用任何未来日期表达。

只能写：

“Max Hang是否执行，
必须读取计划执行当天最新的Max Hang Decision。”


在真正输出之前，
必须再次确认全文没有出现：

明天
明日
后天
随后1-2天
未来1-2天
第2天
第3天
下一天

如果仍然存在，
继续改写，
直到这些表达全部消失。


禁止输出自检过程。
禁止解释你进行了修改。
只输出最终合规报告。

只输出最终重写后的 Weekly Coach 报告。
使用简体中文。
"""


            rewritten_result = (
                generate_weekly_ai_summary(
                    rewrite_prompt
                )
            )


            print(
                "WEEKLY AI REWRITTEN RESULT:",
                repr(
                    rewritten_result
                )
            )


            # =========================
            # 3.4.1 提取重写后的文本
            # =========================

            if isinstance(
                rewritten_result,
                dict
            ):

                rewritten_text = (
                    rewritten_result.get(
                        "ai_report"
                    )
                    or rewritten_result.get(
                        "report"
                    )
                    or rewritten_result.get(
                        "content"
                    )
                    or str(
                        rewritten_result
                    )
                )

            else:

                rewritten_text = str(
                    rewritten_result
                )


            # =========================
            # 3.4.2 第二次最终验证
            # =========================

            final_validation = (
                validate_weekly_output(
                    rewritten_text
                )
            )


            print(
                "WEEKLY FINAL VALIDATION:",
                final_validation
            )


            # =========================
            # 3.4.3 重写后合格
            # =========================

            if final_validation.get(
                "valid",
                False
            ):

                ai_result = (
                    rewritten_result
                )


            # =========================
            # 3.4.4 重写后仍违规
            #       使用安全兜底
            # =========================

            else:

                print(
                    "WEEKLY FINAL VALIDATION FAILED:",
                    final_validation.get(
                        "violations",
                        []
                    )
                )


                safe_fallback_report = f"""
📊 最近7天趋势

最近7天WHOOP与训练数据已经完成分析。

平均Recovery：
{weekly_data.get("avg_recovery")}%

平均HRV：
{weekly_data.get("avg_hrv")} ms

平均静息心率：
{weekly_data.get("avg_resting_hr")} bpm

平均睡眠：
{weekly_data.get("avg_sleep")} 小时

平均Strain：
{weekly_data.get("avg_strain")}


🧗 训练负荷

最近7天攀岩次数：
{weekly_data.get("climbing_sessions_7d", 0)}

最近7天攀岩总时长：
{weekly_data.get("climbing_duration_7d", 0)} 分钟

最近7天指力板次数：
{weekly_data.get("hangboard_sessions_7d", 0)}

最近7天指力板总时长：
{weekly_data.get("hangboard_duration_7d", 0)} 分钟

最近一次手指疲劳：
{weekly_data.get("latest_finger_fatigue")}/10

最近一次肘部疲劳：
{weekly_data.get("latest_elbow_fatigue")}/10


📅 未来训练决策框架

当前训练状态：
根据最近7天恢复和训练负荷，后续训练应继续结合每天最新状态动态调整。

下一训练日：
重新读取当天最新 Daily Coach，
根据当天 Recovery、HRV、静息心率、睡眠、
局部疲劳和 Training Readiness
决定训练类型和训练强度。

质量训练条件：
只有当当天整体恢复、HRV趋势、睡眠和局部手指/肘部状态
支持质量训练时，
才考虑较高质量攀岩或力量训练。

降负荷条件：
如果当天恢复指标下降、
睡眠不足、
HRV趋势不理想、
局部疲劳升高，
或 Training Readiness 不支持，
则由当天 Daily Coach 决定降低训练负荷、恢复或休息。

Max Hang：
Weekly Coach 不预设执行日期。
是否执行必须读取计划训练当天最新的 Max Hang Decision。

整体流程：
当前训练状态
→ 下一训练日重新读取 Daily Coach
→ 根据当天状态决定训练类型和强度
→ 满足质量训练条件时再考虑质量训练
→ Max Hang由执行当天专项决策决定。
"""


                ai_result = {
                    "ai_report":
                        safe_fallback_report,

                    "training_advice":
                        (
                            "未来训练不按固定日期预排。"
                            "下一训练日读取最新Daily Coach后，"
                            "根据当天恢复、睡眠、HRV和局部状态决定训练类型和强度。"
                        ),

                    "risk_warning":
                        (
                            "Weekly数据仅用于趋势和训练框架。"
                            "未来具体训练决策必须结合执行当天最新状态。"
                        )
                }


                print(
                    "WEEKLY SAFE FALLBACK USED"
                )


        # =========================
        # 3.5 最终 AI 结果
        # =========================

        print(
            "WEEKLY AI RAW:",
            repr(ai_result)
        )

     
        # =========================
        # 4. 提取 AI 文本
        # =========================

        if isinstance(
            ai_result,
            dict
        ):

            ai_report = (
                ai_result.get(
                    "ai_report"
                )
                or ai_result.get(
                    "report"
                )
                or ai_result.get(
                    "content"
                )
                or str(ai_result)
            )

        else:

            ai_report = str(
                ai_result
            )


        # =========================
        # 5. 格式化 Weekly Report
        # =========================

        formatted_report = (
            format_weekly_report(
                ai_report
            )
        )


        print(
            "========== WEEKLY COACH REPORT SUCCESS =========="
        )


        # =========================
        # 6. 返回
        # =========================

        return jsonify({

            "success": True,

            "period": {
                "start_date":
                    weekly_data.get(
                        "start_date"
                    ),

                "end_date":
                    weekly_data.get(
                        "end_date"
                    ),

                "valid_days":
                    weekly_data.get(
                        "valid_days",
                        0
                    ),

                "is_complete":
                    weekly_data.get(
                        "is_complete",
                        False
                    )
            },

            "averages": {
                "recovery":
                    weekly_data.get(
                        "avg_recovery"
                    ),

                "hrv":
                    weekly_data.get(
                        "avg_hrv"
                    ),

                "resting_heart_rate":
                    weekly_data.get(
                        "avg_resting_hr"
                    ),

                "sleep":
                    weekly_data.get(
                        "avg_sleep"
                    ),

                "sleep_score":
                    weekly_data.get(
                        "avg_sleep_score"
                    ),

                "strain":
                    weekly_data.get(
                        "avg_strain"
                    )
            },

            "training_load":
                weekly_data.get(
                    "training_load",
                    {}
                ),

            "climbing_fatigue":
                weekly_data.get(
                    "climbing_fatigue",
                    {}
                ),

            "temperature": {
                "latest":
                    weekly_data.get(
                        "skin_temperature"
                    ),

                "average":
                    weekly_data.get(
                        "skin_temperature_avg"
                    ),

                "deviation":
                    weekly_data.get(
                        "temperature_deviation"
                    ),

                "valid_days":
                    weekly_data.get(
                        "skin_temperature_valid_days",
                        0
                    ),

                "baseline_reliable":
                    weekly_data.get(
                        "temperature_baseline_reliable",
                        False
                    )
            },

            "spo2": {
                "latest":
                    weekly_data.get(
                        "spo2_percentage"
                    ),

                "average":
                    weekly_data.get(
                        "spo2_avg"
                    ),

                "deviation":
                    weekly_data.get(
                        "spo2_deviation"
                    ),

                "valid_days":
                    weekly_data.get(
                        "spo2_valid_days",
                        0
                    ),

                "baseline_reliable":
                    weekly_data.get(
                        "spo2_baseline_reliable",
                        False
                    )
            },

            "records":
                weekly_data.get(
                    "records",
                    []
                ),

            "report":
                formatted_report,

            "raw_ai_report":
                ai_report

        })


    except Exception as e:

        import traceback

        print(
            "WEEKLY COACH REPORT ERROR:",
            e
        )

        traceback.print_exc()


        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
     

@app.route("/training/log", methods=["POST"])
def add_training_log():

    import traceback

    conn = None
    cur = None


    # =========================
    # 1. API Key
    # =========================

    if not check_api_key():

        return jsonify({

            "success":
                False,

            "error":
                "unauthorized"

        }), 401


    # =========================
    # 2. 获取 JSON
    # =========================

    data = request.get_json(
        silent=True
    )


    print(
        "CLIMBING SAVE RAW DATA:",
        data
    )


    if not isinstance(
        data,
        dict
    ):

        return jsonify({

            "success":
                False,

            "error":
                "请求内容必须是JSON对象"

        }), 400


    # =========================
    # 3. 必填字段
    # =========================

    if not data.get(
        "training_date"
    ):

        return jsonify({

            "success":
                False,

            "error":
                "缺少training_date"

        }), 400


    if not data.get(
        "training_type"
    ):

        return jsonify({

            "success":
                False,

            "error":
                "缺少training_type"

        }), 400


    # =========================
    # 4. 保存攀岩训练
    # =========================

    try:

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

            VALUES
            (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s
            )
            """,

            (
                data.get(
                    "training_date"
                ),

                data.get(
                    "training_type"
                ),

                data.get(
                    "duration"
                ),

                data.get(
                    "intensity"
                ),

                data.get(
                    "climbing_grade"
                ),

                data.get(
                    "boulder_count"
                ),

                data.get(
                    "hangboard_seconds"
                ),

                data.get(
                    "hangboard_weight"
                ),

                data.get(
                    "finger_fatigue"
                ),

                data.get(
                    "forearm_fatigue"
                ),

                data.get(
                    "notes"
                )
            )
        )


        conn.commit()


        print(
            "CLIMBING TRAINING SAVED"
        )


    except Exception as e:

        print(
            "CLIMBING SAVE ERROR:",
            repr(
                e
            )
        )

        traceback.print_exc()


        if conn:

            conn.rollback()


        return jsonify({

            "success":
                False,

            "training_saved":
                False,

            "error":
                str(
                    e
                )

        }), 500


    finally:

        if cur:

            cur.close()


        if conn:

            conn.close()


    # =========================
    # 5. 自动刷新今日 Coach
    # =========================

    report_refreshed = False

    refresh_error = None

    refreshed_report = None


    try:

        print(
            "START REFRESH DAILY COACH AFTER CLIMBING"
        )


        refreshed_report = (
            generate_daily_coach_report()
        )


        report_refreshed = True


        print(
            "DAILY COACH REFRESHED AFTER CLIMBING"
        )


    except Exception as e:

        refresh_error = str(
            e
        )


        print(
            "DAILY COACH REFRESH ERROR AFTER CLIMBING:",
            repr(
                e
            )
        )

        traceback.print_exc()


    # =========================
    # 6. 返回结果
    # =========================

    response = {

        "success":
            True,

        "training_saved":
            True,

        "report_refreshed":
            report_refreshed,

        "message":
            (
                "攀岩训练已保存，并已刷新今日教练报告"
                if report_refreshed
                else
                "攀岩训练已保存，但今日教练报告刷新失败"
            ),

        "training": {

            "training_date":
                data.get(
                    "training_date"
                ),

            "training_type":
                data.get(
                    "training_type"
                ),

            "duration":
                data.get(
                    "duration"
                ),

            "intensity":
                data.get(
                    "intensity"
                ),

            "climbing_grade":
                data.get(
                    "climbing_grade"
                ),

            "boulder_count":
                data.get(
                    "boulder_count"
                ),

            "hangboard_seconds":
                data.get(
                    "hangboard_seconds"
                ),

            "hangboard_weight":
                data.get(
                    "hangboard_weight"
                ),

            "finger_fatigue":
                data.get(
                    "finger_fatigue"
                ),

            "forearm_fatigue":
                data.get(
                    "forearm_fatigue"
                ),

            "notes":
                data.get(
                    "notes"
                )

        }

    }


    # =========================
    # 7. 刷新成功时返回最新决策
    # =========================

    if report_refreshed:

        response[
            "daily_coach"
        ] = {

            "max_hang_status":
                refreshed_report.get(
                    "max_hang_status"
                ),

            "max_hang_decision":
                refreshed_report.get(
                    "max_hang_decision"
                ),

            "strain_plan":
                refreshed_report.get(
                    "strain_plan"
                ),

            "training_readiness":
                refreshed_report.get(
                    "training_readiness"
                )

        }


    else:

        response[
            "refresh_error"
        ] = refresh_error


    print(
        "CLIMBING TRAINING SAVED:",
        True
    )

    print(
        "REPORT REFRESHED:",
        report_refreshed
    )


    return jsonify(
        response
    ), 200


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


@app.route(
    "/training/hangboard",
    methods=["POST"]
)
def training_hangboard():

    import traceback


    # =========================
    # 1. API Key
    # =========================

    if not check_api_key():

        return jsonify({

            "success":
                False,

            "error":
                "unauthorized"

        }), 401


    # =========================
    # 2. 获取JSON
    # =========================

    data = request.get_json(
        silent=True
    )


    print(
        "HANGBOARD SAVE RAW DATA:",
        data
    )


    if not isinstance(
        data,
        dict
    ):

        return jsonify({

            "success":
                False,

            "error":
                "请求内容必须是JSON对象"

        }), 400


    # =========================
    # 3. 必填字段
    # =========================

    if not data.get(
        "training_date"
    ):

        return jsonify({

            "success":
                False,

            "error":
                "缺少training_date"

        }), 400


    if not data.get(
        "protocol"
    ):

        return jsonify({

            "success":
                False,

            "error":
                "缺少protocol"

        }), 400


    # =========================
    # 4. 保存训练
    # =========================

    try:

        saved = (
            save_hangboard_training(
                data
            )
        )


        if not saved:

            return jsonify({

                "success":
                    False,

                "error":
                    "指力板训练保存失败"

            }), 500


    except Exception as e:

        print(
            "HANGBOARD SAVE ERROR:",
            repr(
                e
            )
        )

        traceback.print_exc()


        return jsonify({

            "success":
                False,

            "error":
                str(
                    e
                )

        }), 500


    print(
        "HANGBOARD TRAINING SAVED"
    )


    # =========================
    # 5. 刷新今日Coach Report
    # =========================

    report_refreshed = False

    refresh_error = None

    refreshed_report = None


    try:

        print(
            "START REFRESH DAILY COACH AFTER HANGBOARD"
        )


        refreshed_report = (
            generate_daily_coach_report()
        )


        report_refreshed = True


        print(
            "DAILY COACH REFRESHED AFTER HANGBOARD"
        )


    except Exception as e:

        refresh_error = str(
            e
        )


        print(
            "DAILY COACH REFRESH ERROR AFTER HANGBOARD:",
            repr(
                e
            )
        )

        traceback.print_exc()


    # =========================
    # 6. 返回
    # =========================

    response = {

        "success":
            True,

        "message":
            (
                "指力板训练已保存，并已刷新今日教练报告"
                if report_refreshed
                else
                "指力板训练已保存，但今日教练报告刷新失败"
            ),

        "training_saved":
            True,

        "report_refreshed":
            report_refreshed,

        "training": {

            "training_date":
                data.get(
                    "training_date"
                ),

            "protocol":
                data.get(
                    "protocol"
                ),

            "session_type":
                data.get(
                    "session_type"
                ),

            "edge_size":
                data.get(
                    "edge_size"
                ),

            "grip_type":
                data.get(
                    "grip_type"
                ),

            "added_weight":
                data.get(
                    "added_weight"
                ),

            "hold_seconds":
                data.get(
                    "hold_seconds"
                ),

            "duration":
                data.get(
                    "duration"
                ),

            "sets":
                data.get(
                    "sets"
                ),

            "total_hang_time":
                data.get(
                    "total_hang_time"
                ),

            "intensity":
                data.get(
                    "intensity"
                ),

            "finger_fatigue":
                data.get(
                    "finger_fatigue"
                ),

            "elbow_fatigue":
                data.get(
                    "elbow_fatigue"
                ),

            "recovery_after":
                data.get(
                    "recovery_after"
                ),

            "notes":
                data.get(
                    "notes"
                )

        }

    }


    if report_refreshed:

        response[
            "daily_coach"
        ] = {

            "max_hang_status":
                refreshed_report.get(
                    "max_hang_status"
                ),

            "max_hang_decision":
                refreshed_report.get(
                    "max_hang_decision"
                ),

            "strain_plan":
                refreshed_report.get(
                    "strain_plan"
                ),

            "training_readiness":
                refreshed_report.get(
                    "training_readiness"
                )

        }


    else:

        response[
            "refresh_error"
        ] = refresh_error


    return jsonify(
        response
    ), 200

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

font-size:22px;

font-weight:700;

margin-bottom:8px;

color:#111;

}}


.ai-item-content {{

font-size:16px;

line-height:1.75;

margin-bottom:6px;

color:#222;

}}


.ai-section-content {{

font-size:16px;

line-height:1.75;

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

.ai-period {{
color:#be185d;
}}

.ai-temperature {{
color:#0891b2;
}}

.ai-injury {{
color:#7c3aed;
}}

.ai-default {{
color:#111;
}}

.ai-risk-box {{

background:#fafafa;

border-radius:16px;

padding:14px 18px;

margin-bottom:12px;

}}


.ai-risk-title {{

font-size:22px;

font-weight:700;

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
        font-size:19px;
        line-height:1.4;
        margin-bottom:8px;
    }}

    .ai-item-content {{
        font-size:15px;
        line-height:1.7;
    }}

    .ai-risk-title {{
        font-size:19px;
        line-height:1.4;
        margin-bottom:8px;
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
        font-size: 18px;
    }}

    .ai-item-content {{
        font-size: 14px;
    }}

    .ai-risk-title {{
        font-size:18px;
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

<div class="ai-item">

<div class="ai-item-title">

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
            "避免  和高强度 Repeaters"
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
强制输出与风险一致性规则
==============================

最终 ai_report 必须严格包含以下8个标题，
且每个标题只出现一次：

🟡 今日教练总结
🧠 今日身体状态
❤️ 恢复分析
😴 睡眠分析
🌡️ 身体温度
🫁 血氧状态
🏋️ 今日训练建议
📈 明日恢复趋势


==============================
身体温度强制规则
==============================

如果提供 WHOOP皮肤温度：

必须在“🌡️ 身体温度”中报告。

如果有效历史少于3天：

必须说明：

“当前温度历史数据不足，
暂不做可靠个人趋势判断。”

不得写：

“体温正常”
“体温偏低”
“体温偏高”
“发烧”
“感染”

WHOOP皮肤温度不是核心体温。


==============================
SpO2强制规则
==============================

如果提供 SpO₂：

必须在“🫁 血氧状态”中报告实际数值。

如果有效历史少于3天：

必须说明：

“当前血氧历史数据不足，
暂不做可靠趋势判断。”

不得仅凭单次SpO₂使用：

“正常范围”
“异常”
“缺氧”
“呼吸系统异常”

等医学或人群标准判断。


==============================
睡眠表达规则
==============================

不得仅根据睡眠效率高
就判断睡眠“充足”。

必须同时考虑：

睡眠时长
睡眠评分
睡眠效率
个人近期平均

如果睡眠时长低于个人近期平均，

优先写：

“睡眠效率较好，但时长略低于近期平均。”

不得自行使用固定7小时或8小时
作为用户个人睡眠达标线，
除非输入数据明确提供该目标。


==============================
Strain字段强制规则
==============================

训练建议中的：

当前 Strain
目标 Strain
训练完成度
剩余建议负荷

必须直接使用输入中提供的结构化字段。

不得自行重新计算：

目标 Strain
训练完成度
remaining_strain。


remaining_strain 表示：

距离推荐 Strain 区间下限还差多少。

它不代表：

当天最多还能增加多少 Strain。

不得写：

“剩余约6”
“今天最多还能增加6”
“今日总Strain不得超过10”

除非后端明确提供这样的上限。


如果后端提供：

current_strain = 4.08
recommended_strain = 8-10
strain_completion = 40%
remaining_strain = 3.92

则应直接写：

当前 Strain：4.08
目标 Strain：8-10
训练完成度：40%
剩余建议负荷：3.92

并可补充说明：

“剩余建议负荷表示距离推荐区间下限的差值，
不代表今日绝对训练上限。”


==============================
明日恢复趋势强制规则
==============================

不得预测任何未来具体数值。

禁止：

“明天Recovery会达到80以上”
“明天Recovery可能达到90”
“HRV明天会升至60”
“静息心率会下降到XX”

只能使用条件式表达：

“如果今晚睡眠和恢复良好，
明天整体恢复状态可能维持或改善。”

“如果HRV维持稳定或回升，
且局部疲劳下降，
明天可以重新评估训练强度。”


==============================
risk_warning强制规则
==============================

risk_warning只能使用输入数据明确支持的风险。

不得自行制造风险。

如果肘部疲劳处于低水平，
且没有明确肘部疼痛、动作受限或伤病记录：

不得写：

“肘部风险”
“攀岩可能伤肘”
“加强肘部力量训练”

应写：

“当前肘部局部疲劳较低，
暂无明确肘部风险信号。”


如果手指疲劳为4-6/10：

必须定义为：

“中等局部手指疲劳”。

不得写：

“疲劳累积”
“恢复不足”
“过度使用”
“肌腱风险”

除非存在明确证据。


训练频率较高只能作为辅助负荷信息，

不能单独成为：

手指风险
肘部风险
过度使用

的依据。


==============================
Max Hang与Repeaters最终决策强制规则
==============================

以下规则属于最终训练决策规则。

如果与前面的普通训练建议、
局部疲劳判断或训练频率判断存在冲突，
以本节规则为准。


一、Max Hang 与 Repeaters 必须分开判断

Max Hang：

属于高强度最大力量指力训练。


Repeaters：

属于重复悬挂训练，
通常偏力量耐力或耐力训练。

Repeaters 的实际训练强度
必须结合：

- 悬挂强度
- 附加重量
- 组数
- 单次悬挂时间
- 总悬挂时间
- 组间休息
- 手指局部状态

综合判断。


不得把所有 Repeaters
统一描述为：

“最大力量训练”
“高强度最大力量训练”。

也不得因为 Max Hang 暂缓，
自动同时禁止 Repeaters。


==============================
二、中等局部手指疲劳规则
==============================

最近一次手指疲劳为4-6/10时，

必须统一定义为：

“中等局部手指疲劳”。


4-6/10本身：

不等于疲劳累积；

不等于恢复不足；

不等于过度使用；

不等于高风险；

不等于必须停止攀岩；

不等于必须禁止Max Hang；

不等于必须禁止Repeaters。


不得仅凭4-6/10直接写：

“今天不适合Max Hang”
“避免Max Hang”
“不建议Max Hang”
“避免Repeaters”
“不建议Repeaters”。


是否适合Max Hang或Repeaters，

必须结合下面的完整条件判断。


==============================
三、Max Hang恢复评估条件
==============================

当同时满足：

1. Recovery >=67%；

2. HRV不低于近期个人基线；

3. 静息心率稳定
   或低于近期个人基线；

4. 睡眠没有明显异常；

5. 训练后恢复评分
   recovery_after >=75；

6. 最近一次手指疲劳为4-6/10；

7. 没有明确记录：
   - 疼痛
   - 僵硬
   - 肌腱敏感
   - 肿胀
   - 动作受限；

且当前唯一未确认的是：

8. 是否达到足够恢复间隔；

9. 热身后手指主观状态；

则不得直接得出：

“避免Max Hang”
“不建议Max Hang”
“不适合Max Hang”
“暂缓高强度最大力量指力训练”。


必须使用条件式结论：

“当前整体恢复条件基本支持
Max Hang的恢复评估。

如果确认距离上次高强度指力训练
的恢复间隔足够，
且热身后手指状态正常，

可以考虑降低总量进行Max Hang；

如果恢复间隔不足，
或热身后手指状态不佳，

则暂缓Max Hang。”


==============================
四、恢复间隔未确认规则
==============================

如果训练记录只有：

training_date

而没有：

具体训练时间
训练开始时间
训练结束时间
准确时间戳

则只能判断：

相隔多少个自然日。


不得声称：

“已经满足48小时”
“已经恢复48小时”
“已经超过48小时”。


同时：

无法确认完整48小时，

也不等于：

“不满足恢复间隔”。


因此，

如果其他Max Hang恢复条件均满足，
但完整恢复间隔无法确认，

不得直接禁止Max Hang。


必须写：

“恢复间隔需要结合实际训练时间确认。”


==============================
五、Max Hang首次恢复训练
==============================

当Max Hang恢复条件满足时，

可以考虑恢复Max Hang，

但第一次恢复训练
必须降低总训练量。


可以采用：

- 减少组数
- 减少总悬挂时间
- 适当降低附加重量
- 增加组间休息
- 在动作质量下降前停止


不得直接建议：

- 恢复最高训练量
- 测试最大重量
- 冲击个人纪录
- 增加到历史最高负荷


==============================
六、允许直接避免Max Hang的条件
==============================

只有存在明确风险证据时，

才可以直接建议：

“避免Max Hang”
或
“暂缓Max Hang”。


明确风险证据包括：

- 最近一次手指疲劳 >=7/10；

- 连续多次手指疲劳 >=7/10；

- recovery_after明显偏低；

- 明确疼痛；

- 明确僵硬；

- 明确肌腱敏感；

- 明确肿胀；

- 明确动作受限；

- 多项恢复指标持续恶化；

- HRV明显低于个人近期基线，
  并伴随其他恢复异常；

- 静息心率明显升高，
  并伴随其他恢复异常；

- 睡眠明显不足，
  并伴随其他恢复异常。


不得仅因为：

- 最近7天指力板训练次数较多；
- 最近7天攀岩次数较多；
- 手指疲劳4-6/10；
- 无法确认完整48小时；

就直接禁止Max Hang。


==============================
七、Repeaters最终判断
==============================

Repeaters必须独立于Max Hang判断。


如果：

- 整体恢复良好；
- Recovery >=67%；
- HRV稳定；
- 静息心率稳定；
- 睡眠没有明显异常；
- 手指疲劳为4-6/10；
- recovery_after >=75；
- 没有明确疼痛、僵硬、
  肌腱敏感、肿胀或动作受限；

则不得自动把Repeaters
放入“避免训练”。


可以根据局部状态建议：

- 降低悬挂强度；
- 减少组数；
- 减少总悬挂时间；
- 增加组间休息；
- 采用低量Repeaters。


推荐表达：

“Repeaters：
如进行，建议降低强度或总量，
并根据热身后的手指状态动态调整。”


如果存在：

手指疲劳 >=7/10、

明显疼痛、

动作受限、

recovery_after明显偏低

或其他明确局部高风险信号，

才可以建议暂缓Repeaters。


==============================
八、ai_report最终措辞要求
==============================

如果Max Hang的主要条件均满足，

但恢复间隔或热身状态尚未确认，

ai_report不得写：

“今天不建议进行最大力量指力训练。”

不得写：

“避免Max Hang。”

不得写：

“暂缓高强度最大力量指力训练。”


应写：

“今天整体恢复状态良好，
但存在中等局部手指疲劳。

Max Hang是否进行，
需要结合恢复间隔和热身后的手指状态判断。

如果恢复间隔足够且热身状态正常，
可以考虑降低总量进行；
否则暂缓。”


==============================
九、training_advice最终措辞要求
==============================

如果Max Hang只有：

恢复间隔

或

热身状态

尚未确认，

training_advice不得把Max Hang
直接放入：

“避免训练”。


应单独写：

“Max Hang：
若恢复间隔足够且热身后手指状态正常，
可考虑降低总量进行；
否则暂缓。”


如果Repeaters没有明确高风险证据，

不得把Repeaters放入：

“避免训练”。


应写：

“Repeaters：
如进行，建议降低强度或总量，
并根据热身后的手指状态调整。”


“避免训练”中只允许放入
当前数据有明确依据需要避免的训练。


==============================
十、最终优先级
==============================

最终训练结论必须按照以下优先级：

1. 明确疼痛、伤病或动作受限；

2. 明确高局部疲劳；

3. recovery_after；

4. 当前Recovery、HRV、静息心率和睡眠；

5. 恢复间隔；

6. 热身后主观状态；

7. 最近7天训练频率。


最近7天训练频率
只能作为辅助背景信息，

不得覆盖：

当前恢复指标、
最近一次局部疲劳、
recovery_after

所支持的训练结论。


最终输出前必须检查：

如果手指疲劳仅为4-6/10，
且没有其他明确高风险证据，

不得因为“中等局部手指疲劳”
自动生成：

“避免Max Hang”
“避免Repeaters”。

必须按照本节规则
重新判断并使用条件式表达。

==============================
WHOOP日期与因果表达规则
==============================

如果数据没有明确提供：

sleep_start
sleep_end
sleep_cycle_date
准确训练与恢复时间关系

不得写：

“昨晚恢复质量很好”
“昨晚睡眠让今天Recovery提高”
“身体已经从之前训练负荷中恢复”

等确定因果表达。

应优先写：

“当前Recovery、HRV和静息心率共同支持整体恢复状态良好。”

“这些指标与当前较好的恢复状态一致。”

“近期恢复指标呈改善趋势。”

不得把相关性自动写成因果关系。


==============================
训练建议一致性
==============================

训练建议必须使用输入中提供的：

当前 Strain
目标 Strain
训练完成度
剩余建议负荷

不得自行重新计算其他目标范围。

如果后端已有明确 training_advice
或 risk_warning，

不得生成与其相反或更严重的结论。



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

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )


        # =========================
        # 最近7天指力板负荷
        # =========================

        cursor.execute(
            """
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
            """
        )

        hangboard = cursor.fetchone()


        if hangboard is None:

            hangboard = {
                "sessions": 0,
                "total_duration": 0,
                "total_hang_time": 0,
                "avg_fatigue": 0,
                "avg_elbow_fatigue": 0
            }

        elif not isinstance(
            hangboard,
            dict
        ):

            hangboard = dict(
                hangboard
            )


        # =========================
        # 最近一次指力板
        # =========================

        cursor.execute(
            """
            SELECT
                training_date,
                protocol,
                session_type,
                finger_fatigue,
                elbow_fatigue,
                recovery_after

            FROM hangboard_training_log

            ORDER BY
                training_date::date DESC,
                created_at DESC

            LIMIT 1
            """
        )

        latest_hangboard = (
            cursor.fetchone()
        )


        if latest_hangboard is None:

            latest_hangboard = {
                "training_date": None,
                "protocol": None,
                "session_type": None,
                "finger_fatigue": 0,
                "elbow_fatigue": 0,
                "recovery_after": None
            }

        elif not isinstance(
            latest_hangboard,
            dict
        ):

            latest_hangboard = dict(
                latest_hangboard
            )


        # =========================
        # 距离最近一次指力板天数
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

            days_row = (
                cursor.fetchone()
            )


            if days_row:

                days_since_hangboard = (
                    days_row[
                        "days_since"
                    ]
                )


        # =========================
        # 最近7天攀岩负荷
        # =========================

        cursor.execute(
            """
            SELECT
                COUNT(*) AS sessions,

                COALESCE(
                    SUM(duration),
                    0
                ) AS total_duration

            FROM climbing_training_log

            WHERE training_date::date
            >= CURRENT_DATE - INTERVAL '7 days'
            """
        )

        climbing = (
            cursor.fetchone()
        )


        if climbing is None:

            climbing = {
                "sessions": 0,
                "total_duration": 0
            }

        elif not isinstance(
            climbing,
            dict
        ):

            climbing = dict(
                climbing
            )


        # =========================
        # 今天指力板训练
        # =========================

        cursor.execute(
            """
            SELECT
                training_date,
                protocol,
                session_type,
                duration,
                total_hang_time,
                finger_fatigue,
                elbow_fatigue,
                recovery_after

            FROM hangboard_training_log

            WHERE training_date::date
            = CURRENT_DATE

            ORDER BY created_at ASC
            """
        )

        today_hangboard_rows = (
            cursor.fetchall()
            or []
        )


        today_hangboard_rows = [
            dict(row)
            if not isinstance(
                row,
                dict
            )
            else row
            for row in today_hangboard_rows
        ]


        # =========================
        # 今天攀岩训练
        # =========================

        cursor.execute(
            """
            SELECT
                training_date,
                training_type,
                duration,
                intensity,
                climbing_grade,
                boulder_count,
                finger_fatigue,
                forearm_fatigue,
                notes

            FROM climbing_training_log

            WHERE training_date::date
            = CURRENT_DATE
            """
        )

        today_climbing_rows = (
            cursor.fetchall()
            or []
        )


        today_climbing_rows = [
            dict(row)
            if not isinstance(
                row,
                dict
            )
            else row
            for row in today_climbing_rows
        ]


        # =========================
        # 今日指力板汇总
        # =========================

        today_hangboard_sessions = (
            len(
                today_hangboard_rows
            )
        )


        today_hangboard_duration = sum(

            float(
                row.get(
                    "duration"
                )
                or 0
            )

            for row
            in today_hangboard_rows
        )


        today_hang_time = sum(

            float(
                row.get(
                    "total_hang_time"
                )
                or 0
            )

            for row
            in today_hangboard_rows
        )


        today_hangboard_protocols = [

            str(
                row.get(
                    "protocol"
                )
            )

            for row
            in today_hangboard_rows

            if row.get(
                "protocol"
            )
        ]


        today_hangboard_finger_values = [

            float(
                row.get(
                    "finger_fatigue"
                )
            )

            for row
            in today_hangboard_rows

            if row.get(
                "finger_fatigue"
            ) is not None
        ]


        today_hangboard_elbow_values = [

            float(
                row.get(
                    "elbow_fatigue"
                )
            )

            for row
            in today_hangboard_rows

            if row.get(
                "elbow_fatigue"
            ) is not None
        ]


        today_recovery_after_values = [

            float(
                row.get(
                    "recovery_after"
                )
            )

            for row
            in today_hangboard_rows

            if row.get(
                "recovery_after"
            ) is not None
        ]


        # =========================
        # 今日攀岩汇总
        # =========================

        today_climbing_sessions = (
            len(
                today_climbing_rows
            )
        )


        today_climbing_duration = sum(

            float(
                row.get(
                    "duration"
                )
                or 0
            )

            for row
            in today_climbing_rows
        )


        today_climbing_types = [

            str(
                row.get(
                    "training_type"
                )
            )

            for row
            in today_climbing_rows

            if row.get(
                "training_type"
            )
        ]


        today_climbing_finger_values = [

            float(
                row.get(
                    "finger_fatigue"
                )
            )

            for row
            in today_climbing_rows

            if row.get(
                "finger_fatigue"
            ) is not None
        ]


        today_forearm_values = [

            float(
                row.get(
                    "forearm_fatigue"
                )
            )

            for row
            in today_climbing_rows

            if row.get(
                "forearm_fatigue"
            ) is not None
        ]


        # =========================
        # 今日综合局部状态
        # =========================

        today_all_finger_values = (
            today_hangboard_finger_values
            +
            today_climbing_finger_values
        )


        today_max_finger_fatigue = (
            max(
                today_all_finger_values
            )
            if today_all_finger_values
            else None
        )


        today_max_elbow_fatigue = (
            max(
                today_hangboard_elbow_values
            )
            if today_hangboard_elbow_values
            else None
        )


        today_max_forearm_fatigue = (
            max(
                today_forearm_values
            )
            if today_forearm_values
            else None
        )


        today_latest_recovery_after = (
            today_recovery_after_values[-1]
            if today_recovery_after_values
            else None
        )


        # =========================
        # 今天是否已训练
        # =========================

        climbing_done_today = (
            today_climbing_sessions > 0
        )

        hangboard_done_today = (
            today_hangboard_sessions > 0
        )

        trained_today = (
            climbing_done_today
            or hangboard_done_today
        )


        # =========================
        # 今日是否已做特殊协议
        # =========================

        normalized_protocols = [

            protocol
            .strip()
            .lower()

            for protocol
            in today_hangboard_protocols
        ]


        max_hang_done_today = any(

            "max hang" in protocol
            or "maxhang" in protocol

            for protocol
            in normalized_protocols
        )


        repeaters_done_today = any(

            "repeater" in protocol

            for protocol
            in normalized_protocols
        )


        # =========================
        # 今日训练摘要
        # =========================

        today_training_summary = []


        for protocol in today_hangboard_protocols:

            today_training_summary.append(
                f"指力板：{protocol}"
            )


        for row in today_climbing_rows:

            training_type = (
                row.get(
                    "training_type"
                )
                or "攀岩"
            )

            duration = (
                row.get(
                    "duration"
                )
            )


            if duration is not None:

                today_training_summary.append(
                    f"{training_type}：{duration}分钟"
                )

            else:

                today_training_summary.append(
                    str(
                        training_type
                    )
                )


        # =========================
        # DEBUG
        # =========================

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

        print(
            "DEBUG TODAY HANGBOARD:",
            today_hangboard_rows
        )

        print(
            "DEBUG TODAY CLIMBING:",
            today_climbing_rows
        )

        print(
            "DEBUG TODAY TRAINING SUMMARY:",
            today_training_summary
        )


        # =========================
        # 返回
        # =========================

        return {

            # =====================
            # 最近7天指力板
            # =====================

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
                    )
                    or 0
                ),

            "avg_elbow_fatigue_7d":
                float(
                    hangboard.get(
                        "avg_elbow_fatigue",
                        0
                    )
                    or 0
                ),


            # =====================
            # 最近一次指力板
            # =====================

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
                )
                or 0,

            "latest_elbow_fatigue":
                latest_hangboard.get(
                    "elbow_fatigue",
                    0
                )
                or 0,

            "latest_recovery_after":
                latest_hangboard.get(
                    "recovery_after"
                ),

            "days_since_hangboard":
                days_since_hangboard,


            # =====================
            # 最近7天攀岩
            # =====================

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


            # =====================
            # 今天是否训练
            # =====================

            "trained_today":
                trained_today,

            "climbing_done_today":
                climbing_done_today,

            "hangboard_done_today":
                hangboard_done_today,

            "max_hang_done_today":
                max_hang_done_today,

            "repeaters_done_today":
                repeaters_done_today,


            # =====================
            # 今天指力板
            # =====================

            "today_hangboard_sessions":
                today_hangboard_sessions,

            "today_hangboard_duration":
                round(
                    today_hangboard_duration,
                    1
                ),

            "today_hang_time":
                round(
                    today_hang_time,
                    1
                ),

            "today_hangboard_protocols":
                today_hangboard_protocols,


            # =====================
            # 今天攀岩
            # =====================

            "today_climbing_sessions":
                today_climbing_sessions,

            "today_climbing_duration":
                round(
                    today_climbing_duration,
                    1
                ),

            "today_climbing_types":
                today_climbing_types,


            # =====================
            # 今日局部反馈
            # =====================

            "today_max_finger_fatigue":
                today_max_finger_fatigue,

            "today_max_elbow_fatigue":
                today_max_elbow_fatigue,

            "today_max_forearm_fatigue":
                today_max_forearm_fatigue,

            "today_latest_recovery_after":
                today_latest_recovery_after,


            # =====================
            # 今日训练摘要
            # =====================

            "today_training_summary":
                today_training_summary,


            # =====================
            # 旧字段兼容
            # =====================

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
                )
                or 0,

            "elbow_fatigue":
                latest_hangboard.get(
                    "elbow_fatigue",
                    0
                )
                or 0,

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


    except Exception as e:

        import traceback

        print(
            "CALCULATE TRAINING LOAD ERROR:",
            repr(
                e
            )
        )

        traceback.print_exc()

        raise


    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()



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
    training_advice,
    risk_warning,
    menstrual_data,
    temperature_data,
    injury_data,
    max_hang_status,
    max_hang_decision,
    strain_plan,
    training_readiness
):

    import json

    conn = None
    cursor = None


    try:

        # =========================
        # 类型保护
        # =========================

        if not isinstance(metrics, dict):
            metrics = {}

        if not isinstance(training_load, dict):
            training_load = {}


        if not isinstance(
            max_hang_decision,
            dict
        ):

            max_hang_decision = {

                "status":
                    max_hang_status
                    or "conditional"

            }


        if not isinstance(
            strain_plan,
            dict
        ):

            strain_plan = (
                calculate_strain_plan(
                    metrics
                )
            )


        if not isinstance(
            training_readiness,
            dict
        ):

            training_readiness = {}


        # =========================
        # 数据库
        # =========================

        conn = get_db_connection()

        cursor = conn.cursor()


        report_date = (
            datetime.now()
            .strftime("%Y-%m-%d")
        )


        # =========================
        # None保护
        # =========================

        ai_report = (
            ai_report
            or ""
        )

        training_advice = (
            training_advice
            or ""
        )

        risk_warning = (
            risk_warning
            or ""
        )


        max_hang_status = (
            max_hang_status
            or max_hang_decision.get(
                "status",
                "conditional"
            )
        )


        # =========================
        # DEBUG
        # =========================

        print(
            "SAVE DATE:",
            report_date
        )

        print(
            "SAVE MAX HANG STATUS:",
            max_hang_status
        )

        print(
            "SAVE MAX HANG DECISION:",
            max_hang_decision
        )

        print(
            "SAVE STRAIN PLAN:",
            strain_plan
        )

        print(
            "SAVE TRAINING READINESS:",
            training_readiness
        )


        # =========================
        # 保存
        # =========================

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
                injury_data,
                max_hang_status,
                max_hang_decision,
                strain_plan,
                training_readiness
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s::jsonb,
                %s::jsonb
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
                    EXCLUDED.injury_data,

                max_hang_status =
                    EXCLUDED.max_hang_status,

                max_hang_decision =
                    EXCLUDED.max_hang_decision,

                strain_plan =
                    EXCLUDED.strain_plan,

                training_readiness =
                    EXCLUDED.training_readiness
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
                    training_load.get(
                        "climbing_duration_7d",
                        0
                    )
                ),

                training_load.get(
                    "hangboard_duration",
                    training_load.get(
                        "hangboard_duration_7d",
                        0
                    )
                ),

                training_load.get(
                    "latest_finger_fatigue",
                    training_load.get(
                        "finger_fatigue",
                        0
                    )
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
                ),

                max_hang_status,

                json.dumps(
                    max_hang_decision,
                    ensure_ascii=False
                ),

                json.dumps(
                    strain_plan,
                    ensure_ascii=False
                ),

                json.dumps(
                    training_readiness,
                    ensure_ascii=False
                )
            )
        )


        conn.commit()


        print(
            "DAILY COACH REPORT SAVED"
        )

        print(
            "SAVED MAX HANG STATUS:",
            max_hang_status
        )

        print(
            "SAVED MAX HANG DECISION:",
            max_hang_decision
        )

        print(
            "SAVED STRAIN PLAN:",
            strain_plan
        )

        print(
            "SAVED TRAINING READINESS:",
            training_readiness
        )


        return True


    except Exception as e:

        print(
            "SAVE DAILY COACH REPORT ERROR:",
            e
        )

        if conn:

            conn.rollback()


        return False


    finally:

        if cursor:

            cursor.close()


        if conn:

            conn.close()


def calculate_max_hang_decision(
    metrics,
    training_load,
    weekly_data,
    injury_data=None
):

    # =========================
    # 类型保护
    # =========================

    if not isinstance(metrics, dict):
        metrics = {}

    if not isinstance(training_load, dict):
        training_load = {}

    if not isinstance(weekly_data, dict):
        weekly_data = {}

    if injury_data is None:
        injury_data = []


    print(
        "MAX HANG FUNCTION INPUT TYPES:",
        type(metrics),
        type(training_load),
        type(weekly_data),
        type(injury_data)
    )


    # =========================
    # 当前 WHOOP
    # =========================

    recovery = metrics.get(
        "recovery_score"
    )

    hrv = metrics.get(
        "hrv"
    )

    rhr = metrics.get(
        "resting_heart_rate"
    )

    sleep = metrics.get(
        "sleep_duration"
    )


    # =========================
    # 近期基线
    # =========================

    avg_hrv = weekly_data.get(
        "avg_hrv"
    )

    avg_rhr = weekly_data.get(
        "avg_resting_hr"
    )

    avg_sleep = weekly_data.get(
        "avg_sleep"
    )


    # =========================
    # 最近一次指力板
    # =========================

    finger_fatigue = training_load.get(
        "latest_finger_fatigue"
    )

    elbow_fatigue = training_load.get(
        "latest_elbow_fatigue"
    )

    recovery_after = training_load.get(
        "latest_recovery_after"
    )

    days_since_hangboard = training_load.get(
        "days_since_hangboard"
    )

    latest_hangboard_date = training_load.get(
        "latest_hangboard_date"
    )


    # =========================
    # 恢复状态
    # =========================

    recovery_green = (
        recovery is not None
        and recovery >= 67
    )

    recovery_yellow = (
        recovery is not None
        and 34 <= recovery < 67
    )

    recovery_red = (
        recovery is not None
        and recovery < 34
    )


    hrv_supportive = (
        hrv is not None
        and avg_hrv is not None
        and hrv >= avg_hrv
    )


    rhr_supportive = (
        rhr is not None
        and avg_rhr is not None
        and rhr <= avg_rhr
    )


    sleep_supportive = (
        sleep is not None
        and avg_sleep is not None
        and sleep >= avg_sleep * 0.85
    )


    recovery_after_good = (
        recovery_after is not None
        and recovery_after >= 75
    )


    low_finger_fatigue = (
        finger_fatigue is not None
        and finger_fatigue <= 3
    )


    moderate_finger_fatigue = (
        finger_fatigue is not None
        and 4 <= finger_fatigue <= 6
    )


    high_finger_fatigue = (
        finger_fatigue is not None
        and finger_fatigue >= 7
    )


    # =========================
    # 默认
    # =========================

    status = "conditional"

    reasons = []

    allowed_if = []

    avoid_if = [
        "手指疲劳达到7/10或以上",
        "训练后恢复评分明显偏低",
        "出现明确疼痛、僵硬、肌腱敏感、肿胀或动作受限",
        "Recovery进入红色区间并伴随其他恢复异常",
        "多项恢复指标持续恶化"
    ]

    volume_adjustment = (
        "首次恢复Max Hang建议降低总量，"
        "可减少组数、总悬挂时间或附加重量，"
        "并增加组间休息。"
    )


    # =========================
    # 明确 avoid
    # =========================

    if high_finger_fatigue:

        status = "avoid"

        reasons.append(
            f"最近一次手指疲劳为{finger_fatigue}/10，"
            "属于明显或高局部疲劳。"
        )


    if (
        recovery_after is not None
        and recovery_after < 75
    ):

        status = "avoid"

        reasons.append(
            f"训练后恢复评分为{recovery_after}，"
            "低于Max Hang恢复条件。"
        )


    if recovery_red:

        status = "avoid"

        reasons.append(
            f"当前Recovery为{recovery}%，"
            "处于红色恢复区间。"
        )


    # =========================
    # conditional 分析
    # =========================

    if status != "avoid":

        if recovery_green:

            reasons.append(
                f"Recovery为{recovery}%，"
                "处于绿色恢复区间。"
            )

        elif recovery_yellow:

            reasons.append(
                f"Recovery为{recovery}%，"
                "处于黄色恢复区间，"
                "Max Hang需要条件式评估。"
            )

            allowed_if.append(
                "当天整体恢复状态足够支持高强度最大力量训练"
            )

        else:

            reasons.append(
                "Recovery数据不足。"
            )

            allowed_if.append(
                "确认当天整体恢复状态"
            )


        if hrv_supportive:

            reasons.append(
                "HRV未低于近期个人平均。"
            )

        else:

            if (
                hrv is not None
                and avg_hrv is not None
            ):

                reasons.append(
                    f"HRV为{round(hrv, 2)}ms，"
                    f"近期平均为{round(avg_hrv, 2)}ms。"
                )

            else:

                reasons.append(
                    "HRV近期基线数据不足。"
                )

            allowed_if.append(
                "HRV稳定或回升至不明显低于近期个人基线"
            )


        if rhr_supportive:

            reasons.append(
                "静息心率未高于近期个人平均。"
            )

        else:

            if (
                rhr is not None
                and avg_rhr is not None
            ):

                reasons.append(
                    f"静息心率为{round(rhr, 1)}bpm，"
                    f"近期平均为{round(avg_rhr, 1)}bpm。"
                )

            else:

                reasons.append(
                    "静息心率近期基线数据不足。"
                )

            allowed_if.append(
                "静息心率没有明显高于近期个人基线"
            )


        if sleep_supportive:

            reasons.append(
                "睡眠时长未明显低于近期个人平均。"
            )

        else:

            if (
                sleep is not None
                and avg_sleep is not None
            ):

                reasons.append(
                    f"睡眠为{round(sleep, 2)}小时，"
                    f"近期平均为{round(avg_sleep, 2)}小时。"
                )

            else:

                reasons.append(
                    "睡眠近期基线数据不足。"
                )

            allowed_if.append(
                "睡眠和主观恢复状态足够支持高强度训练"
            )


        if low_finger_fatigue:

            reasons.append(
                f"最近一次手指疲劳为{finger_fatigue}/10，"
                "属于低局部疲劳。"
            )

        elif moderate_finger_fatigue:

            reasons.append(
                f"最近一次手指疲劳为{finger_fatigue}/10，"
                "属于中等局部手指疲劳。"
            )

            allowed_if.append(
                "热身后手指主观状态正常"
            )

        elif finger_fatigue is None:

            reasons.append(
                "最近一次手指疲劳数据缺失。"
            )

            allowed_if.append(
                "热身后确认手指状态正常"
            )


        if recovery_after_good:

            reasons.append(
                f"训练后恢复评分为{recovery_after}，"
                "支持局部恢复。"
            )

        elif recovery_after is None:

            reasons.append(
                "训练后恢复评分数据缺失。"
            )

            allowed_if.append(
                "确认局部恢复状态良好"
            )


        if days_since_hangboard is not None:

            reasons.append(
                f"距离最近一次指力板训练约"
                f"{days_since_hangboard}个自然日。"
            )

        else:

            reasons.append(
                "最近一次指力板训练间隔数据不足。"
            )


        allowed_if.append(
            "确认距离上次高强度指力训练的实际恢复间隔足够"
        )


        if (
            "热身后手指主观状态正常"
            not in allowed_if
        ):

            allowed_if.append(
                "热身后手指主观状态正常"
            )


    # =========================
    # 状态文案
    # =========================

    if status == "avoid":

        status_label = (
            "当前数据支持暂缓Max Hang"
        )

        instruction = (
            "当前存在明确限制因素，"
            "建议暂缓Max Hang，"
            "优先进行低至中等强度训练或恢复。"
        )

    elif status == "allowed":

        status_label = (
            "当前数据支持进行Max Hang"
        )

        instruction = (
            "当前条件支持进行Max Hang，"
            "仍应根据热身后的手指状态"
            "动态调整训练量。"
        )

    else:

        status_label = (
            "条件式评估Max Hang"
        )

        instruction = (
            "如果恢复间隔足够，"
            "且热身后手指状态正常，"
            "可以考虑降低总量进行Max Hang；"
            "否则暂缓。"
        )


    result = {

        "status":
            status,

        "status_label":
            status_label,

        "instruction":
            instruction,

        "reason":
            " ".join(reasons),

        "allowed_if":
            list(
                dict.fromkeys(
                    allowed_if
                )
            ),

        "avoid_if":
            avoid_if,

        "volume_adjustment":
            volume_adjustment,

        "finger_fatigue":
            finger_fatigue,

        "elbow_fatigue":
            elbow_fatigue,

        "recovery_after":
            recovery_after,

        "days_since_hangboard":
            days_since_hangboard,

        "latest_hangboard_date":
            latest_hangboard_date

    }


    print(
        "MAX HANG DECISION:",
        result
    )


    return result



# =========================
# 兼容旧调用
# =========================

def calculate_max_hang_status(
    metrics,
    training_load,
    weekly_data,
    injury_data=None
):

    decision = calculate_max_hang_decision(
        metrics,
        training_load,
        weekly_data,
        injury_data
    )

    return decision.get(
        "status",
        "conditional"
    )


def calculate_strain_plan(
    metrics
):

    # =========================
    # 类型保护
    # =========================

    if not isinstance(metrics, dict):
        metrics = {}


    recovery = metrics.get(
        "recovery_score"
    )

    cycle_strain = metrics.get(
        "cycle_strain"
    )


    # =========================
    # 当前 Strain
    # =========================

    try:

        current_strain = (
            float(cycle_strain)
            if cycle_strain is not None
            else 0.0
        )

    except Exception:

        current_strain = 0.0


    # =========================
    # Recovery → Strain区间
    # =========================

    if recovery is None:

        target_min = 0

        target_max = 0

        training_level = (
            "数据不足"
        )


    elif float(recovery) >= 67:

        target_min = 12

        target_max = 16

        training_level = (
            "中高强度训练候选"
        )


    elif float(recovery) >= 34:

        target_min = 8

        target_max = 12

        training_level = (
            "低至中等强度"
        )


    else:

        target_min = 0

        target_max = 8

        training_level = (
            "恢复优先"
        )


    # =========================
    # 推荐区间
    # =========================

    recommended_strain = (
        f"{target_min}-{target_max}"
    )


    # =========================
    # 完成度 / 剩余建议负荷
    # =========================

    if target_min > 0:

        strain_completion = round(
            current_strain
            / target_min
            * 100,
            1
        )

        remaining_strain = round(
            max(
                target_min
                - current_strain,
                0
            ),
            1
        )


    else:

        strain_completion = 100.0

        remaining_strain = 0.0


    # =========================
    # 返回统一结构
    # =========================

    result = {

        "current_strain":
            round(
                current_strain,
                2
            ),

        "target_min":
            target_min,

        "target_max":
            target_max,

        "recommended_strain":
            recommended_strain,

        "strain_completion":
            strain_completion,

        "remaining_strain":
            remaining_strain,

        "training_level":
            training_level,

        "remaining_strain_explanation":
            (
                "remaining_strain表示距离推荐Strain区间下限的差值，"
                "不代表今天绝对训练上限。"
            )

    }


    print(
        "STRAIN PLAN:",
        result
    )


    return result


def calculate_training_readiness(
    metrics,
    training_load,
    weekly_data,
    strain_plan,
    max_hang_decision,
    injury_data=None
):

    # =========================
    # 类型保护
    # =========================

    if not isinstance(metrics, dict):
        metrics = {}

    if not isinstance(training_load, dict):
        training_load = {}

    if not isinstance(weekly_data, dict):
        weekly_data = {}

    if not isinstance(strain_plan, dict):
        strain_plan = {}

    if not isinstance(max_hang_decision, dict):
        max_hang_decision = {}

    if injury_data is None:
        injury_data = []


    # =========================
    # WHOOP 当前状态
    # =========================

    recovery = metrics.get(
        "recovery_score"
    )

    hrv = metrics.get(
        "hrv"
    )

    rhr = metrics.get(
        "resting_heart_rate"
    )

    sleep = metrics.get(
        "sleep_duration"
    )


    # =========================
    # 近期基线
    # =========================

    avg_hrv = weekly_data.get(
        "avg_hrv"
    )

    avg_rhr = weekly_data.get(
        "avg_resting_hr"
    )

    avg_sleep = weekly_data.get(
        "avg_sleep"
    )


    # =========================
    # 最近一次指力板局部状态
    # =========================

    finger_fatigue = training_load.get(
        "latest_finger_fatigue"
    )

    elbow_fatigue = training_load.get(
        "latest_elbow_fatigue"
    )

    recovery_after = training_load.get(
        "latest_recovery_after"
    )

    days_since_hangboard = training_load.get(
        "days_since_hangboard"
    )


    # =========================
    # 今天已经完成的训练
    # =========================

    trained_today = bool(
        training_load.get(
            "trained_today",
            False
        )
    )

    climbing_done_today = bool(
        training_load.get(
            "climbing_done_today",
            False
        )
    )

    hangboard_done_today = bool(
        training_load.get(
            "hangboard_done_today",
            False
        )
    )

    max_hang_done_today = bool(
        training_load.get(
            "max_hang_done_today",
            False
        )
    )

    repeaters_done_today = bool(
        training_load.get(
            "repeaters_done_today",
            False
        )
    )


    today_climbing_sessions = (
        training_load.get(
            "today_climbing_sessions",
            0
        )
        or 0
    )

    today_climbing_duration = (
        training_load.get(
            "today_climbing_duration",
            0
        )
        or 0
    )

    today_hangboard_sessions = (
        training_load.get(
            "today_hangboard_sessions",
            0
        )
        or 0
    )

    today_hangboard_duration = (
        training_load.get(
            "today_hangboard_duration",
            0
        )
        or 0
    )

    today_hang_time = (
        training_load.get(
            "today_hang_time",
            0
        )
        or 0
    )


    today_training_summary = (
        training_load.get(
            "today_training_summary",
            []
        )
    )

    if not isinstance(
        today_training_summary,
        list
    ):
        today_training_summary = []


    today_max_finger_fatigue = (
        training_load.get(
            "today_max_finger_fatigue"
        )
    )

    today_max_elbow_fatigue = (
        training_load.get(
            "today_max_elbow_fatigue"
        )
    )

    today_max_forearm_fatigue = (
        training_load.get(
            "today_max_forearm_fatigue"
        )
    )

    today_latest_recovery_after = (
        training_load.get(
            "today_latest_recovery_after"
        )
    )


    # =========================
    # Strain Plan
    # =========================

    current_strain = strain_plan.get(
        "current_strain"
    )

    recommended_strain = strain_plan.get(
        "recommended_strain"
    )

    strain_completion = strain_plan.get(
        "strain_completion"
    )

    remaining_strain = strain_plan.get(
        "remaining_strain"
    )


    # =========================
    # Max Hang 专项决策
    # =========================

    max_hang_status = (
        max_hang_decision.get(
            "status",
            "conditional"
        )
    )

    max_hang_status_label = (
        max_hang_decision.get(
            "status_label",
            ""
        )
    )

    max_hang_instruction = (
        max_hang_decision.get(
            "instruction",
            ""
        )
    )


    # =========================
    # Recovery 状态
    # =========================

    if recovery is None:

        recovery_state = (
            "unknown"
        )

    elif recovery >= 67:

        recovery_state = (
            "green"
        )

    elif recovery >= 34:

        recovery_state = (
            "yellow"
        )

    else:

        recovery_state = (
            "red"
        )


    # =========================
    # HRV 状态
    # =========================

    if (
        hrv is None
        or avg_hrv is None
    ):

        hrv_state = (
            "unknown"
        )

    elif hrv >= avg_hrv:

        hrv_state = (
            "supportive"
        )

    else:

        hrv_state = (
            "below_baseline"
        )


    # =========================
    # 静息心率状态
    # =========================

    if (
        rhr is None
        or avg_rhr is None
    ):

        rhr_state = (
            "unknown"
        )

    elif rhr <= avg_rhr:

        rhr_state = (
            "supportive"
        )

    else:

        rhr_state = (
            "above_baseline"
        )


    # =========================
    # 睡眠状态
    # =========================

    if (
        sleep is None
        or avg_sleep is None
    ):

        sleep_state = (
            "unknown"
        )

    elif sleep >= avg_sleep * 0.85:

        sleep_state = (
            "supportive"
        )

    else:

        sleep_state = (
            "below_baseline"
        )


    # =========================
    # 今日训练后反馈优先
    # =========================

    effective_finger_fatigue = (
        today_max_finger_fatigue
        if today_max_finger_fatigue is not None
        else finger_fatigue
    )

    effective_elbow_fatigue = (
        today_max_elbow_fatigue
        if today_max_elbow_fatigue is not None
        else elbow_fatigue
    )

    effective_recovery_after = (
        today_latest_recovery_after
        if today_latest_recovery_after is not None
        else recovery_after
    )


    # =========================
    # 手指状态
    # =========================

    if effective_finger_fatigue is None:

        finger_status = (
            "unknown"
        )

    elif effective_finger_fatigue <= 3:

        finger_status = (
            "low_fatigue"
        )

    elif effective_finger_fatigue <= 6:

        finger_status = (
            "moderate_fatigue"
        )

    else:

        finger_status = (
            "high_fatigue"
        )


    # =========================
    # 肘部状态
    # =========================

    if effective_elbow_fatigue is None:

        elbow_status = (
            "unknown"
        )

    elif effective_elbow_fatigue <= 3:

        elbow_status = (
            "low_fatigue"
        )

    elif effective_elbow_fatigue <= 5:

        elbow_status = (
            "moderate_fatigue"
        )

    else:

        elbow_status = (
            "high_fatigue"
        )


    # =========================
    # 前臂状态
    # =========================

    if today_max_forearm_fatigue is None:

        forearm_status = (
            "unknown"
        )

    elif today_max_forearm_fatigue <= 3:

        forearm_status = (
            "low_fatigue"
        )

    elif today_max_forearm_fatigue <= 6:

        forearm_status = (
            "moderate_fatigue"
        )

    else:

        forearm_status = (
            "high_fatigue"
        )


    # =========================
    # 全身恢复
    # =========================

    systemic_negative_count = 0


    if hrv_state == "below_baseline":

        systemic_negative_count += 1


    if rhr_state == "above_baseline":

        systemic_negative_count += 1


    if sleep_state == "below_baseline":

        systemic_negative_count += 1


    if recovery_state == "red":

        systemic_recovery = (
            "poor"
        )

    elif (
        recovery_state == "green"
        and systemic_negative_count == 0
    ):

        systemic_recovery = (
            "good"
        )

    elif (
        recovery_state in [
            "green",
            "yellow"
        ]
        and systemic_negative_count <= 1
    ):

        systemic_recovery = (
            "moderate"
        )

    elif recovery_state == "unknown":

        systemic_recovery = (
            "unknown"
        )

    else:

        systemic_recovery = (
            "limited"
        )


    # =========================
    # 伤病记录
    # =========================

    injury_recorded = bool(
        injury_data
    )


    # =========================
    # 主要限制因素
    # =========================

    primary_limiter = (
        "none_identified"
    )


    if systemic_recovery in [
        "poor",
        "limited"
    ]:

        primary_limiter = (
            "systemic_recovery"
        )

    elif finger_status == "high_fatigue":

        primary_limiter = (
            "finger_fatigue"
        )

    elif elbow_status == "high_fatigue":

        primary_limiter = (
            "elbow_fatigue"
        )

    elif forearm_status == "high_fatigue":

        primary_limiter = (
            "forearm_fatigue"
        )

    elif finger_status == "moderate_fatigue":

        primary_limiter = (
            "finger_fatigue"
        )

    elif elbow_status == "moderate_fatigue":

        primary_limiter = (
            "elbow_fatigue"
        )

    elif forearm_status == "moderate_fatigue":

        primary_limiter = (
            "forearm_fatigue"
        )

    elif injury_recorded:

        primary_limiter = (
            "injury_record_review"
        )


    # =========================
    # Overall Status
    # =========================

    if (
        systemic_recovery == "poor"
        or finger_status == "high_fatigue"
        or elbow_status == "high_fatigue"
        or forearm_status == "high_fatigue"
    ):

        overall_status = (
            "recovery_priority"
        )

    elif (
        systemic_recovery in [
            "limited",
            "moderate",
            "unknown"
        ]
        or finger_status == "moderate_fatigue"
        or elbow_status == "moderate_fatigue"
        or forearm_status == "moderate_fatigue"
        or max_hang_status == "conditional"
    ):

        overall_status = (
            "conditional"
        )

    else:

        overall_status = (
            "ready"
        )


    # =========================
    # 状态标签
    # =========================

    if overall_status == "ready":

        overall_label = (
            "训练准备度良好"
        )

    elif overall_status == "recovery_priority":

        overall_label = (
            "恢复优先"
        )

    else:

        overall_label = (
            "条件式训练"
        )


    # =========================
    # 训练阶段
    # =========================

    if trained_today:

        training_phase = (
            "post_training"
        )

    else:

        training_phase = (
            "pre_training"
        )


    # =========================
    # 基础推荐训练
    # =========================

    recommended_training = []


    if overall_status == "recovery_priority":

        recommended_training.extend([
            "低强度主动恢复",
            "轻松有氧",
            "活动度训练",
            "低负荷技术练习"
        ])


    elif overall_status == "conditional":

        recommended_training.extend([
            "技术攀岩",
            "中低强度攀岩",
            "基础耐力训练"
        ])


        if finger_status in [
            "low_fatigue",
            "moderate_fatigue"
        ]:

            recommended_training.append(
                "低量或降低强度的Repeaters，可根据热身后手指状态调整"
            )


    else:

        recommended_training.extend([
            "高质量技术攀岩",
            "中等至中高强度攀岩",
            "计划内力量训练"
        ])


        if finger_status == "low_fatigue":

            recommended_training.append(
                "Repeaters可按计划执行，并根据手指状态调整"
            )


    # =========================
    # 基础限制
    # =========================

    avoid_or_limit = []


    if finger_status == "high_fatigue":

        avoid_or_limit.append(
            "高强度指力训练"
        )


    if elbow_status == "high_fatigue":

        avoid_or_limit.append(
            "高负荷拉力与高强度上肢训练"
        )


    if forearm_status == "high_fatigue":

        avoid_or_limit.append(
            "高总量抓握和连续高强度攀爬"
        )


    if systemic_recovery == "poor":

        avoid_or_limit.append(
            "高强度训练和极限尝试"
        )


    elif systemic_recovery == "limited":

        avoid_or_limit.append(
            "高总量或连续高强度训练"
        )


    # =========================
    # Max Hang专项限制
    # =========================

    if max_hang_status == "avoid":

        avoid_or_limit.append(
            "Max Hang"
        )

    elif max_hang_status == "conditional":

        avoid_or_limit.append(
            "Max Hang需满足后端条件后再决定"
        )


    # =========================
    # 日内剩余训练建议
    # =========================

    additional_training = []

    additional_high_intensity = (
        "conditional"
    )


    if not trained_today:

        additional_training = list(
            recommended_training
        )


        if overall_status == "ready":

            additional_high_intensity = (
                "possible"
            )

        elif overall_status == "recovery_priority":

            additional_high_intensity = (
                "not_recommended"
            )


    else:

        additional_training.append(
            "不需要为了达到推荐Strain区间下限而机械追加训练"
        )


        if hangboard_done_today:

            additional_training.append(
                "今天已经完成指力板训练，后续优先观察手指和肘部训练后反应"
            )


        if repeaters_done_today:

            additional_training.append(
                "今天已经完成Repeaters，不建议为了增加训练量再次安排同类指力板刺激"
            )


        if max_hang_done_today:

            additional_training.append(
                "今天已经完成Max Hang，不建议当天再次安排Max Hang"
            )


        if climbing_done_today:

            additional_training.append(
                "今天已经完成攀岩训练，是否继续训练应根据当前局部疲劳和主观状态决定"
            )


        if (
            hangboard_done_today
            and climbing_done_today
        ):

            additional_training.append(
                "今天已同时完成指力板和攀岩训练，后续更适合低强度活动、恢复或结束主要训练"
            )

            additional_high_intensity = (
                "not_recommended"
            )


        elif (
            hangboard_done_today
            or climbing_done_today
        ):

            if (
                finger_status == "low_fatigue"
                and elbow_status == "low_fatigue"
                and forearm_status in [
                    "low_fatigue",
                    "unknown"
                ]
                and systemic_recovery in [
                    "good",
                    "moderate"
                ]
            ):

                additional_training.append(
                    "如果仍想活动，可选择低强度技术练习或轻松恢复活动"
                )

            else:

                additional_training.append(
                    "当前更适合结束主要训练并进入恢复"
                )


            additional_high_intensity = (
                "not_recommended"
            )


    # =========================
    # 今日 Max Hang 行动
    # =========================
    #
    # 注意：
    #
    # max_hang_status
    # = Max Hang专项资格
    #
    # max_hang_today_action
    # = 今天现在还要不要追加
    #
    # 两者不能混为一谈
    # =========================

    if max_hang_done_today:

        max_hang_today_action = (
            "completed_today"
        )

        max_hang_today_label = (
            "今天已经完成Max Hang"
        )

        max_hang_today_instruction = (
            "今天已经完成Max Hang，"
            "不建议当天再次安排Max Hang。"
            "Max Hang专项状态保留用于下一次训练机会重新评估。"
        )


    elif hangboard_done_today:

        max_hang_today_action = (
            "do_not_add_today"
        )

        max_hang_today_label = (
            "今天不再追加Max Hang"
        )

        max_hang_today_instruction = (
            "今天已经完成指力板训练，"
            "不建议为了增加训练量再追加Max Hang。"
            f"当前Max Hang专项状态仍为{max_hang_status}，"
            "该专项状态用于下一次训练机会重新评估，"
            "不代表今天仍需要执行Max Hang。"
        )


    elif climbing_done_today:

        max_hang_today_action = (
            "reassess_before_adding"
        )

        max_hang_today_label = (
            "如考虑Max Hang需重新评估"
        )

        max_hang_today_instruction = (
            "今天已经完成攀岩训练。"
            "如果仍考虑Max Hang，"
            "需结合当前局部疲劳、实际恢复间隔"
            "以及热身后的手指状态重新评估。"
            "不要仅因为Max Hang专项状态允许或条件式允许"
            "就自动追加训练。"
        )


    else:

        if max_hang_status == "allowed":

            max_hang_today_action = (
                "possible_today"
            )

        elif max_hang_status == "avoid":

            max_hang_today_action = (
                "avoid_today"
            )

        else:

            max_hang_today_action = (
                "conditional_today"
            )


        max_hang_today_label = (
            max_hang_status_label
        )

        max_hang_today_instruction = (
            max_hang_instruction
        )


    # =========================
    # 已做项目不再重复推荐
    # =========================

    if trained_today:

        filtered_training = []


        for item in recommended_training:

            item_lower = (
                item.lower()
            )


            if (
                repeaters_done_today
                and "repeaters"
                in item_lower
            ):

                continue


            if (
                climbing_done_today
                and (
                    "技术攀岩" in item
                    or "中低强度攀岩" in item
                    or "高质量技术攀岩" in item
                )
            ):

                continue


            filtered_training.append(
                item
            )


        recommended_training = (
            filtered_training
        )


    # =========================
    # 决策原因
    # =========================

    reasons = []


    if recovery is not None:

        reasons.append(
            f"Recovery为{recovery}%"
        )


    if (
        hrv is not None
        and avg_hrv is not None
    ):

        reasons.append(
            f"HRV为{round(hrv, 2)}ms，"
            f"近期平均为{round(avg_hrv, 2)}ms"
        )


    if (
        rhr is not None
        and avg_rhr is not None
    ):

        reasons.append(
            f"静息心率为{round(rhr, 1)}bpm，"
            f"近期平均为{round(avg_rhr, 1)}bpm"
        )


    if (
        sleep is not None
        and avg_sleep is not None
    ):

        reasons.append(
            f"睡眠为{round(sleep, 2)}小时，"
            f"近期平均为{round(avg_sleep, 2)}小时"
        )


    if effective_finger_fatigue is not None:

        reasons.append(
            f"当前可用手指疲劳信息为"
            f"{effective_finger_fatigue}/10"
        )


    if effective_elbow_fatigue is not None:

        reasons.append(
            f"当前可用肘部疲劳信息为"
            f"{effective_elbow_fatigue}/10"
        )


    if today_max_forearm_fatigue is not None:

        reasons.append(
            f"今日前臂疲劳最高记录为"
            f"{today_max_forearm_fatigue}/10"
        )


    if effective_recovery_after is not None:

        reasons.append(
            f"训练后恢复评分为"
            f"{effective_recovery_after}"
        )


    if trained_today:

        if today_training_summary:

            reasons.append(
                "今天已经完成："
                +
                "、".join(
                    today_training_summary
                )
            )

        else:

            reasons.append(
                "今天已经存在训练记录"
            )


    # =========================
    # 最终结构
    # =========================

    result = {

        "overall_status":
            overall_status,

        "overall_label":
            overall_label,

        "primary_limiter":
            primary_limiter,


        # =====================
        # 全身恢复
        # =====================

        "systemic_recovery":
            systemic_recovery,

        "recovery_state":
            recovery_state,

        "hrv_state":
            hrv_state,

        "rhr_state":
            rhr_state,

        "sleep_state":
            sleep_state,


        # =====================
        # 局部状态
        # =====================

        "finger_status":
            finger_status,

        "finger_fatigue":
            effective_finger_fatigue,

        "elbow_status":
            elbow_status,

        "elbow_fatigue":
            effective_elbow_fatigue,

        "forearm_status":
            forearm_status,

        "forearm_fatigue":
            today_max_forearm_fatigue,

        "recovery_after":
            effective_recovery_after,

        "days_since_hangboard":
            days_since_hangboard,


        # =====================
        # 日内训练
        # =====================

        "training_phase":
            training_phase,

        "trained_today":
            trained_today,

        "climbing_done_today":
            climbing_done_today,

        "hangboard_done_today":
            hangboard_done_today,

        "max_hang_done_today":
            max_hang_done_today,

        "repeaters_done_today":
            repeaters_done_today,

        "today_climbing_sessions":
            today_climbing_sessions,

        "today_climbing_duration":
            today_climbing_duration,

        "today_hangboard_sessions":
            today_hangboard_sessions,

        "today_hangboard_duration":
            today_hangboard_duration,

        "today_hang_time":
            today_hang_time,

        "today_training_summary":
            today_training_summary,


        # =====================
        # 训练建议
        # =====================

        "recommended_training":
            list(
                dict.fromkeys(
                    recommended_training
                )
            ),

        "avoid_or_limit":
            list(
                dict.fromkeys(
                    avoid_or_limit
                )
            ),

        "additional_training":
            list(
                dict.fromkeys(
                    additional_training
                )
            ),

        "additional_high_intensity":
            additional_high_intensity,


        # =====================
        # Max Hang 专项
        # =====================

        "max_hang_status":
            max_hang_status,

        "max_hang_instruction":
            max_hang_instruction,


        # =====================
        # Max Hang 今日行动
        # =====================

        "max_hang_today_action":
            max_hang_today_action,

        "max_hang_today_label":
            max_hang_today_label,

        "max_hang_today_instruction":
            max_hang_today_instruction,


        # =====================
        # Strain
        # =====================

        "current_strain":
            current_strain,

        "recommended_strain":
            recommended_strain,

        "strain_completion":
            strain_completion,

        "remaining_strain":
            remaining_strain,

        "strain_chasing_recommended":
            False
            if trained_today
            else None,


        # =====================
        # 伤病
        # =====================

        "injury_recorded":
            injury_recorded,

        "injury_note":
            (
                "存在伤病记录，需结合记录内容确认当前是否仍有限制。"
                if injury_recorded
                else
                "当前未检测到非空伤病记录。"
            ),


        # =====================
        # 原因
        # =====================

        "reason":
            "；".join(
                reasons
            )

    }


    print(
        "TRAINING READINESS:",
        result
    )


    return result
 
 

def generate_coach_prompt(
    metrics,
    training_load,
    weekly_data,
    climbing_fatigue,
    menstrual_data,
    temperature_data,
    injury_data,
    max_hang_decision=None,
    strain_plan=None,
    training_readiness=None
):

    # =========================
    # 类型保护
    # =========================

    if not isinstance(
        metrics,
        dict
    ):
        metrics = {}

    if not isinstance(
        training_load,
        dict
    ):
        training_load = {}

    if not isinstance(
        weekly_data,
        dict
    ):
        weekly_data = {}

    if not isinstance(
        climbing_fatigue,
        dict
    ):
        climbing_fatigue = {}


    # =========================
    # Max Hang
    # =========================

    if not isinstance(
        max_hang_decision,
        dict
    ):

        max_hang_decision = (
            calculate_max_hang_decision(
                metrics,
                training_load,
                weekly_data,
                injury_data
            )
        )


    max_hang_status = (
        max_hang_decision.get(
            "status",
            "conditional"
        )
    )


    # =========================
    # Strain
    # =========================

    if not isinstance(
        strain_plan,
        dict
    ):

        strain_plan = (
            calculate_strain_plan(
                metrics
            )
        )


    current_strain = (
        strain_plan.get(
            "current_strain"
        )
    )

    recommended_strain = (
        strain_plan.get(
            "recommended_strain"
        )
    )

    strain_completion = (
        strain_plan.get(
            "strain_completion"
        )
    )

    remaining_strain = (
        strain_plan.get(
            "remaining_strain"
        )
    )


    # =========================
    # Training Readiness
    # =========================

    if not isinstance(
        training_readiness,
        dict
    ):

        training_readiness = (
            calculate_training_readiness(
                metrics,
                training_load,
                weekly_data,
                strain_plan,
                max_hang_decision,
                injury_data
            )
        )


    # =========================
    # 日内训练状态
    # =========================

    training_phase = (
        training_readiness.get(
            "training_phase"
        )
    )

    trained_today = (
        training_readiness.get(
            "trained_today"
        )
    )

    today_training_summary = (
        training_readiness.get(
            "today_training_summary",
            []
        )
    )

    additional_training = (
        training_readiness.get(
            "additional_training",
            []
        )
    )

    additional_high_intensity = (
        training_readiness.get(
            "additional_high_intensity"
        )
    )


    # =========================
    # 今日 Max Hang行动
    # =========================

    max_hang_today_action = (
        training_readiness.get(
            "max_hang_today_action"
        )
    )

    max_hang_today_label = (
        training_readiness.get(
            "max_hang_today_label"
        )
    )

    max_hang_today_instruction = (
        training_readiness.get(
            "max_hang_today_instruction"
        )
    )


    # =========================
    # 温度 / SpO2
    # =========================

    skin_temperature = (
        metrics.get(
            "skin_temperature"
        )
    )

    spo2_percentage = (
        metrics.get(
            "spo2_percentage"
        )
    )


    skin_temperature_avg = (
        weekly_data.get(
            "skin_temperature_avg"
        )
    )

    skin_temperature_valid_days = (
        weekly_data.get(
            "skin_temperature_valid_days",
            0
        )
        or 0
    )

    temperature_deviation = (
        weekly_data.get(
            "temperature_deviation"
        )
    )


    spo2_avg = (
        weekly_data.get(
            "spo2_avg"
        )
    )

    spo2_valid_days = (
        weekly_data.get(
            "spo2_valid_days",
            0
        )
        or 0
    )

    spo2_deviation = (
        weekly_data.get(
            "spo2_deviation"
        )
    )


    skin_temperature_text = (
        f"{skin_temperature} °C"
        if skin_temperature is not None
        else "数据缺失"
    )


    spo2_text = (
        f"{spo2_percentage}%"
        if spo2_percentage is not None
        else "数据缺失"
    )


    # =========================
    # 最近一次训练
    # =========================

    latest_finger_fatigue = (
        training_load.get(
            "latest_finger_fatigue"
        )
    )

    latest_elbow_fatigue = (
        training_load.get(
            "latest_elbow_fatigue"
        )
    )

    latest_recovery_after = (
        training_load.get(
            "latest_recovery_after"
        )
    )

    days_since_hangboard = (
        training_load.get(
            "days_since_hangboard"
        )
    )


    # =========================
    # Prompt
    # =========================

    return f"""

你是一名专业的 WHOOP 私人攀岩健康教练。

你的任务是根据今天的 WHOOP 数据、
近期个人基线、攀岩训练、指力板训练、
局部疲劳、今日已经完成的训练、
经期、WHOOP夜间皮肤温度、
SpO₂和伤病记录，

生成谨慎、专业、简洁、可执行的训练建议。


==============================
最重要的数据优先级
==============================

后端已经完成三个核心结构化决策：

1. Training Readiness
2. Strain Plan
3. Max Hang Decision

AI不得自行重新计算、
修改或推翻这些结构化结果。


Training Readiness负责：

今天整体怎么练，
以及今天已经完成训练之后
还适合做什么。


Strain Plan负责：

当前Strain、
推荐区间、
完成度、
remaining_strain。


Max Hang Decision负责：

Max Hang专项资格状态。


此外：

Training Readiness中的
max_hang_today_action
负责：

“今天现在还要不要追加Max Hang”。


必须区分：

Max Hang专项资格

和

今天是否追加Max Hang。


==============================
后端Strain最终决策
==============================

当前Strain：
{current_strain}

目标Strain：
{recommended_strain}

目标下限：
{strain_plan.get("target_min")}

目标上限：
{strain_plan.get("target_max")}

完成度：
{strain_completion}%

距离区间下限：
{remaining_strain}

训练等级：
{strain_plan.get("training_level")}


强制规则：

以上Strain数据为后端最终结果。

不得自行：

修改目标Strain
缩小区间
扩大区间
重新计算完成度
重新计算remaining_strain。


remaining_strain只表示：

距离推荐Strain区间下限的差值。


它不代表：

今天剩余训练额度
今天最多还能增加多少
今天必须补足多少。


如果用户今天已经完成训练：

不得为了达到target_min
而建议机械补Strain。


==============================
Training Readiness
==============================

整体状态：
{training_readiness.get("overall_status")}

状态说明：
{training_readiness.get("overall_label")}

主要限制因素：
{training_readiness.get("primary_limiter")}

全身恢复：
{training_readiness.get("systemic_recovery")}

手指状态：
{training_readiness.get("finger_status")}

肘部状态：
{training_readiness.get("elbow_status")}

前臂状态：
{training_readiness.get("forearm_status")}

推荐训练：
{training_readiness.get("recommended_training")}

限制或避免：
{training_readiness.get("avoid_or_limit")}


AI不得推翻：

overall_status
primary_limiter
recommended_training
avoid_or_limit。


==============================
今日训练阶段
==============================

训练阶段：
{training_phase}

今天是否已经训练：
{trained_today}

今天已经完成：
{today_training_summary}

今日攀岩是否完成：
{training_readiness.get("climbing_done_today")}

今日指力板是否完成：
{training_readiness.get("hangboard_done_today")}

今日Repeaters是否完成：
{training_readiness.get("repeaters_done_today")}

今日Max Hang是否完成：
{training_readiness.get("max_hang_done_today")}


如果：

training_phase = post_training

必须把回答重点从：

“今天适合训练什么”

切换成：

“今天已经完成这些训练后，
现在还适合做什么”。


剩余训练建议：
{additional_training}

额外高强度训练状态：
{additional_high_intensity}


如果：

additional_high_intensity = not_recommended

不得继续推荐：

极限抱石
高强度指力
Max Hang
高强度项目
其他额外高强度训练。


==============================
Max Hang专项资格
==============================

专项状态：
{max_hang_status}

完整专项决策：
{max_hang_decision}


这个状态回答：

“Max Hang这个训练项目本身，
当前属于allowed、
conditional还是avoid？”


AI不得自行改变该专项状态。


==============================
今天是否追加Max Hang
==============================

今日行动：
{max_hang_today_action}

今日标签：
{max_hang_today_label}

今日执行说明：
{max_hang_today_instruction}


这是回答：

“今天现在还应不应该再做一次Max Hang？”


必须优先服从
max_hang_today_action。


例如：

如果专项状态为：

conditional

但今日行动为：

do_not_add_today

必须表达：

“Max Hang专项状态仍是条件式评估，
但今天已经完成指力板训练，
因此今天不再追加Max Hang。
该专项状态留到下一次训练机会重新评估。”


不得错误表达为：

“Max Hang已经变成avoid”。

因为：

专项状态没有改变。


==============================
今日WHOOP
==============================

Recovery：
{metrics.get("recovery_score")}

HRV：
{metrics.get("hrv")} ms

静息心率：
{metrics.get("resting_heart_rate")} bpm

睡眠：
{metrics.get("sleep_duration")} 小时

睡眠评分：
{metrics.get("sleep_score")}

睡眠效率：
{metrics.get("sleep_efficiency")}

深睡：
{metrics.get("deep_sleep_duration")} 小时

REM：
{metrics.get("rem_sleep_duration")} 小时

当前Strain：
{current_strain}


==============================
近期个人基线
==============================

平均Recovery：
{weekly_data.get("avg_recovery")}

平均HRV：
{weekly_data.get("avg_hrv")}

平均静息心率：
{weekly_data.get("avg_resting_hr")}

平均睡眠：
{weekly_data.get("avg_sleep")} 小时

平均Strain：
{weekly_data.get("avg_strain")}


==============================
Recovery统一规则
==============================

Recovery >=67%：
绿色恢复

Recovery 34-66%：
黄色恢复

Recovery <34%：
红色恢复


不得自行使用其他分界。

Recovery不能作为唯一训练依据。


==============================
局部疲劳
==============================

最近一次手指疲劳：
{latest_finger_fatigue}/10

最近一次肘部疲劳：
{latest_elbow_fatigue}/10

训练后恢复评分：
{latest_recovery_after}

距离最近一次指力板：
{days_since_hangboard}个自然日


今日综合手指疲劳：
{training_readiness.get("finger_fatigue")}/10

今日综合肘部疲劳：
{training_readiness.get("elbow_fatigue")}/10

今日前臂疲劳：
{training_readiness.get("forearm_fatigue")}/10


手指疲劳4-6/10必须描述为：

“中等局部手指疲劳”。


不得仅凭4-6/10判断：

疲劳累积
恢复不足
过度使用
肌腱损伤
高伤病风险。


==============================
Repeaters
==============================

Repeaters不等于Max Hang。

不得把Max Hang专项决策
直接套用到Repeaters。


如果今天已经完成Repeaters：

不得再次推荐同日追加Repeaters。


如果今天尚未完成，
且整体训练准备度允许，
可结合局部疲劳考虑：

降低强度
减少组数
减少总量
增加休息。


==============================
训练频率
==============================

最近7天训练次数较多：

只能作为辅助负荷信息。

不得单独证明：

疲劳累积
过度使用
恢复不足
伤病风险。


==============================
WHOOP夜间皮肤温度
==============================

今日：
{skin_temperature_text}

近期平均：
{skin_temperature_avg}

有效历史：
{skin_temperature_valid_days}天

偏差：
{temperature_deviation}


WHOOP skin_temperature是夜间皮肤温度。

不是核心体温、
腋温或口腔体温。


如果有效历史不足3天：

必须说明：

“当前温度历史数据不足，
暂不做可靠个人趋势判断。”


不得根据单日皮肤温度判断：

发烧
感染
疾病。


==============================
WHOOP SpO₂
==============================

今日：
{spo2_text}

近期平均：
{spo2_avg}

有效历史：
{spo2_valid_days}天

偏差：
{spo2_deviation}


如果有效历史不足3天：

必须说明：

“当前血氧历史数据不足，
暂不做可靠趋势判断。”


不得根据单次SpO₂
进行医学诊断。


==============================
经期 / 伤病
==============================

经期：
{menstrual_data}

伤病：
{injury_data}


如果经期数据缺失：

写：

“数据缺失，无法判断。”


如果没有明确伤病记录：

可以写：

“当前没有明确伤病记录，
无法据此排除全部风险。”


不得自行推测：

疼痛
肿胀
僵硬
肌腱敏感
动作受限。


==============================
攀岩专项疲劳
==============================

疲劳等级：
{climbing_fatigue.get(
    "fatigue_level",
    "数据不足"
)}

建议：
{climbing_fatigue.get(
    "recommendations",
    []
)}


==============================
最终输出要求
==============================

必须首先判断：

training_phase。


如果是：

pre_training

回答重点：

今天适合什么训练。


如果是：

post_training

回答重点：

今天已经练了什么，
现在还建议做什么。


必须说明：

今日整体恢复状态

HRV与静息心率状态

睡眠支持或限制

当前主要限制因素

今天已经完成的训练

现在是否还需要继续训练

Repeaters状态

Max Hang专项状态

Max Hang今日行动

当前Strain

目标Strain

训练完成度

remaining_strain的正确含义。


如果今天已经完成主要训练：

不得为了追Strain
鼓励追加高强度训练。


未来建议必须使用：

如果……
若……
当……

等条件式表达。


不得预测明天具体：

Recovery
HRV
静息心率
Sleep Score。


使用中文简体。

表达：

专业
谨慎
简洁
清晰
可执行。

"""
    

def generate_weekly_ai_summary(
    ai_prompt
):

    import json


    try:

        response = (
            client.chat.completions.create(

                model="deepseek-chat",

                messages=[

                    {
                        "role":
                            "system",

                        "content":
                            """

你是一名专业的 WHOOP 私人攀岩 Weekly Coach。

你的职责是：

分析最近7天 WHOOP 趋势、
攀岩训练负荷、
指力板训练负荷、
局部手指/肘部状态、
睡眠趋势以及恢复趋势，

并提供未来训练的条件框架。


==============================
Weekly Coach职责边界
==============================

Weekly Coach负责：

1. 最近7天Recovery趋势；
2. 最近7天HRV趋势；
3. 最近7天静息心率趋势；
4. 最近7天睡眠趋势；
5. 最近7天Strain总体负荷；
6. 攀岩训练负荷；
7. 指力板训练负荷；
8. 最近局部疲劳状态；
9. 未来训练进入不同强度所需条件。


Weekly Coach不负责：

今天还应该训练多少；
今天是否必须补Strain；
未来某一天具体练什么；
未来某一天必须休息；
未来某一天必须进行高强度训练。


今天具体训练决策必须服从：

Daily Coach
Training Readiness
Max Hang Decision。


==============================
禁止Daily Strain污染
==============================

Weekly Coach可以分析：

最近7天平均Strain
最近7天Strain趋势
最近7天整体训练负荷
攀岩与指力板训练负荷结构


Weekly Coach不得输出或重点讨论：

当前 Strain
今日 Strain
目标 Strain
训练完成度
剩余建议负荷


即使输入中存在：

current_strain
recommended_strain
strain_completion
remaining_strain

Weekly Coach也必须忽略这些Daily决策字段。


不得在ai_report、
training_advice
或risk_warning中重复这些字段的具体数值。


例如输入中存在：

current_strain = 4.34

不得输出：

“当前Strain 4.34”

“今日Strain为4.34”

“当前Strain距离目标还有……”

“当前训练完成度……”


Weekly Coach应该改为分析：

“最近7天整体训练负荷”

“最近7天平均Strain”

“近期训练负荷结构”

“攀岩与指力板训练密度”


Weekly Coach不得根据：

current_strain
recommended_strain
remaining_strain
strain_completion

决定当前或未来训练。


不得写：

“还需要补X Strain”

“建议达到今天目标Strain”

“剩余训练额度”

“今天应继续训练直到达到目标”。


Weekly Coach关注的是：

最近7天训练负荷结构、
恢复趋势以及后续训练决策条件，

而不是单日距离某个Daily Strain目标还差多少。

==============================
Recovery规则
==============================

Recovery统一分级：

Recovery >=67%：
绿色恢复

Recovery 34-66%：
黄色恢复

Recovery <34%：
红色恢复


不得自行使用其他Recovery分界。


最近7天平均Recovery只代表周趋势，

不得直接代替今天Daily Recovery。


==============================
HRV / 静息心率
==============================

必须优先使用个人近期趋势。

不得仅凭单日HRV变化判断：

疲劳累积
恢复不足
过度训练。


如果HRV下降，

必须同时考虑：

静息心率
Recovery
睡眠
局部疲劳
训练负荷。


不得把相关性写成确定因果。


==============================
局部疲劳
==============================

手指疲劳：

0-3/10：
低局部疲劳

4-6/10：
中等局部手指疲劳

7-8/10：
明显局部疲劳

9-10/10：
高局部疲劳


4-6/10不得仅凭评分解释成：

疲劳累积
恢复不足
过度使用
肌腱风险
高风险。


最近7天平均疲劳：

只代表历史训练记录平均值。

不得当作今天当前疲劳。


判断当前局部状态时，

优先参考：

最近一次手指疲劳
最近一次肘部疲劳
训练后恢复评分
伤病记录。


==============================
训练频率规则
==============================

最近7天：

攀岩次数
指力板次数
总训练时长
总悬挂时间

都属于训练负荷背景。


训练频率较高：

不能单独证明：

疲劳累积
过度使用
恢复不足
伤病风险。


不得仅因为最近7天指力板次数较多，

直接规定：

固定休息日
未来数天禁止指力训练
未来数天禁止Max Hang。


==============================
Max Hang
==============================

Weekly Coach只能描述：

下一次Max Hang需要满足什么条件。


不得安排：

Max Hang执行日期。


不得声称：

“下一次一定可以Max Hang”。

不得声称：

“已经满足完整48小时”

除非输入明确提供准确训练时间。


只有训练日期而没有准确时间时，

只能说：

恢复间隔需要结合实际训练时间确认。


Max Hang实际执行必须服从：

计划执行当天最新的
Max Hang Decision。


==============================
未来训练决策边界
==============================

Weekly Coach只能提供：

训练方向
决策条件
训练优先级

不得替未来具体日期决定训练内容。


未来训练建议中不得使用以下时间标签排课：

明天
明日
后天
后日
随后1-2天
未来1-2天
第2天
第3天
下一天


不得输出：

“明天恢复”

“明天低负荷”

“明天休息”

“明天技术攀岩”

“后天质量训练”

“随后1-2天安排质量训练”

“恢复后安排一个质量日”。


正确表达方式：

“下一训练日重新读取最新Daily Coach，
根据当天Recovery、HRV、静息心率、睡眠、
局部疲劳和Training Readiness
决定训练类型和强度。”


质量训练只能表达为：

“当执行当天整体恢复、
HRV趋势、睡眠和局部状态
支持质量训练时，
再考虑较高质量攀岩或力量训练。”


如果条件不支持：

“由执行当天Daily Coach
决定降低训练负荷、恢复或休息。”


==============================
未来生理指标
==============================

不得预测未来具体：

Recovery
HRV
静息心率
Sleep Score。


不得输出：

“未来Recovery会上升”

“HRV会恢复到XX”

“恢复状态可能维持或改善”。


未来状态尚未知，

必须在执行当天重新读取数据。


==============================
温度规则
==============================

WHOOP skin_temperature
是夜间皮肤温度，

不是核心体温。


如果有效历史不足3天：

必须说明：

“当前温度历史数据不足，
暂不做可靠个人趋势判断。”


不得根据单日皮肤温度判断：

发烧
感染
疾病。


==============================
SpO₂规则
==============================

如果有效历史不足3天：

必须说明：

“当前血氧历史数据不足，
暂不做可靠趋势判断。”


不得根据单次SpO₂
进行医学诊断。


==============================
Daily与Weekly优先级
==============================

Weekly Coach：

负责趋势和未来训练条件框架。


Daily Coach：

负责执行当天训练决策。


如果Weekly趋势与执行当天Daily Coach不同，

执行当天以最新Daily Coach为准。


Max Hang：

必须以执行当天最新
Max Hang Decision为准。


==============================
最终输出内容
==============================

报告重点应包含：

最近7天整体恢复趋势

Recovery趋势

HRV和静息心率趋势

睡眠趋势

攀岩训练负荷

指力板训练负荷

局部手指/肘部状态

当前需要关注的主要因素

未来训练决策框架

质量训练进入条件

Max Hang下一次评估原则


不得输出Daily Strain目标字段。


==============================
最终未来训练框架
==============================

推荐使用：

“当前训练状态
→ 下一训练日重新读取Daily Coach
→ 根据执行当天状态决定训练类型和强度
→ 满足质量训练条件时再考虑质量训练
→ Max Hang由执行当天专项决策决定。”


不得把它改写成日期训练表。


==============================
输出前自检
==============================

最终文本不得出现：

明天
明日
后天
后日
随后1-2天
未来1-2天
第2天
第3天
下一天


如果草稿出现，

必须改写成：

下一训练日
后续训练
计划训练当天
执行当天
当天最新Daily Coach
满足条件时


最终文本也不得出现：

目标 Strain
训练完成度
剩余建议负荷


如果输入中存在这些Daily字段，

Weekly Coach必须忽略。


==============================
最终输出格式
==============================

必须只输出JSON。

禁止JSON以外任何内容。


严格返回：

{
  "ai_report": "",
  "training_advice": "",
  "risk_warning": ""
}


ai_report：

填写完整最近7天Weekly Coach分析。


training_advice：

只填写未来训练条件框架。

不得按日期排课。


risk_warning：

只填写当前数据明确支持的风险或关注因素。

不得自行升级风险。


如果没有明确风险：

填写：

“暂无明显风险”。


语言：

中文简体
专业
简洁
谨慎
可执行

"""
                    },


                    {
                        "role":
                            "user",

                        "content":
                            json.dumps(
                                ai_prompt,
                                ensure_ascii=False
                            )
                    }

                ],

                temperature=0.3,

                max_tokens=1100

            )
        )


        content = (
            response
            .choices[0]
            .message
            .content
        )


        print(
            "DEBUG WEEKLY AI RAW:",
            repr(
                content
            )
        )


        # =========================
        # 去除Markdown代码块
        # =========================

        content = (
            content.strip()
        )


        if content.startswith(
            "```"
        ):

            content = (
                content.replace(
                    "```json",
                    ""
                )
            )

            content = (
                content.replace(
                    "```",
                    ""
                )
            )

            content = (
                content.strip()
            )


        # =========================
        # JSON解析
        # =========================

        try:

            result = (
                json.loads(
                    content
                )
            )


            return result


        except Exception as e:

            print(
                "WEEKLY JSON LOAD ERROR:",
                e
            )


            return {

                "ai_report":
                    content,

                "training_advice":
                    "",

                "risk_warning":
                    ""

            }


    except Exception as e:

        print(
            "WEEKLY AI SUMMARY ERROR:",
            e
        )


        return {

            "ai_report":
                "⚠️ Weekly Coach暂时无法生成建议",

            "training_advice":
                "",

            "risk_warning":
                ""

        }



def generate_weekly_analysis():

    conn = None
    cur = None

    try:

        conn = get_db_connection()
        cur = conn.cursor()


        # =========================
        # 1. 最近7天 WHOOP 数据
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
                cycle_strain,
                skin_temperature,
                spo2_percentage

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
        # 2. 没有 WHOOP 数据
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

                "training_load": {},

                "climbing_fatigue": {},

                "prompt_text":
                    "暂无 WHOOP 历史数据"
            }


        # 数据库是 DESC
        # 转换成日期正序

        rows = list(
            reversed(rows)
        )


        # =========================
        # 3. 工具函数
        # =========================

        def safe_float(value):

            if value is None:
                return None

            try:

                return float(value)

            except Exception:

                return None


        def safe_avg(values):

            valid = []

            for value in values:

                converted = safe_float(
                    value
                )

                if converted is not None:

                    valid.append(
                        converted
                    )


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
        # 4. 整理每日 WHOOP 数据
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
                cycle_strain,
                skin_temperature,
                spo2_percentage
            ) = row


            record = {

                "report_date":
                    str(report_date),

                "recovery_score":
                    safe_float(
                        recovery_score
                    ),

                "hrv":
                    safe_float(
                        hrv
                    ),

                "resting_heart_rate":
                    safe_float(
                        resting_heart_rate
                    ),

                "sleep_duration":
                    safe_float(
                        sleep_duration
                    ),

                "sleep_score":
                    safe_float(
                        sleep_score
                    ),

                "cycle_strain":
                    safe_float(
                        cycle_strain
                    ),

                "skin_temperature":
                    safe_float(
                        skin_temperature
                    ),

                "spo2_percentage":
                    safe_float(
                        spo2_percentage
                    )

            }


            records.append(
                record
            )


            data_lines.append(
                f"日期：{report_date}\n"
                f"Recovery：{show_value(recovery_score, '%')}\n"
                f"HRV：{show_value(hrv, ' ms')}\n"
                f"静息心率：{show_value(resting_heart_rate, ' bpm')}\n"
                f"睡眠时长：{show_value(sleep_duration, ' 小时')}\n"
                f"睡眠评分：{show_value(sleep_score, ' 分')}\n"
                f"Strain：{show_value(cycle_strain)}\n"
                f"WHOOP皮肤温度：{show_value(skin_temperature, ' °C')}\n"
                f"SpO₂：{show_value(spo2_percentage, '%')}"
            )
            

        # =========================
        # 5. 周期信息
        # =========================

        valid_days = len(
            records
        )


        start_date = records[0][
            "report_date"
        ]


        end_date = records[-1][
            "report_date"
        ]


        # =========================
        # 6. WHOOP 平均值
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
        # WHOOP 温度 / SpO2趋势
        # =========================

        valid_skin_temperatures = [
            r["skin_temperature"]
            for r in records
            if r.get("skin_temperature") is not None
        ]


        valid_spo2_values = [
            r["spo2_percentage"]
            for r in records
            if r.get("spo2_percentage") is not None
        ]


        skin_temperature_valid_days = len(
            valid_skin_temperatures
        )


        spo2_valid_days = len(
            valid_spo2_values
        )


        skin_temperature_avg = (
            round(
                sum(valid_skin_temperatures)
                / skin_temperature_valid_days,
                2
            )
            if skin_temperature_valid_days > 0
            else None
        )


        spo2_avg = (
            round(
                sum(valid_spo2_values)
                / spo2_valid_days,
                2
            )
            if spo2_valid_days > 0
            else None
        )


        # 最新一天
        latest_skin_temperature = (
            records[-1].get(
                "skin_temperature"
            )
            if records
            else None
        )


        latest_spo2_percentage = (
            records[-1].get(
                "spo2_percentage"
            )
            if records
            else None
        )


        # 至少3天数据才允许形成趋势偏差
        temperature_deviation = None

        if (
            skin_temperature_valid_days >= 3
            and latest_skin_temperature is not None
            and skin_temperature_avg is not None
        ):

            temperature_deviation = round(
                latest_skin_temperature
                - skin_temperature_avg,
                2
            )


        spo2_deviation = None

        if (
            spo2_valid_days >= 3
            and latest_spo2_percentage is not None
            and spo2_avg is not None
        ):

            spo2_deviation = round(
                latest_spo2_percentage
                - spo2_avg,
                2
            )


        temperature_baseline_reliable = (
            skin_temperature_valid_days >= 3
        )


        spo2_baseline_reliable = (
            spo2_valid_days >= 3
        )


        print(
            "WEEKLY TEMPERATURE:",
            {
                "latest":
                    latest_skin_temperature,

                "avg":
                    skin_temperature_avg,

                "valid_days":
                    skin_temperature_valid_days,

                "deviation":
                    temperature_deviation,

                "baseline_reliable":
                    temperature_baseline_reliable
            }
        )


        print(
            "WEEKLY SPO2:",
            {
                "latest":
                    latest_spo2_percentage,

                "avg":
                    spo2_avg,

                "valid_days":
                    spo2_valid_days,

                "deviation":
                    spo2_deviation,

                "baseline_reliable":
                    spo2_baseline_reliable
            }
        )



        # =========================
        # 7. 最近7天攀岩/指力板负荷
        # =========================

        try:

            training_load = (
                calculate_training_load()
            )


            if not isinstance(
                training_load,
                dict
            ):

                training_load = {}


        except Exception as e:

            print(
                "WEEKLY TRAINING LOAD ERROR:",
                e
            )

            training_load = {}


        print(
            "WEEKLY TRAINING LOAD:",
            training_load
        )


        # =========================
        # 8. 局部攀岩疲劳分析
        # =========================

        try:

            climbing_fatigue = (
                analyze_climbing_fatigue(
                    training_load
                )
            )


            if not isinstance(
                climbing_fatigue,
                dict
            ):

                climbing_fatigue = {}


        except Exception as e:

            print(
                "WEEKLY CLIMBING FATIGUE ERROR:",
                e
            )

            climbing_fatigue = {}


        print(
            "WEEKLY CLIMBING FATIGUE:",
            climbing_fatigue
        )


        # =========================
        # 9. 提取训练负荷字段
        # =========================

        climbing_sessions_7d = (
            training_load.get(
                "climbing_sessions_7d",
                training_load.get(
                    "climbing_sessions",
                    0
                )
            )
        )


        climbing_duration_7d = (
            training_load.get(
                "climbing_duration_7d",
                training_load.get(
                    "climbing_duration",
                    0
                )
            )
        )


        hangboard_sessions_7d = (
            training_load.get(
                "hangboard_sessions_7d",
                training_load.get(
                    "hangboard_sessions",
                    0
                )
            )
        )


        hangboard_duration_7d = (
            training_load.get(
                "hangboard_duration_7d",
                training_load.get(
                    "hangboard_duration",
                    0
                )
            )
        )


        hang_time_7d = (
            training_load.get(
                "hang_time_7d",
                0
            )
        )


        avg_finger_fatigue_7d = (
            training_load.get(
                "avg_finger_fatigue_7d",
                0
            )
        )


        avg_elbow_fatigue_7d = (
            training_load.get(
                "avg_elbow_fatigue_7d",
                0
            )
        )


        latest_finger_fatigue = (
            training_load.get(
                "latest_finger_fatigue",
                0
            )
        )


        latest_elbow_fatigue = (
            training_load.get(
                "latest_elbow_fatigue",
                0
            )
        )


        latest_hangboard_date = (
            training_load.get(
                "latest_hangboard_date"
            )
        )


        days_since_hangboard = (
            training_load.get(
                "days_since_hangboard"
            )
        )


        latest_recovery_after = (
            training_load.get(
                "latest_recovery_after"
            )
        )


        # =========================
        # 10. WHOOP 数据文本
        # =========================

        weekly_data_text = "\n\n".join(
            data_lines
        )


        # =========================
        # 11. Weekly AI Prompt
        # =========================

        data_completeness = (
            "完整7天数据"
            if valid_days >= 7
            else "不足7天，仅代表阶段性趋势"
        )


        prompt_text = (
            f"统计周期：\n"
            f"{start_date} 至 {end_date}\n\n"

            f"有效 WHOOP 记录：\n"
            f"{valid_days}/7天\n\n"

            f"数据完整性：\n"
            f"{data_completeness}\n\n"

            f"==============================\n"
            f"WHOOP 每日数据\n"
            f"==============================\n\n"

            f"以下数据按日期正序排列：\n\n"
            f"{weekly_data_text}\n\n"

            f"==============================\n"
            f"WHOOP 周平均\n"
            f"==============================\n\n"

            f"平均 Recovery：\n"
            f"{avg_recovery}%\n\n"

            f"平均 HRV：\n"
            f"{avg_hrv} ms\n\n"

            f"平均静息心率：\n"
            f"{avg_resting_hr} bpm\n\n"

            f"平均睡眠：\n"
            f"{avg_sleep} 小时\n\n"

            f"平均睡眠评分：\n"
            f"{avg_sleep_score}\n\n"

            f"平均 Strain：\n"
            f"{avg_strain}\n\n"


            f"==============================\n"
            f"WHOOP皮肤温度与血氧\n"
            f"==============================\n\n"

            f"今日WHOOP皮肤温度：\n"
            f"{show_value(latest_skin_temperature, ' °C')}\n\n"

            f"最近有效皮肤温度平均：\n"
            f"{show_value(skin_temperature_avg, ' °C')}\n\n"

            f"皮肤温度有效记录：\n"
            f"{skin_temperature_valid_days}/7天\n\n"

            f"皮肤温度相对近期平均偏差：\n"
            f"{show_value(temperature_deviation, ' °C')}\n\n"

            f"温度基线是否足够：\n"
            f"{'是' if temperature_baseline_reliable else '否'}\n\n"

            f"今日WHOOP SpO₂：\n"
            f"{show_value(latest_spo2_percentage, '%')}\n\n"

            f"最近有效SpO₂平均：\n"
            f"{show_value(spo2_avg, '%')}\n\n"

            f"SpO₂有效记录：\n"
            f"{spo2_valid_days}/7天\n\n"

            f"SpO₂相对近期平均偏差：\n"
            f"{show_value(spo2_deviation, '%')}\n\n"

            f"SpO₂基线是否足够：\n"
            f"{'是' if spo2_baseline_reliable else '否'}\n\n"

            f"重要说明：\n"
            f"WHOOP皮肤温度是夜间皮肤温度，不等于核心体温、"
            f"腋温或口腔温度。\n"
            f"如果皮肤温度有效记录少于3天，"
            f"只能报告当前值，不得判断相对个人基线升高或降低。\n"
            f"如果SpO₂有效记录少于3天，"
            f"只能报告当前值，不得进行可靠趋势判断。\n"
            f"单次皮肤温度或SpO₂不得用于医学诊断。\n\n"


            f"==============================\n"
            f"最近7天攀岩训练负荷\n"
            f"==============================\n\n"

            f"攀岩次数：\n"
            f"{climbing_sessions_7d}\n\n"

            f"攀岩总时长：\n"
            f"{climbing_duration_7d} 分钟\n\n"

            f"==============================\n"
            f"最近7天指力板训练负荷\n"
            f"==============================\n\n"
        
            f"指力板次数：\n"
            f"{hangboard_sessions_7d}\n\n"

            f"指力板总时长：\n"
            f"{hangboard_duration_7d} 分钟\n\n"

            f"总悬挂时间：\n"
            f"{hang_time_7d} 秒\n\n"

            f"最近7天平均手指疲劳：\n"
            f"{avg_finger_fatigue_7d}/10\n\n"
        
            f"最近7天平均肘部疲劳：\n"
            f"{avg_elbow_fatigue_7d}/10\n\n"

            f"重要：\n"
            f"最近7天平均手指疲劳和肘部疲劳，"
            f"只代表历史训练记录的平均值，"
            f"不得直接解释为今天当前疲劳。\n\n"

            f"==============================\n"
            f"最近一次指力板状态\n"
            f"==============================\n\n"

            f"最近一次训练日期：\n"
            f"{latest_hangboard_date}\n\n"

            f"距最近一次训练：\n"
            f"{days_since_hangboard} 个自然日\n\n"

            f"最近一次手指疲劳：\n"
            f"{latest_finger_fatigue}/10\n\n"

            f"最近一次肘部疲劳：\n"
            f"{latest_elbow_fatigue}/10\n\n"

            f"训练后恢复评分：\n"
            f"{latest_recovery_after}\n\n"

            f"==============================\n"
            f"攀岩专项疲劳模型\n"
            f"==============================\n\n"

            f"疲劳等级：\n"
            f"{climbing_fatigue.get('fatigue_level', '数据不足')}\n\n"

            f"模型建议：\n"
            f"{climbing_fatigue.get('recommendations', [])}\n\n"

            f"==============================\n"
            f"分析要求\n"
            f"==============================\n\n"

            f"1. 只能根据以上实际数据分析。\n\n"

            f"2. 如果 WHOOP 数据不足7天，"
            f"必须明确说明这是阶段性趋势。\n\n"

            f"3. 不得推测缺失日期或缺失指标。\n\n"

            f"4. 不得把没有训练记录解释为休息日。\n\n"

            f"5. Recovery 必须结合 HRV、静息心率、睡眠和 Strain 综合判断。\n\n"
        
            f"6. Strain 必须结合 Recovery 和睡眠判断负荷是否匹配。\n\n"

            f"7. 单日变化不得直接定义为长期疲劳或恢复异常。\n\n"

            f"8. 必须区分短期波动与连续趋势。\n\n"

            f"9. Weekly训练建议必须同时结合 WHOOP恢复趋势、"
            f"攀岩负荷、指力板负荷、手指疲劳和肘部疲劳。\n\n"

            f"10. 最近7天指力板频率较高，"
            f"本身不能证明过度使用或疲劳累积。\n\n"

            f"11. 最近7天平均疲劳不能等同于当前手指或肘部疲劳。\n\n"

            f"12. 判断当前局部风险时，优先参考最近一次疲劳评分、"
            f"距离最近一次训练的自然日、recovery_after以及近期训练频率。\n\n"

            f"13. 如果最近一次手指疲劳为4-6/10，"
            f"应描述为中等局部疲劳或建议关注恢复，"
            f"不得直接描述为疲劳累积、恢复不足或过度使用。\n\n"

            f"14. 未来7天训练建议必须采用条件式建议。\n"
            f"对未来具体日期，不得使用今天的 Recovery "
            f"直接决定未来当天训练强度。\n"
            f"如果未来当天 Recovery 较高、HRV稳定、睡眠充足、"
            f"局部手指/肘部状态良好且无伤病限制，"
            f"可以考虑中高强度攀岩或符合条件的力量训练。\n"
            f"如果未来当天 Recovery 为黄色，"
            f"应结合当天HRV、静息心率、睡眠和局部状态"
            f"再决定是否采用技术训练或低至中等强度训练。\n"
            f"如果未来当天 HRV明显下降、睡眠不足、"
            f"局部疲劳升高或出现伤病限制，"
            f"再降低训练负荷或恢复。\n\n"

            f"15. Max Hang 属于高强度最大力量训练。\n"
            f"只有在整体恢复良好、局部手指状态允许、"
            f"距离上次高强度指力训练具有足够恢复间隔，"
            f"且无明确伤病信号时，才可以考虑 Max Hang。\n\n"

            f"如果训练记录只有日期而没有准确训练时间，"
            f"不得声称已经满足完整48小时恢复间隔。\n"
            f"只能说明距离上次训练约多少个自然日，"
            f"完整48小时需要结合实际训练时间确认。\n\n"

            f"手指疲劳4-6/10属于中等局部手指疲劳，"
            f"不自动禁止 Max Hang。\n"
            f"如果 Recovery >=67%、HRV没有明显低于近期基线、"
            f"静息心率稳定、睡眠基本充足、"
            f"recovery_after >=75、"
            f"没有疼痛/僵硬/肌腱敏感/动作受限记录、"
            f"恢复间隔足够且热身后手指状态正常，"
            f"可以考虑恢复 Max Hang，"
            f"但首次恢复训练应降低总量。\n\n"

            f"16. 不得根据历史训练次数，直接假设用户今天存在"
            f"疼痛、酸痛、僵硬、肌腱敏感或动作受限。\n\n"

            f"17. 不进行医学诊断。\n\n"

            f"18. WHOOP、睡眠、HRV、Strain和训练负荷之间"
            f"只能描述数据支持的关联，不得自行建立确定因果关系。\n"
            f"禁止使用：直接导致、证明、一定因为。\n"
            f"优先使用：可能与……有关、与……同时出现、"
            f"可能对恢复形成压力、数据提示可能存在关联。\n\n"

            f"19. Recovery 分级必须统一使用：\n"
            f"Recovery >=67%：绿色恢复；\n"
            f"Recovery 34-66%：黄色恢复；\n"
            f"Recovery <34%：红色恢复。\n"
            f"不得自行使用70%、75%、50%等其他Recovery分界。\n\n"

            f"20. Weekly Coach 与 Daily Coach 的职责必须严格区分。\n"
            f"Weekly Coach 负责识别最近7天趋势、训练负荷结构、"
            f"恢复趋势以及未来训练安排的条件框架；"
            f"不得代替未来某一天的 Daily Coach 提前做最终训练决定。\n\n"

            f"对于明天、后天以及未来具体日期，"
            f"如果尚未获得该日新的 Recovery、HRV、静息心率、"
            f"睡眠、局部疲劳和伤病状态，"
            f"不得提前定义为恢复日、休息日、低负荷日、"
            f"高强度日或 Max Hang 日。\n\n"

            f"禁止仅因为今天已经训练、"
            f"最近7天训练次数较多、"
            f"指力板频率较高或当前HRV存在短期下降，"
            f"就直接写："
            f"“明天优先恢复”、"
            f"“明天休息”、"
            f"“明天低负荷”、"
            f"“未来1-2天恢复”"
            f"或其他已经替未来日期做出最终决定的表达。\n\n"

            f"未来日期必须采用条件式表达，例如：\n"
            f"“明天根据新的 Daily Coach 数据决定训练安排。"
            f"如果 Recovery、HRV、静息心率、睡眠、"
            f"局部手指/肘部状态和伤病状态支持，"
            f"可以正常安排训练；"
            f"如果恢复指标或局部状态下降，再降低训练负荷或恢复。”\n\n"

            f"Weekly Coach 可以指出未来训练的优先级、"
            f"需要观察的指标以及进入高强度训练所需条件，"
            f"但不得在未来 Daily 数据尚不存在时，"
            f"提前确定某一天必须训练或必须休息。\n\n"

            f"最近7天训练频率只能作为负荷背景，"
            f"不能单独用于规定固定休息1-2天，"
            f"也不能单独用于规定未来2-3天禁止 Max Hang。\n\n"

            f"21. WHOOP皮肤温度必须明确称为"
            f"“WHOOP夜间皮肤温度”或“皮肤温度”，"
            f"不得称为核心体温。\n\n"

            f"22. 如果皮肤温度有效历史少于3天，"
            f"不得使用“较个人基线升高”“较个人基线下降”"
            f"或“温度异常”等结论，"
            f"只能报告当前数值并说明历史不足。\n\n"

            f"23. 如果SpO₂有效历史少于3天，"
            f"只能报告当前值，"
            f"不得根据单次读数进行医学推断。\n\n"

            f"24. WHOOP皮肤温度和SpO₂只能作为辅助恢复信号，"
            f"不得仅凭其中一个指标提高训练风险等级。\n"

            f"25. 【最高优先级：未来日期决策边界】\n"
            f"Weekly Coach 绝对不能提前决定明天、后天或任何未来具体日期"
            f"属于恢复日、休息日、低负荷日、中等强度日、高强度日或质量训练日。\n\n"

            f"即使使用“如果”作为前缀，也不能使用今天的数据"
            f"直接给明天指定训练类型。"
            f"例如以下表达仍然禁止：\n"
            f"“如果明天Recovery仍为黄色，则优先恢复”；\n"
            f"“如果HRV没有改善，明天低负荷”；\n"
            f"“明天优先恢复/低负荷”；\n"
            f"“状态改善后安排一个质量日”。\n\n"

            f"原因是未来日期的最终训练类型必须由该日最新的"
            f"Daily Coach / Training Readiness / 局部状态决定，"
            f"Weekly Coach 不能提前完成这个决策。\n\n"

            f"当描述明天时，优先使用以下结构：\n"
            f"“明天先读取新的 Recovery、HRV、静息心率、睡眠、"
            f"局部疲劳和伤病状态，再由 Daily Coach 决定当天训练类型和强度。”\n\n"

            f"当描述随后几天时，只能描述进入不同训练类型所需的条件，"
            f"不能提前指定日期。"
            f"例如：\n"
            f"“当全身恢复、HRV趋势、睡眠和局部状态支持质量训练时，"
            f"可以考虑较高质量攀岩；"
            f"若条件不支持，则当天根据 Daily Coach 调整。”\n\n"

            f"Max Hang 同样不得由 Weekly Coach 提前指定执行日期。"
            f"Weekly Coach 只能说明下一次 Max Hang 所需条件，"
            f"实际是否执行必须读取执行当天的 Max Hang Decision。\n\n"

            f"最终总结不得写成按日期预排的训练时间表。"
            f"禁止："
            f"“今天结束负荷 → 明天恢复/低负荷 → 后天质量训练”。\n"

            f"最终总结应写成决策流程："
            f"“今天完成当前训练 → 明天读取新的 Daily Coach → "
            f"根据当天数据决定训练类型 → "
            f"满足质量训练条件时再考虑质量训练 → "
            f"Max Hang 由执行当天专项决策决定。”\n\n"

            f"如果本条规则与前面任何训练建议发生冲突，"
            f"以第25条为最高优先级。\n\n"

            f"26. 【Weekly未来训练：禁止日期排程】\n"
            f"Weekly Coach 只能提供训练方向和决策条件，"
            f"绝对不能替未来某一天决定具体训练内容。\n\n"

            f"【禁止使用的未来时间表达】\n"
            f"在未来训练建议中，禁止使用：\n"
            f"“明天”、“后天”、“随后1-2天”、“未来1-2天”、"
            f"“第2天”、“第3天”、“下一天”等时间标签来安排训练。\n\n"

            f"禁止生成任何类似以下内容：\n"
            f"“明天休息”；\n"
            f"“明天低负荷”；\n"
            f"“明天技术攀岩”；\n"
            f"“随后1-2天安排质量训练”；\n"
            f"“恢复后安排质量日”；\n"
            f"“今天结束负荷 → 明天恢复 → 后天质量训练”。\n\n"

            f"即使根据当前 Recovery、HRV、睡眠或局部疲劳，"
            f"某种未来安排看起来很合理，也禁止直接安排。\n"
            f"原因是未来训练日的 Recovery、HRV、睡眠、局部疲劳、"
            f"Training Readiness 和 Max Hang Decision 尚未知。\n\n"

            f"【唯一允许的未来训练结构】\n"
            f"未来训练建议必须使用以下结构：\n\n"

            f"“当前阶段：说明目前训练负荷和恢复方向。”\n\n"

            f"“下一训练日：重新读取当天最新 Daily Coach，"
            f"根据当天 Recovery、HRV、睡眠、局部疲劳和 "
            f"Training Readiness 决定训练类型和强度。”\n\n"

            f"“质量训练条件：只有当天 Daily Coach 判断训练准备度支持，"
            f"并且局部手指/肘部状态允许时，才考虑较高质量训练。”\n\n"

            f"“降负荷条件：如果当天恢复指标、睡眠、HRV趋势、"
            f"局部疲劳或 Training Readiness 不支持，"
            f"则当天降低训练负荷或恢复。”\n\n"

            f"“Max Hang：不得由 Weekly Coach 安排日期。"
            f"只允许在计划执行当天读取最新 Max Hang Decision 后决定。”\n\n"

            f"【最终总结格式】\n"
            f"最终只能总结为：\n"
            f"“当前训练状态 → 下一训练日重新读取 Daily Coach → "
            f"根据当天状态决定训练类型和强度 → "
            f"满足质量训练条件时再考虑质量训练 → "
            f"Max Hang 由执行当天专项决策决定。”\n\n"

            f"不得把以上决策流程重新改写成按日期排列的训练计划。\n"
        )


        # =========================
        # 12. 返回统一 dict
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
         

            # WHOOP皮肤温度

            "skin_temperature":
                latest_skin_temperature,

            "skin_temperature_avg":
                skin_temperature_avg,

            "skin_temperature_valid_days":
                skin_temperature_valid_days,

            "temperature_deviation":
                temperature_deviation,

            "temperature_baseline_reliable":
                temperature_baseline_reliable,


            # WHOOP SpO2

            "spo2_percentage":
                latest_spo2_percentage,

            "spo2_avg":
                spo2_avg,

            "spo2_valid_days":
                spo2_valid_days,

            "spo2_deviation":
                spo2_deviation,

            "spo2_baseline_reliable":
                spo2_baseline_reliable,

            "records":
                records,

            # 攀岩与指力板数据
            "training_load":
                training_load,

            "climbing_fatigue":
                climbing_fatigue,

            "climbing_sessions_7d":
                climbing_sessions_7d,

            "climbing_duration_7d":
                climbing_duration_7d,

            "hangboard_sessions_7d":
                hangboard_sessions_7d,

            "hangboard_duration_7d":
                hangboard_duration_7d,

            "latest_finger_fatigue":
                latest_finger_fatigue,

            "latest_elbow_fatigue":
                latest_elbow_fatigue,

            "days_since_hangboard":
                days_since_hangboard,

            "prompt_text":
                prompt_text,

            "hang_time_7d":
                hang_time_7d,

            "avg_finger_fatigue_7d":
                avg_finger_fatigue_7d,

            "avg_elbow_fatigue_7d":
                avg_elbow_fatigue_7d,

            "latest_hangboard_date":
                latest_hangboard_date,

            "latest_recovery_after":
                latest_recovery_after,

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

            "skin_temperature":
                None,

            "skin_temperature_avg":
                None,

            "skin_temperature_valid_days":
                0,

            "temperature_deviation":
                None,

            "temperature_baseline_reliable":
                False,

            "spo2_percentage":
                None,

            "spo2_avg":
                None,

            "spo2_valid_days":
                0,

            "spo2_deviation":
                None,

            "spo2_baseline_reliable":
                False,

            "records": [],

            "training_load": {},

            "climbing_fatigue": {},

            "prompt_text": "",

            "error":
                str(e)

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


    print("========== NEW EXTRACT DAILY METRICS VERSION ==========")

 
    print(
        "FUNCTION INPUT CYCLE:",
        data.get("cycle")
    )

    result = {}


    # =========================
    # Recovery
    # =========================

    try:

        recovery_data = data.get(
            "recovery",
            []
        )


        if isinstance(
            recovery_data,
            dict
        ):

            recovery_records = recovery_data.get(
                "records",
                []
            )

        else:

            recovery_records = (
                recovery_data
                if isinstance(
                    recovery_data,
                    list
                )
                else []
            )


        recovery = (
            recovery_records[0]
            if recovery_records
            else {}
        )


        recovery_score_data = (
            recovery.get(
                "score"
            )
            or {}
        )

        print(
            "RAW RECOVERY SCORE DATA:",
            recovery_score_data
       )

     

        # =========================
        # Recovery Score
        # =========================

        result["recovery_score"] = (
            recovery_score_data.get(
                "recovery_score"
            )
        )


        # =========================
        # HRV
        # =========================

        result["hrv"] = (
            recovery_score_data.get(
                "hrv_rmssd_milli"
            )
        )


        # =========================
        # 静息心率
        # =========================

        result["resting_heart_rate"] = (
            recovery_score_data.get(
                "resting_heart_rate"
            )
        )


        # =========================
        # WHOOP 皮肤温度
        # =========================

        skin_temperature = (
            recovery_score_data.get(
                "skin_temp_celsius"
            )
        )


        if skin_temperature is not None:

            try:

                skin_temperature = round(
                    float(
                        skin_temperature
                    ),
                    2
                )

            except Exception:

                skin_temperature = None


        result["skin_temperature"] = (
            skin_temperature
        )


        # =========================
        # WHOOP 血氧
        # =========================

        spo2_percentage = (
            recovery_score_data.get(
                "spo2_percentage"
            )
        )


        if spo2_percentage is not None:

            try:

                spo2_percentage = round(
                    float(
                        spo2_percentage
                    ),
                    1
                )

            except Exception:

                spo2_percentage = None


        result["spo2_percentage"] = (
            spo2_percentage
        )


        print(
            "RECOVERY PARSED:",
            {
                "recovery_score":
                    result.get(
                        "recovery_score"
                    ),

                "hrv":
                    result.get(
                        "hrv"
                    ),

                "resting_heart_rate":
                    result.get(
                        "resting_heart_rate"
                    ),

                "skin_temperature":
                    result.get(
                        "skin_temperature"
                    ),

                "spo2_percentage":
                    result.get(
                        "spo2_percentage"
                    )
            }
        )


    except Exception as e:

        print(
            "RECOVERY ERROR:",
            e
        )

        result["recovery_score"] = None

        result["hrv"] = None

        result["resting_heart_rate"] = None

        result["skin_temperature"] = None

        result["spo2_percentage"] = None


    # =========================
    # Sleep
    # =========================

    try:

        sleep_data = data.get(
            "sleep",
            {}
        )


        if (
            not sleep_data
            and "score" in data
        ):

            sleep_data = data


        if isinstance(
            sleep_data,
            dict
        ):

            sleep_records = (
                sleep_data.get(
                    "records",
                    []
                )
            )


            if (
                not sleep_records
                and sleep_data.get(
                    "score"
                )
            ):

                sleep_records = [
                    sleep_data
                ]


        else:

            sleep_records = (
                sleep_data
                if isinstance(
                    sleep_data,
                    list
                )
                else []
            )


        # =========================
        # 优先非小睡 + 已评分睡眠
        # =========================

        main_sleep = None


        for record in sleep_records:

            if (
                not record.get(
                    "nap",
                    False
                )
                and record.get(
                    "score_state"
                ) == "SCORED"
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
            main_sleep.get(
                "score"
            )
            or {}
        )


        print(
            "SLEEP SCORE RAW:",
            sleep_score_data
        )


        stage = (
            sleep_score_data.get(
                "stage_summary"
            )
            or {}
        )


        # =========================
        # Sleep Score
        # =========================

        result["sleep_score"] = (
            sleep_score_data.get(
                "sleep_performance_percentage"
            )
        )


        # =========================
        # 睡眠阶段
        # =========================

        light_sleep = (
            stage.get(
                "total_light_sleep_time_milli"
            )
            or 0
        )


        deep_sleep = (
            stage.get(
                "total_slow_wave_sleep_time_milli"
            )
            or 0
        )


        rem_sleep = (
            stage.get(
                "total_rem_sleep_time_milli"
            )
            or 0
        )


        # 实际睡眠时间
        total_sleep = (
            light_sleep
            + deep_sleep
            + rem_sleep
        )


        result["sleep_duration"] = (
            round(
                total_sleep
                / 3600000,
                2
            )
            if total_sleep
            else None
        )


        # =========================
        # 睡眠效率
        # =========================

        result["sleep_efficiency"] = (
            sleep_score_data.get(
                "sleep_efficiency_percentage"
            )
        )


        # =========================
        # 深睡
        # =========================

        result["deep_sleep_duration"] = (
            round(
                deep_sleep
                / 3600000,
                2
            )
            if deep_sleep
            else None
        )


        # =========================
        # REM
        # =========================

        result["rem_sleep_duration"] = (
            round(
                rem_sleep
                / 3600000,
                2
            )
            if rem_sleep
            else None
        )


        print(
            "SLEEP PARSED:",
            {
                "sleep_score":
                    result.get(
                        "sleep_score"
                    ),

                "sleep_duration":
                    result.get(
                        "sleep_duration"
                    ),

                "sleep_efficiency":
                    result.get(
                        "sleep_efficiency"
                    ),

                "deep_sleep_duration":
                    result.get(
                        "deep_sleep_duration"
                    ),

                "rem_sleep_duration":
                    result.get(
                        "rem_sleep_duration"
                    )
            }
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


    # =========================
    # Cycle
    # =========================

    strain = None


    try:

        cycle_data = data.get(
            "cycle",
            {}
        )


        if isinstance(
            cycle_data,
            dict
        ):

            cycle_records = (
                cycle_data.get(
                    "records",
                    []
                )
            )

        else:

            cycle_records = (
                cycle_data
                if isinstance(
                    cycle_data,
                    list
                )
                else []
            )


        print(
            "CYCLE RECORD COUNT:",
            len(
                cycle_records
            )
        )


        for cycle in cycle_records:

            score = (
                cycle.get(
                    "score"
                )
                or {}
            )


            if (
                score.get(
                    "strain"
                )
                is not None
            ):

                strain = (
                    score.get(
                        "strain"
                    )
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


    result["cycle_strain"] = (
        strain
    )


    # =========================
    # Workout
    # =========================

    try:

        workout_data = data.get(
            "workout",
            {}
        )


        if isinstance(
            workout_data,
            dict
        ):

            result["workout_data"] = (
                workout_data.get(
                    "records",
                    workout_data
                )
            )

        else:

            result["workout_data"] = (
                workout_data
            )


    except Exception as e:

        print(
            "WORKOUT ERROR:",
            e
        )

        result["workout_data"] = {}


    # =========================
    # 最终输出
    # =========================

    print(
        "FINAL EXTRACT METRICS:",
        result
    )


    print(
        "WHOOP TEMPERATURE:",
        result.get(
            "skin_temperature"
        )
    )


    print(
        "WHOOP SPO2:",
        result.get(
            "spo2_percentage"
        )
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


        print(
            "SAVE WHOOP EXTRA:",
            {
                "skin_temperature":
                    metrics.get(
                        "skin_temperature"
                    ),

                "spo2_percentage":
                    metrics.get(
                        "spo2_percentage"
                    )
            }
        )


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
                health_score,
                skin_temperature,
                spo2_percentage
            )

            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s
            )

            ON CONFLICT (report_date)

            DO UPDATE SET

                recovery_score =
                    EXCLUDED.recovery_score,

                hrv =
                    EXCLUDED.hrv,

                resting_heart_rate =
                    EXCLUDED.resting_heart_rate,

                sleep_score =
                    EXCLUDED.sleep_score,

                sleep_duration =
                    EXCLUDED.sleep_duration,

                sleep_efficiency =
                    EXCLUDED.sleep_efficiency,

                deep_sleep_duration =
                    EXCLUDED.deep_sleep_duration,

                rem_sleep_duration =
                    EXCLUDED.rem_sleep_duration,

                cycle_strain =
                    EXCLUDED.cycle_strain,

                workout_data =
                    EXCLUDED.workout_data,

                health_score =
                    EXCLUDED.health_score,

                skin_temperature =
                    EXCLUDED.skin_temperature,

                spo2_percentage =
                    EXCLUDED.spo2_percentage
            """,

            (
                today,

                metrics.get(
                    "recovery_score",
                    0
                ),

                metrics.get(
                    "hrv",
                    0
                ),

                metrics.get(
                    "resting_heart_rate",
                    0
                ),

                metrics.get(
                    "sleep_score",
                    0
                ),

                metrics.get(
                    "sleep_duration",
                    0
                ),

                metrics.get(
                    "sleep_efficiency",
                    0
                ),

                metrics.get(
                    "deep_sleep_duration",
                    0
                ),

                metrics.get(
                    "rem_sleep_duration",
                    0
                ),

                metrics.get(
                    "cycle_strain",
                    0
                ),

                str(
                    metrics.get(
                        "workout_data",
                        ""
                    )
                ),

                metrics.get(
                    "health_score",
                    0
                ),

                metrics.get(
                    "skin_temperature"
                ),

                metrics.get(
                    "spo2_percentage"
                )
            )
        )


        conn.commit()


        print(
            "AUTO DAILY SAVE OK"
        )


        print(
            "BEFORE SELECT TEST"
        )


        print(
            "SAVED METRICS:",
            metrics
        )


        cur.execute(
            """
            SELECT
                report_date,
                recovery_score,
                hrv,
                resting_heart_rate,
                sleep_duration,
                cycle_strain,
                skin_temperature,
                spo2_percentage
            FROM daily_metrics
            WHERE report_date = %s
            LIMIT 1
            """,
            (
                today,
            )
        )


        latest_row = (
            cur.fetchone()
        )


        print(
            "LATEST DAILY ROW:",
            latest_row
        )


    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "SAVE DAILY DATA ERROR:",
            e
        )

        raise


    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


def save_hangboard_training(
    data
):

    conn = None
    cursor = None


    try:

        # =========================
        # 类型保护
        # =========================

        if not isinstance(
            data,
            dict
        ):

            raise ValueError(
                "hangboard data必须是dict"
            )


        # =========================
        # 数字转换函数
        # =========================

        def to_float(
            value
        ):

            if value is None:
                return None

            if value == "":
                return None

            if isinstance(
                value,
                (int, float)
            ):

                return float(
                    value
                )


            text = str(
                value
            ).strip()


            # 支持:
            # 10
            # +10
            # 10kg
            # +10 kg

            text = (
                text
                .replace(
                    "kg",
                    ""
                )
                .replace(
                    "KG",
                    ""
                )
                .strip()
            )


            return float(
                text
            )


        def to_int(
            value
        ):

            if value is None:
                return None

            if value == "":
                return None

            if isinstance(
                value,
                bool
            ):

                return int(
                    value
                )

            if isinstance(
                value,
                int
            ):

                return value

            if isinstance(
                value,
                float
            ):

                return int(
                    round(
                        value
                    )
                )


            text = str(
                value
            ).strip()


            # 防止类似:
            # "7秒"
            # "35 sec"

            number_text = ""

            decimal_found = False


            for char in text:

                if char.isdigit():

                    number_text += char

                elif (
                    char == "."
                    and not decimal_found
                ):

                    number_text += char

                    decimal_found = True

                elif (
                    char == "-"
                    and not number_text
                ):

                    number_text += char


            if not number_text:

                return None


            return int(
                round(
                    float(
                        number_text
                    )
                )
            )


        # =========================
        # 清理字段
        # =========================

        training_date = (
            str(
                data.get(
                    "training_date"
                )
            ).strip()
            if data.get(
                "training_date"
            ) is not None
            else None
        )


        protocol = (
            str(
                data.get(
                    "protocol"
                )
            ).strip()
            if data.get(
                "protocol"
            ) is not None
            else None
        )


        session_type = (
            str(
                data.get(
                    "session_type"
                )
            ).strip()
            if data.get(
                "session_type"
            ) not in [
                None,
                ""
            ]
            else None
        )


        edge_size = (
            str(
                data.get(
                    "edge_size"
                )
            ).strip()
            if data.get(
                "edge_size"
            ) not in [
                None,
                ""
            ]
            else None
        )


        grip_type = (
            str(
                data.get(
                    "grip_type"
                )
            ).strip()
            if data.get(
                "grip_type"
            ) not in [
                None,
                ""
            ]
            else None
        )


        added_weight = to_float(
            data.get(
                "added_weight"
            )
        )


        hold_seconds = to_int(
            data.get(
                "hold_seconds"
            )
        )


        duration = to_int(
            data.get(
                "duration"
            )
        )


        sets = to_int(
            data.get(
                "sets"
            )
        )


        total_hang_time = to_int(
            data.get(
                "total_hang_time"
            )
        )


        intensity = (
            str(
                data.get(
                    "intensity"
                )
            ).strip()
            if data.get(
                "intensity"
            ) not in [
                None,
                ""
            ]
            else None
        )


        finger_fatigue = to_int(
            data.get(
                "finger_fatigue"
            )
        )


        elbow_fatigue = to_int(
            data.get(
                "elbow_fatigue"
            )
        )


        recovery_after = to_int(
            data.get(
                "recovery_after"
            )
        )


        notes = (
            str(
                data.get(
                    "notes"
                )
            ).strip()
            if data.get(
                "notes"
            ) not in [
                None,
                ""
            ]
            else None
        )


        # =========================
        # 必填字段检查
        # =========================

        if not training_date:

            raise ValueError(
                "training_date不能为空"
            )


        if not protocol:

            raise ValueError(
                "protocol不能为空"
            )


        # =========================
        # 疲劳评分保护
        # =========================

        if (
            finger_fatigue is not None
            and not 0 <= finger_fatigue <= 10
        ):

            raise ValueError(
                "finger_fatigue必须在0-10之间"
            )


        if (
            elbow_fatigue is not None
            and not 0 <= elbow_fatigue <= 10
        ):

            raise ValueError(
                "elbow_fatigue必须在0-10之间"
            )


        if (
            recovery_after is not None
            and not 0 <= recovery_after <= 100
        ):

            raise ValueError(
                "recovery_after必须在0-100之间"
            )


        # =========================
        # DEBUG
        # =========================

        cleaned_data = {

            "training_date":
                training_date,

            "protocol":
                protocol,

            "session_type":
                session_type,

            "edge_size":
                edge_size,

            "grip_type":
                grip_type,

            "added_weight":
                added_weight,

            "hold_seconds":
                hold_seconds,

            "duration":
                duration,

            "sets":
                sets,

            "total_hang_time":
                total_hang_time,

            "intensity":
                intensity,

            "finger_fatigue":
                finger_fatigue,

            "elbow_fatigue":
                elbow_fatigue,

            "recovery_after":
                recovery_after,

            "notes":
                notes

        }


        print(
            "HANGBOARD CLEANED DATA:",
            cleaned_data
        )


        # =========================
        # 数据库
        # =========================

        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO hangboard_training_log
            (
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

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,

            (
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
        )


        conn.commit()


        print(
            "HANGBOARD DB INSERT SUCCESS"
        )


        return True


    except Exception as e:

        print(
            "SAVE HANGBOARD TRAINING ERROR:",
            repr(e)
        )


        if conn:

            conn.rollback()


        raise


    finally:

        if cursor:

            cursor.close()


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


def generate_daily_coach_report():

    import json


    print(
        "========== GENERATE DAILY COACH START =========="
    )


    # =========================
    # 1. 获取 WHOOP
    # =========================

    data = {

        "recovery":
            whoop_get(
                "/recovery"
            ),

        "cycle":
            whoop_get(
                "/cycle"
            ),

        "sleep":
            whoop_get(
                "/activity/sleep"
            ),

        "workout":
            whoop_get(
                "/activity/workout"
            )

    }


    # =========================
    # 2. 时间转换
    # =========================

    convert_utc_to_beijing(
        data
    )


    # =========================
    # 3. 提取指标
    # =========================

    metrics = (
        extract_daily_metrics(
            data
        )
    )


    print(
        "DAILY METRICS:",
        metrics
    )


    # =========================
    # 4. 保存每日指标
    # =========================

    save_daily_data(
        metrics
    )


    # =========================
    # 5. 分析数据
    # =========================

    weekly_data = (
        generate_weekly_analysis()
    )


    if not isinstance(
        weekly_data,
        dict
    ):

        weekly_data = {}


    training_load = (
        calculate_training_load()
    )


    if not isinstance(
        training_load,
        dict
    ):

        training_load = {}


    climbing_fatigue = (
        analyze_climbing_fatigue(
            training_load
        )
    )


    menstrual_data = (
        get_latest_menstrual_data()
    )


    temperature_data = (
        get_latest_temperature_data()
    )


    injury_data = (
        get_latest_injury_data()
    )


    data[
        "menstrual_data"
    ] = menstrual_data

    data[
        "temperature_data"
    ] = temperature_data

    data[
        "injury_data"
    ] = injury_data


    # =========================
    # 6. Max Hang只计算一次
    # =========================

    max_hang_decision = (
        calculate_max_hang_decision(
            metrics,
            training_load,
            weekly_data,
            injury_data
        )
    )


    max_hang_status = (
        max_hang_decision.get(
            "status",
            "conditional"
        )
    )


    print(
        "DAILY COACH MAX HANG STATUS:",
        max_hang_status
    )

    print(
        "DAILY COACH MAX HANG DECISION:",
        max_hang_decision
    )


    # =========================
    # 7. Strain只计算一次
    # =========================

    strain_plan = (
        calculate_strain_plan(
            metrics
        )
    )


    print(
        "DAILY COACH STRAIN PLAN:",
        strain_plan
    )


    # =========================
    # 8. Training Readiness只计算一次
    # =========================

    training_readiness = (
        calculate_training_readiness(
            metrics,
            training_load,
            weekly_data,
            strain_plan,
            max_hang_decision,
            injury_data
        )
    )


    print(
        "DAILY COACH TRAINING READINESS:",
        training_readiness
    )


    # =========================
    # 9. 基础报告
    # =========================

    report = (
        generate_ai_summary(
            data
        )
    )


    # =========================
    # 10. Coach Prompt
    # =========================

    ai_prompt = (
        generate_coach_prompt(
            metrics,
            training_load,
            weekly_data,
            climbing_fatigue,
            menstrual_data,
            temperature_data,
            injury_data,
            max_hang_decision,
            strain_plan,
            training_readiness
        )
    )


    print(
        "DEBUG PROMPT READY"
    )


    # =========================
    # 11. AI Coach
    # =========================

    ai_result = (
        generate_weekly_ai_summary(
            ai_prompt
        )
    )


    print(
        "DEBUG RAW AI:",
        repr(
            ai_result
        )
    )


    # =========================
    # 12. 解析AI
    # =========================

    ai_report = ""

    training_advice = ""

    risk_warning = ""


    try:

        if isinstance(
            ai_result,
            dict
        ):

            coach_json = (
                ai_result
            )


        else:

            raw = str(
                ai_result
            ).strip()


            if raw.startswith(
                "```"
            ):

                raw = raw.replace(
                    "```json",
                    ""
                )

                raw = raw.replace(
                    "```",
                    ""
                )

                raw = raw.strip()


            coach_json = (
                json.loads(
                    raw
                )
            )


        ai_report = (
            coach_json.get(
                "ai_report",
                ""
            )
        )


        training_advice = (
            coach_json.get(
                "training_advice",
                ""
            )
        )


        risk_warning = (
            coach_json.get(
                "risk_warning",
                ""
            )
        )


    except Exception as e:

        print(
            "JSON PARSE ERROR:",
            e
        )

        print(
            "FAILED AI:",
            repr(
                ai_result
            )
        )


        ai_report = str(
            ai_result
        )


    # =========================
    # 13. 保存日报
    # =========================

    saved = (
        save_daily_coach_report(

            metrics,

            training_load,

            ai_report,

            training_advice,

            risk_warning,

            menstrual_data,

            temperature_data,

            injury_data,

            max_hang_status,

            max_hang_decision,

            strain_plan,

            training_readiness

        )
    )


    if not saved:

        raise RuntimeError(
            "daily_coach_reports 保存失败"
        )


    print(
        "========== GENERATE DAILY COACH SUCCESS =========="
    )


    # =========================
    # 14. 返回普通dict
    # =========================

    return {

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
            injury_data,

        "max_hang_status":
            max_hang_status,

        "max_hang_decision":
            max_hang_decision,

        "strain_plan":
            strain_plan,

        "training_readiness":
            training_readiness

    }


@app.route("/whoop/auto-report")
def auto_report():

    print(
        "ENTER AUTO REPORT FUNCTION"
    )


    if not check_api_key():

        print(
            "API KEY FAILED"
        )

        return jsonify({

            "error":
                "unauthorized"

        }), 401


    print(
        "API KEY PASSED"
    )


    try:

        result = (
            generate_daily_coach_report()
        )


        return jsonify(
            result
        ), 200


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
