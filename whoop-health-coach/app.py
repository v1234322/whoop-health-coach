import json
import os
print("WHOOP VERSION TEST 2026-08-03")
import psycopg2

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, Response
import requests
import threading
import time


app = Flask(__name__)

app.json.ensure_ascii = False
app.config["JSON_AS_ASCII"] = False


# ============================
# WHOOP Dashboard 首页
# ============================

@app.route("/")
def home():

    status = "🟢 系统正常"

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
                    "🟢 恢复日\n"
                    "当前训练压力较低，适合增加Zone2有氧或轻力量训练。"
                )


            elif strain_value < 12:


                strain_text = (
                    "🟡 最佳训练区间\n"
                    "当前负荷适中，可以完成主要训练。"
                )


            elif strain_value < 17:


                strain_text = (
                    "🟠 高压力训练\n"
                    "注意睡眠和恢复。"
                )


            else:


                strain_text = (
                    "🔴 极高压力\n"
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


# =====================
# DATABASE CONNECTION
# =====================

def get_db_connection():

    return psycopg2.connect(
        os.environ.get(
            "DATABASE_URL"
        )
    )

    return conn


def generate_coach_advice(
    recovery_score,
    hrv,
    sleep_duration,
    sleep_debt,
    strain
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

# =====================
# DATABASE INIT
# =====================

def init_db():

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        # =================================
        # 创建 daily_metrics 主表
        # =================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (

            id SERIAL PRIMARY KEY,

            report_date TEXT,

            recovery_score FLOAT,

            hrv FLOAT,

            resting_heart_rate FLOAT,

            sleep_score FLOAT,

            sleep_duration FLOAT,

            sleep_efficiency FLOAT,

            deep_sleep_duration FLOAT,

            rem_sleep_duration FLOAT,

            cycle_strain FLOAT,

            workout_data JSONB

        )
        """)



        # =================================
        # 数据库自动迁移
        # 如果旧表没有字段，自动添加
        # =================================


        migrations = [

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS report_date TEXT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS recovery_score FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS hrv FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS resting_heart_rate FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS sleep_score FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS sleep_duration FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS sleep_efficiency FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS deep_sleep_duration FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS rem_sleep_duration FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS cycle_strain FLOAT
            """,

            """
            ALTER TABLE daily_metrics
            ADD COLUMN IF NOT EXISTS workout_data JSONB
            """
        ]


        for sql in migrations:

            cur.execute(sql)



        # =================================
        # Token 表
        # =================================

        cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (

            id SERIAL PRIMARY KEY,

            refresh_token TEXT,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
        """)



        conn.commit()


        cur.close()

        conn.close()


        print(
            "DATABASE INIT OK"
        )



    except Exception as e:


        print(
            "DATABASE INIT ERROR:",
            e
        )

@app.route("/privacy")
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


# =========================
# DATABASE INIT
# =========================

init_db()


# =========================
# ENVIRONMENT
# =========================

WHOOP_CLIENT_ID = os.environ.get(
    "WHOOP_CLIENT_ID",
    ""
).strip()



WHOOP_CLIENT_SECRET = os.environ.get(
    "WHOOP_CLIENT_SECRET",
    ""
).strip()



WHOOP_REFRESH_TOKEN = os.environ.get(
    "WHOOP_REFRESH_TOKEN",
    ""
).strip()



API_SECRET = os.environ.get(
    "API_SECRET",
    ""
).strip()



WHOOP_TOKEN_URL = (
    "https://api.prod.whoop.com/oauth/oauth2/token"
)



WHOOP_API_BASE = (
    "https://api.prod.whoop.com/developer/v2"
)




# =========================
# TOKEN CACHE
# =========================

ACCESS_TOKEN = None

ACCESS_TOKEN_EXPIRE = 0


TOKEN_LOCK = threading.Lock()


# =========================
# API KEY
# =========================

def check_api_key():


    key = request.headers.get(
        "X-API-Key"
    )


    return key == API_SECRET


# =====================
# WHOOP CALLBACK
# =====================

@app.route("/callback")
def callback():


    code = request.args.get(
        "code"
    )


    if not code:

        return jsonify({

            "error": "NO CODE",

            "params": dict(request.args)

        })


    print(
        "AUTH CODE:",
        code[:20]
    )


    response = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",

        data={

            "grant_type":
            "authorization_code",

            "code":
            code,

            "client_id":
            os.environ.get(
                "WHOOP_CLIENT_ID"
            ),

            "client_secret":
            os.environ.get(
                "WHOOP_CLIENT_SECRET"
            ),

            "redirect_uri":
            "https://whoop-health-coach.onrender.com/callback"

        }

    )


    print(
        "TOKEN STATUS:",
        response.status_code
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

    print(
    "REFRESH TOKEN:",
    refresh_token
)
    if refresh_token:

       save_refresh_token(
          refresh_token
       )

    return jsonify({

    "status":
    "WHOOP AUTH SUCCESS",

    "saved_refresh_token":
    True

})


# =========================
# AUTH CODE TOKEN
# =========================

@app.route("/whoop/token")
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


            "grant_type":
            "authorization_code",


            "code":
            code,


            "client_id":
            WHOOP_CLIENT_ID,


            "client_secret":
            WHOOP_CLIENT_SECRET,


            "redirect_uri":
            "https://whoop-health-coach.onrender.com/callback"


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



    return jsonify(
        r.json()
    )


# =====================
# TOKEN STORAGE
# =====================

def save_refresh_token(token):

    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute(
        """
        DELETE FROM tokens
        """
    )


    cur.execute(
        """
        INSERT INTO tokens
        (refresh_token)
        VALUES (%s)
        """,
        (token,)
    )


    conn.commit()


    cur.close()

    conn.close()


    print(
        "NEW REFRESH TOKEN SAVED"
    )



# =====================
# LOAD REFRESH TOKEN
# =====================

def load_refresh_token():


    conn = get_db_connection()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT refresh_token
        FROM tokens
        ORDER BY id DESC
        LIMIT 1
        """
    )


    result = cur.fetchone()


    cur.close()

    conn.close()


    if result:

        return result[0]


    return None


# =====================
# WHOOP Refresh Token
# =====================

def refresh_access_token():


    refresh_token = load_refresh_token()


    client_id = os.environ.get(
        "WHOOP_CLIENT_ID"
    )

    client_secret = os.environ.get(
        "WHOOP_CLIENT_SECRET"
    )


    print(
        "CLIENT ID:",
        bool(client_id)
    )

    print(
        "CLIENT SECRET:",
        bool(client_secret)
    )

    print(
        "REFRESH TOKEN:",
        bool(refresh_token)
    )


    if not refresh_token:

        raise Exception(
            "NO REFRESH TOKEN"
        )


    payload = {

        "grant_type":
        "refresh_token",

        "refresh_token":
        refresh_token,

        "client_id":
        client_id,

        "client_secret":
        client_secret

    }


    response = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",

        data=payload

    )


    print(
        "REFRESH STATUS:",
        response.status_code
    )


    print(
        "REFRESH RESPONSE:",
        response.text
    )


    response.raise_for_status()


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


    return access_token

# =========================
# WHOOP API GET
# =========================

def whoop_get(endpoint):


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



    if r.status_code == 401:


        token = refresh_access_token(
            True
        )


        r = requests.get(


            WHOOP_API_BASE + endpoint,


            headers={


                "Authorization":
                f"Bearer {token}"


            },


            timeout=30

        )




    print(
        "WHOOP STATUS:",
        r.status_code
    )



    r.raise_for_status()



    return r.json()


# =========================
# EXTRACT DAILY METRICS
# =========================

def extract_daily_metrics(data):

    result = {}


    # =====================
    # Recovery
    # =====================

    try:

        recovery_records = (
            data
            .get("recovery", {})
            .get("records", [])
        )

        recovery = (
            recovery_records[0]
            if recovery_records
            else {}
        )

        score = recovery.get("score") or {}

        result["recovery_score"] = score.get(
            "recovery_score"
        )

        result["hrv"] = score.get(
            "hrv_rmssd_milli"
        )

        result["resting_heart_rate"] = score.get(
            "resting_heart_rate"
        )

    except Exception as e:

        print(
            "RECOVERY PARSE ERROR:",
            e
        )

        result["recovery_score"] = None
        result["hrv"] = None
        result["resting_heart_rate"] = None


    # =====================
    # Sleep
    # =====================

    try:

        sleep_records = (
            data
            .get("sleep", {})
            .get("records", [])
        )

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
    # Cycle Strain
    # =====================

    try:

        cycle_records = (
            data
            .get("cycle", {})
            .get("records", [])
        )

        cycle = (
            cycle_records[0]
            if cycle_records
            else {}
        )

        cycle_score = (
            cycle.get("score") or {}
        )

        result["cycle_strain"] = (
            cycle_score.get("strain")
        )

    except Exception as e:

        print(
            "CYCLE PARSE ERROR:",
            e
        )

        result["cycle_strain"] = None


    # =====================
    # Workout
    # =====================

    result["workout_data"] = (
        data.get("workout", {})
    )


    return result

# =====================
# 保存每日历史数据 V6
# PostgreSQL
# =====================

def save_daily_data(metrics):

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        today = datetime.now().strftime(
            "%Y-%m-%d"
        )


        # 删除当天旧数据，避免重复
        cur.execute(
            """
            DELETE FROM daily_metrics
            WHERE report_date = %s
            """,
            (
                today,
            )
        )


        # 写入当天最新数据
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
                workout_data
            )

            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,

            (
                today,

                metrics.get(
                    "recovery_score"
                ),

                metrics.get(
                    "hrv"
                ),

                metrics.get(
                    "resting_heart_rate"
                ),

                metrics.get(
                    "sleep_score"
                ),

                metrics.get(
                    "sleep_duration"
                ),

                metrics.get(
                    "sleep_efficiency"
                ),

                metrics.get(
                    "deep_sleep_duration"
                ),

                metrics.get(
                    "rem_sleep_duration"
                ),

                metrics.get(
                    "cycle_strain"
                ),

                json.dumps(
                    metrics.get(
                        "workout_data",
                        {}
                    ),
                    ensure_ascii=False
                )
            )
        )


        conn.commit()

        cur.close()
        conn.close()


        print(
            "DAILY METRICS SAVED OK"
        )


    except Exception as e:

        print(
            "SAVE DAILY DATA ERROR:",
            str(e)
        )

# =====================
# UTC 转北京时间
# =====================

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


# =========================
# TODAY REPORT
# =========================

def get_whoop_data():

    try:

        conn = get_db_connection()

        cur = conn.cursor()


        cur.execute(
           """
           SELECT
               recovery_score,
               hrv,
               resting_heart_rate,
               sleep_score,
               sleep_duration,
               sleep_efficiency,
               cycle_strain
           FROM daily_metrics
           ORDER BY id DESC
           LIMIT 1
           """
       )


        row = cur.fetchone()


        print("DATABASE ROW:", row)


        cur.close()

        conn.close()


        if not row:

            return {
                "recovery": {
                    "score": 0,
                    "hrv": 0
                },

                "sleep": {
                    "duration": 0,
                    "performance": 0
                },

                "workout": {
                    "strain": 0
                }
            }



        return {

            "recovery": {
                "score": row[0],
                "hrv": row[1],
                "resting_hr": row[2]
            },


            "sleep": {
                "performance": row[3],
                "duration": row[4],
                "efficiency": row[5]
            },


            "workout": {
                "strain": row[6]
            }

        }


    except Exception as e:

        print("GET WHOOP DATA ERROR:", e)

        return {}

@app.route("/whoop/today")
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


    if recovery >=67:


        return """
        ✅ 今日适合训练

        推荐：
        - 力量训练45-60分钟
        - Zone2有氧40分钟

        建议目标 Strain:
        8-12
        """



    elif recovery>=34:


        return """
        🟡 中等恢复状态

        推荐：
        - Zone2轻松有氧
        - 技术训练
        - 拉伸恢复


        建议目标 Strain:
        5-8
        """



    else:


        return """
        🔴 恢复不足

        建议：
        - 休息
        - 散步
        - 拉伸


        避免：
        - HIIT
        - 大重量训练
        """
    

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

        <h3>{date}</h3>

        Recovery:
        {recovery:.1f}%<br>

        HRV:
        {hrv:.1f} ms<br>

        静息心率:
        {resting_hr:.1f} bpm<br>

        睡眠:
        {sleep:.2f} 小时<br>

        Strain:
        {strain:.2f}

        """


    days = len(data)


    avg_recovery = sum(recovery_list) / days
    avg_hrv = sum(hrv_list) / days
    avg_hr = sum(hr_list) / days
    avg_sleep = sum(sleep_list) / days
    avg_strain = sum(strain_list) / days


    # =========================
    # AI 周总结
    # =========================

    if avg_recovery >= 70:

        ai_summary = """
    🟢 本周恢复状态良好。
    
    Recovery 平均水平较高，
    HRV表现稳定，身体恢复能力充足。

    训练方面可以保持正常计划，
    未来1-3天建议：
    1. 保持力量训练或Zone2有氧
    2. 控制单日 Strain 在8-12
    3. 保证睡眠7.5小时以上
    """


    elif avg_recovery >= 40:

        ai_summary = """
    🟡 本周恢复状态一般。

    身体可以支持训练，
    但需要注意训练负荷不要连续增加。

    未来1-3天建议：
    1. 降低高强度训练比例
    2. 增加恢复性有氧
    3. 优先保证睡眠质量
    """


    else:

        ai_summary = """
    🔴 本周恢复不足。

    可能存在累积疲劳。

    未来1-3天建议：
    1. 降低训练强度
    2. 增加睡眠时间
    3. 避免高 Strain训练
    """

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

        strain_comment = "🔴 多天高 Strain，存在过劳风险"

    elif high_strain_days > 0:

        strain_comment = "🟡 有高负荷训练，需要匹配恢复"

    else:

        strain_comment = "🟢 当前训练负荷合理"



    # ======================
    # 状态判断
    # ======================

    if avg_recovery >= 67:

        status = "🟢 良好"

    elif avg_recovery >= 34:

        status = "🟡 需小心"

    else:

        status = "🔴 危险"



    # ======================
    # 自动训练建议
    # ======================

    if avg_recovery >= 67:

        training_plan = """
        可以正常训练

        推荐：
        - 力量训练
        - Zone2有氧

        目标 Strain:
        8-12
        """

    elif avg_recovery >= 34:

        training_plan = """
        建议降低训练量

        推荐：
        - 轻松有氧
        - 技术训练
        - 拉伸恢复

        目标 Strain:
        5-8
        """

    else:

        training_plan = """
        建议恢复

        避免：
        - HIIT
        - 高强度力量

        优先睡眠和恢复
        """



    return f"""

<h1>
WHOOP 最近7天私人健康报告
</h1>


<h2>
整体状态：
{status}
</h2>


<h2>📊 平均指标</h2>

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



<h2>📈 Recovery趋势</h2>

{recovery_trend}



<h2>❤️ HRV趋势</h2>

{hrv_comment}



<h2>💤 睡眠债分析</h2>

累计睡眠债:
<b>{sleep_debt:.2f} 小时</b>

<br>

{sleep_comment}



<h2>🏃 Strain风险</h2>

{strain_comment}


<h2>📅 每日记录</h2>

{daily_html}



<h2>🤖 私人教练建议</h2>

{training_plan}



<h2>🧠 AI 周总结</h2>

<p>
{ai_summary}
</p>


<h2>未来1-3天</h2>

1. 保证睡眠 ≥8小时<br>
2. 根据 Recovery 调整训练<br>
3. 避免连续高 Strain


"""



@app.route("/whoop/week")
def whoop_week():
    try:
        data = get_whoop_week_data()
        report = generate_week_report(data)
        return report

    except Exception as e:
        print("WEEK ERROR:", e)
        return "暂无数据"


def generate_health_report(data):

    print("### USING NEW HEALTH REPORT ###")

    recovery = data.get("recovery", {})

    # =========================
    # 数据读取
    # =========================
    recovery = data.get("recovery", {})
    sleep = data.get("sleep", {})
    workout = data.get("workout", {})


    # =========================
    # 数据类型统一
    # =========================
    try:
        recovery_score = float(recovery.get("score", 0))
        hrv = float(recovery.get("hrv", 0))
        resting_hr = float(recovery.get("resting_hr", 0))

        sleep_duration = float(sleep.get("duration", 0))
        sleep_performance = float(sleep.get("performance", 0))
        sleep_efficiency = float(sleep.get("efficiency", 0))

        strain = float(workout.get("strain", 0))

    except Exception as e:
        print("数字转换失败:", e)

        recovery_score = 0
        hrv = 0
        resting_hr = 0
        sleep_duration = 0
        sleep_performance = 0
        sleep_efficiency = 0
        strain = 0


    print("DEBUG DATA:", data)


    # =========================
    # 基础状态
    # =========================
    status = "🟢 良好"

    sleep_consistency = "稳定"

    sleep_debt = 0

    risk_warning = "暂无明显风险"


    # =========================
    # 训练信息
    # =========================
    avg_hr = resting_hr
    max_hr = resting_hr

    workout_start = "暂无训练记录"
    workout_end = "暂无训练记录"
    workout_duration = "暂无数据"
    workout_type = "训练"

    sport_name = "综合训练"


    training_advice = "根据 Recovery 调整训练强度"


    # =========================
    # AI 教练建议
    # =========================
    coach_advice = generate_coach_advice(
        recovery_score,
        hrv,
        sleep_duration,
        sleep_debt,
        strain
    )

    if isinstance(coach_advice, dict):
        coach_advice = "<br>".join(coach_advice.values())


    print("DEBUG TYPES:")
    print(type(recovery_score))
    print(type(hrv))
    print(type(sleep_duration))
    print(type(strain))
    print(type(sleep_debt))


    return f"""

<div style="
font-family:Arial;
padding:20px;
line-height:1.8;
">

<h1>
🏋️ WHOOP 今日健康报告
</h1>


<h2>
状态：
{status}
</h2>


<hr>


<h2>❤️ 恢复</h2>

<p>
Recovery：
<b>{recovery_score:.1f}%</b>
</p>

<p>
HRV：
<b>{hrv:.1f} ms</b>
</p>

<p>
静息心率：
<b>{resting_hr:.0f} bpm</b>
</p>


<hr>


<h2>💤 睡眠</h2>

<p>
睡眠时长：
<b>{sleep_duration:.2f} 小时</b>
</p>

<p>
睡眠表现：
<b>{sleep_performance:.1f}%</b>
</p>

<p>
睡眠效率：
<b>{sleep_efficiency:.1f}%</b>
</p>


<hr>


<h2>🏃 训练</h2>

<p>
Strain：
<b>{strain:.2f}</b>
</p>


<p>
平均心率：
<b>{avg_hr:.0f} bpm</b>
</p>


<p>
最大心率：
<b>{max_hr:.0f} bpm</b>
</p>


<hr>


<h2>🤖 训练建议</h2>

<p>
{training_advice}
</p>


<hr>


<h2>🧠 AI 教练建议</h2>

<p>
{coach_advice}
</p>


<hr>


<h2>📅 未来1-3天</h2>

<p>
1. 保证充足睡眠恢复<br>
2. 根据 Recovery 调整训练强度<br>
3. 避免连续高 Strain
</p>


</div>

"""

# =====================
# DAILY AUTO REPORT
# =====================

@app.route("/whoop/auto-report")
def auto_report():


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


    convert_utc_to_beijing(data)


    report = generate_health_report(data)


    metrics = extract_daily_metrics(
        data
    )


    save_daily_data(
        metrics
    )


    return jsonify({

        "status":
        "daily report generated",


        "report":
        report

    })


# ============================
# WHOOP TREND REPORT V5.1
# 最近7天趋势分析
# ============================

@app.route("/whoop/trend")
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

                "recovery": r[1],

                "hrv": r[2],

                "resting_hr": r[3],

                "sleep": r[4],

                "sleep_score": r[5],

                "strain": r[6]

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

            risk_level = "🟢 低风险"


        elif len(risks) <= 2:

            risk_level = "🟡 中风险"


        else:

            risk_level = "🔴 高风险"





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

            risk_html = "✅ 暂未发现明显恢复风险"



        coach_html = "<br>".join(
            [
                "• " + c
                for c in coach
            ]
        )





        return f"""

<!DOCTYPE html>

<html lang="zh-CN">

<head>


<meta charset="UTF-8">


<meta name="viewport"
content="width=device-width,initial-scale=1">


<title>
WHOOP AI Coach Trend
</title>


<style>


body {{

font-family:Arial,sans-serif;

background:#f4f5f7;

padding:20px;

}}



.container {{

max-width:800px;

margin:auto;

}}



.card {{

background:white;

padding:25px;

border-radius:18px;

margin-bottom:18px;

box-shadow:
0 3px 12px rgba(0,0,0,.08);

}}



.value {{

font-size:32px;

font-weight:bold;

}}



table {{

width:100%;

border-collapse:collapse;

}}



td,th {{

padding:10px;

border-bottom:1px solid #ddd;

}}



.button {{

display:block;

background:#111;

color:white;

padding:14px;

border-radius:12px;

text-align:center;

text-decoration:none;

}}



</style>


</head>



<body>


<div class="container">


<div class="card">

<h1>
WHOOP AI Coach
</h1>


<h2>
最近7天趋势
</h2>


<p>
数据天数：
{len(history)}
天
</p>


</div>





<div class="card">

<h3>
训练准备度 Readiness
</h3>


<div class="value">

{readiness}/100

</div>


<p>
综合 Recovery、睡眠、训练压力
</p>


</div>





<div class="card">

<h3>
平均恢复指标
</h3>


<p>
Recovery：
{avg_recovery}%
</p>


<p>
HRV：
{avg_hrv} ms
</p>


<p>
静息心率：
{avg_resting_hr} bpm
</p>


<p>
睡眠：
{avg_sleep} 小时
</p>


<p>
睡眠评分：
{avg_sleep_score}%
</p>


<p>
平均

"""

    except Exception as e:

        return str(e)


            
# =========================
# START SERVER
# =========================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=10000

    )
