import json
import os
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
        # Recovery 状态判断
        # =====================

        if recovery is not None and recovery >= 80:


            status = "🟢 今日状态：良好"


            advice = (
                "恢复状态优秀，可以进行正常训练。"
                "建议今日 Strain 控制在 10-12。"
            )


        elif recovery is not None and recovery >= 50:


            status = "🟡 今日状态：需注意"


            advice = (
                "恢复一般，建议中等强度训练。"
                "避免连续高负荷。"
            )


        else:


            status = "🔴 今日状态：恢复不足"


            advice = (
                "建议优先恢复，安排低强度活动。"
            )




        # =====================
        # Strain 解释
        # =====================

        if strain is not None:


            strain_value = float(strain)


            if strain_value < 7:


                strain_text = (
                    "低训练负荷恢复日，"
                    "适合恢复、有氧或轻训练。"
                )


            elif strain_value < 12:


                strain_text = (
                    "正常训练区间，"
                    "可以安排主要训练。"
                )


            elif strain_value < 15:


                strain_text = (
                    "较高训练负荷，"
                    "注意睡眠和恢复质量。"
                )


            else:


                strain_text = (
                    "高负荷训练日，"
                    "建议减少额外压力。"
                )


        else:


            strain_text = "暂无训练压力数据"




        # =====================
        # 显示格式
        # =====================

        recovery_display = (

            f"{round(recovery,1)}%"

            if isinstance(recovery,(int,float))

            else "-"

        )


        hrv_display = (

            f"{round(hrv,2)} ms"

            if isinstance(hrv,(int,float))

            else "-"

        )


        sleep_display = (

            f"{round(sleep,2)} 小时"

            if isinstance(sleep,(int,float))

            else "-"

        )


        strain_display = (

            f"{round(strain,2)}"

            if isinstance(strain,(int,float))

            else "-"

        )





        return f"""

<!DOCTYPE html>

<html lang="zh-CN">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1">


<title>WHOOP AI Coach</title>


<style>


body {{

font-family:Arial,sans-serif;

background:#f4f5f7;

margin:0;

padding:20px;

}}



.container {{

max-width:700px;

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



.button {{

display:block;

padding:14px;

background:#111;

color:white;

text-decoration:none;

border-radius:12px;

text-align:center;

margin-top:10px;

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
{status}
</h2>


<p>
最新数据：
{date}
</p>

</div>




<div class="card">

<h3>
Recovery
</h3>

<div class="value">
{recovery_display}
</div>

</div>





<div class="card">

<h3>
HRV
</h3>

<div class="value">
{hrv_display}
</div>

</div>





<div class="card">

<h3>
睡眠
</h3>

<div class="value">
{sleep_display}
</div>

</div>





<div class="card">

<h3>
训练压力 Strain
</h3>

<div class="value">
{strain_display}
</div>


<p>
{strain_text}
</p>

</div>






<div class="card">

<h3>
AI 教练建议
</h3>

<p>
{advice}
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

生成最新报告

</a>


</div>



</div>


</body>

</html>


"""



    except Exception as e:


        return f"""

<h1>
WHOOP Dashboard Error
</h1>


<p>
{str(e)}
</p>

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

@app.route("/whoop/today")
def today():

    ...


# =====================
# AI 健康报告 V2
# =====================

def generate_health_report(data):

    ...


    return report



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
# WHOOP TREND REPORT V5
# 最近7天可视化健康报告
# ============================

@app.route("/whoop/trend")
def trend_report():

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
                sleep_score,
                sleep_duration,
                sleep_efficiency,
                cycle_strain
            FROM daily_metrics
            ORDER BY report_date DESC, id DESC
            LIMIT 7
            """
        )

        rows = cur.fetchall()

        if not rows:

            return Response(
                """
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport"
                          content="width=device-width, initial-scale=1">
                    <title>WHOOP 趋势报告</title>
                </head>

                <body style="
                    font-family: Arial, sans-serif;
                    max-width: 760px;
                    margin: 60px auto;
                    padding: 20px;
                    color: #222;
                ">
                    <h1>WHOOP 最近7天趋势</h1>
                    <p>暂无历史数据。</p>
                    <p>请先运行一次：</p>
                    <code>/whoop/auto-report</code>
                </body>
                </html>
                """,
                mimetype="text/html"
            )

        # SQL结果为最新在前，反转后变成最旧到最新
        rows = list(reversed(rows))

        history = []

        recovery_values = []
        hrv_values = []
        resting_hr_values = []
        sleep_score_values = []
        sleep_duration_values = []
        sleep_efficiency_values = []
        strain_values = []

        for row in rows:

            item = {
                "date": row[0],
                "recovery": row[1],
                "hrv": row[2],
                "resting_heart_rate": row[3],
                "sleep_score": row[4],
                "sleep_duration": row[5],
                "sleep_efficiency": row[6],
                "strain": row[7]
            }

            history.append(item)

            if row[1] is not None:
                recovery_values.append(float(row[1]))

            if row[2] is not None:
                hrv_values.append(float(row[2]))

            if row[3] is not None:
                resting_hr_values.append(float(row[3]))

            if row[4] is not None:
                sleep_score_values.append(float(row[4]))

            if row[5] is not None:
                sleep_duration_values.append(float(row[5]))

            if row[6] is not None:
                sleep_efficiency_values.append(float(row[6]))

            if row[7] is not None:
                strain_values.append(float(row[7]))

        def average(values):

            if not values:
                return None

            return round(
                sum(values) / len(values),
                2
            )

        def format_value(value, suffix=""):

            if value is None:
                return "暂无数据"

            return f"{value}{suffix}"

        def trend_text(values, threshold):

            # 少于3天不做强趋势判断
            if len(values) < 3:
                return "数据不足"

            oldest = values[0]
            latest = values[-1]
            change = latest - oldest

            if change >= threshold:
                return "明显上升"

            if change <= -threshold:
                return "明显下降"

            return "基本稳定"

        avg_recovery = average(recovery_values)
        avg_hrv = average(hrv_values)
        avg_resting_hr = average(resting_hr_values)
        avg_sleep_score = average(sleep_score_values)
        avg_sleep_duration = average(sleep_duration_values)
        avg_sleep_efficiency = average(sleep_efficiency_values)
        avg_strain = average(strain_values)

        recovery_trend = trend_text(
            recovery_values,
            5
        )

        hrv_trend = trend_text(
            hrv_values,
            5
        )

        sleep_trend = trend_text(
            sleep_duration_values,
            0.5
        )

        # =====================
        # 总体状态判断
        # =====================

        if (
            avg_recovery is not None
            and avg_recovery >= 80
        ):

            status_icon = "🟢"
            status_text = "良好"

        elif (
            avg_recovery is not None
            and avg_recovery >= 50
        ):

            status_icon = "🟡"
            status_text = "需小心"

        elif avg_recovery is not None:

            status_icon = "🔴"
            status_text = "危险"

        else:

            status_icon = "⚪"
            status_text = "数据不足"

        # =====================
        # 风险判断
        # =====================

        risks = []

        short_sleep_days = sum(
            1
            for value in sleep_duration_values
            if value < 6
        )

        low_recovery_days = sum(
            1
            for value in recovery_values
            if value < 50
        )

        high_strain_days = sum(
            1
            for value in strain_values
            if value > 14
        )

        if short_sleep_days >= 2:

            risks.append(
                f"最近记录中有 {short_sleep_days} 天睡眠少于6小时，存在睡眠债风险。"
            )

        if low_recovery_days >= 2:

            risks.append(
                f"最近记录中有 {low_recovery_days} 天恢复低于50，身体可能处于累积疲劳状态。"
            )

        if high_strain_days >= 2:

            risks.append(
                f"最近记录中有 {high_strain_days} 天 Strain 高于14，训练压力偏高。"
            )

        if (
            hrv_trend == "明显下降"
            and avg_resting_hr is not None
        ):

            risks.append(
                "HRV呈下降趋势，需要关注睡眠、压力、疲劳或身体不适。"
            )

        if not risks:

            risks.append(
                "目前未发现明显的恢复、睡眠或训练失衡风险。"
            )

        # =====================
        # 未来1–3天建议
        # =====================

        advice = []

        if (
            avg_sleep_duration is not None
            and avg_sleep_duration < 7
        ):

            advice.append(
                "未来1–3天优先保证至少7小时睡眠，尽量固定入睡时间。"
            )

        if (
            avg_recovery is not None
            and avg_recovery < 50
        ):

            advice.append(
                "训练以休息、散步、拉伸或低强度恢复性有氧为主。"
            )

        elif (
            avg_recovery is not None
            and avg_recovery >= 80
        ):

            advice.append(
                "恢复总体良好，可安排正常训练，但避免连续多天高 Strain。"
            )

        else:

            advice.append(
                "建议保持中等训练强度，并根据当天 Recovery 再调整训练量。"
            )

        if hrv_trend == "明显下降":

            advice.append(
                "若HRV继续下降，建议把训练容量降低20%–30%，并观察静息心率。"
            )

        latest = history[-1]

        risk_html = "".join(
            f"<li>{risk}</li>"
            for risk in risks
        )

        advice_html = "".join(
            f"<li>{item}</li>"
            for item in advice
        )

        history_rows = ""

        for item in reversed(history):

            history_rows += f"""
            <tr>
                <td>{item["date"]}</td>
                <td>{format_value(item["recovery"], "%")}</td>
                <td>{format_value(item["hrv"], " ms")}</td>
                <td>{format_value(item["sleep_duration"], " h")}</td>
                <td>{format_value(item["strain"])}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>

        <html lang="zh-CN">

        <head>

            <meta charset="UTF-8">

            <meta name="viewport"
                  content="width=device-width, initial-scale=1">

            <title>WHOOP 最近7天趋势</title>

            <style>

                body {{
                    font-family:
                        -apple-system,
                        BlinkMacSystemFont,
                        "Segoe UI",
                        Arial,
                        sans-serif;

                    background: #f4f5f7;
                    color: #191919;
                    margin: 0;
                    padding: 24px;
                }}

                .container {{
                    max-width: 860px;
                    margin: 0 auto;
                }}

                .header {{
                    background: #111;
                    color: white;
                    border-radius: 18px;
                    padding: 28px;
                    margin-bottom: 18px;
                }}

                .header h1 {{
                    margin: 0 0 12px 0;
                    font-size: 30px;
                }}

                .status {{
                    font-size: 22px;
                    font-weight: 700;
                }}

                .subtext {{
                    color: #cfcfcf;
                    margin-top: 8px;
                }}

                .grid {{
                    display: grid;
                    grid-template-columns:
                        repeat(auto-fit, minmax(180px, 1fr));
                    gap: 14px;
                    margin-bottom: 18px;
                }}

                .card {{
                    background: white;
                    border-radius: 16px;
                    padding: 20px;
                    box-shadow:
                        0 3px 14px rgba(0, 0, 0, 0.07);
                }}

                .label {{
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 8px;
                }}

                .value {{
                    font-size: 27px;
                    font-weight: 750;
                }}

                .trend {{
                    margin-top: 8px;
                    color: #555;
                    font-size: 14px;
                }}

                h2 {{
                    margin-top: 0;
                    font-size: 21px;
                }}

                ul {{
                    padding-left: 22px;
                    line-height: 1.7;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 14px;
                }}

                th,
                td {{
                    text-align: left;
                    padding: 11px 8px;
                    border-bottom: 1px solid #e9e9e9;
                }}

                th {{
                    color: #666;
                }}

                .footer {{
                    text-align: center;
                    color: #777;
                    font-size: 13px;
                    margin: 25px 0;
                }}

            </style>

        </head>

        <body>

            <div class="container">

                <div class="header">

                    <h1>WHOOP 最近7天趋势</h1>

                    <div class="status">
                        {status_icon} 总体状态：{status_text}
                    </div>

                    <div class="subtext">
                        已记录 {len(history)} 天 ·
                        最新数据日期：{latest["date"]} ·
                        北京时间 UTC+8
                    </div>

                </div>


                <div class="grid">

                    <div class="card">

                        <div class="label">
                            平均 Recovery
                        </div>

                        <div class="value">
                            {format_value(avg_recovery, "%")}
                        </div>

                        <div class="trend">
                            趋势：{recovery_trend}
                        </div>

                    </div>


                    <div class="card">

                        <div class="label">
                            平均 HRV
                        </div>

                        <div class="value">
                            {format_value(avg_hrv, " ms")}
                        </div>

                        <div class="trend">
                            趋势：{hrv_trend}
                        </div>

                    </div>


                    <div class="card">

                        <div class="label">
                            平均睡眠
                        </div>

                        <div class="value">
                            {format_value(avg_sleep_duration, " h")}
                        </div>

                        <div class="trend">
                            趋势：{sleep_trend}
                        </div>

                    </div>


                    <div class="card">

                        <div class="label">
                            平均 Strain
                        </div>

                        <div class="value">
                            {format_value(avg_strain)}
                        </div>

                        <div class="trend">
                            训练压力
                        </div>

                    </div>

                </div>


                <div class="grid">

                    <div class="card">

                        <h2>睡眠与心率</h2>

                        <p>
                            平均睡眠表现：
                            <strong>
                                {format_value(avg_sleep_score, "%")}
                            </strong>
                        </p>

                        <p>
                            平均睡眠效率：
                            <strong>
                                {format_value(avg_sleep_efficiency, "%")}
                            </strong>
                        </p>

                        <p>
                            平均静息心率：
                            <strong>
                                {format_value(avg_resting_hr, " bpm")}
                            </strong>
                        </p>

                    </div>


                    <div class="card">

                        <h2>风险提示</h2>

                        <ul>
                            {risk_html}
                        </ul>

                    </div>

                </div>


                <div class="card"
                     style="margin-bottom:18px;">

                    <h2>未来1–3天建议</h2>

                    <ul>
                        {advice_html}
                    </ul>

                </div>


                <div class="card">

                    <h2>最近记录</h2>

                    <div style="overflow-x:auto;">

                        <table>

                            <thead>

                                <tr>
                                    <th>日期</th>
                                    <th>恢复</th>
                                    <th>HRV</th>
                                    <th>睡眠</th>
                                    <th>Strain</th>
                                </tr>

                            </thead>

                            <tbody>
                                {history_rows}
                            </tbody>

                        </table>

                    </div>

                </div>


                <div class="footer">
                    WHOOP 健康教练 · 仅供健康趋势参考
                </div>

            </div>

        </body>

        </html>
        """

        return Response(
            html,
            mimetype="text/html"
        )


    except Exception as e:

        print(
            "TREND REPORT ERROR:",
            str(e)
        )

        return Response(
            f"""
            <h1>趋势报告生成失败</h1>
            <p>{str(e)}</p>
            """,
            status=500,
            mimetype="text/html"
        )


    finally:

        if cur is not None:

            try:
                cur.close()

            except Exception:
                pass

        if conn is not None:

            try:
                conn.close()

            except Exception:
                pass
# =====================
# AI 健康报告 V2
# =====================

def generate_health_report(data):


    recovery = data.get(
        "recovery",
        {}
    )

    sleep = data.get(
        "sleep",
        {}
    )

    cycle = data.get(
        "cycle",
        {}
    )

    workout = data.get(
        "workout",
        {}
    )



    # =====================
    # Recovery
    # =====================


    recovery_record = recovery.get(
        "records",
        [{}]
    )[0]


    recovery_score_data = recovery_record.get(
        "score",
        {}
    )


    recovery_score = recovery_score_data.get(
        "recovery_score",
        0
    )


    hrv = recovery_score_data.get(
        "hrv_rmssd_milli",
        0
    )


    resting_hr = recovery_score_data.get(
        "resting_heart_rate",
        0
    )



    # =====================
    # Sleep
    # =====================


    sleep_record = sleep.get(
        "records",
        [{}]
    )[0]


    sleep_score = sleep_record.get(
        "score",
        {}
    )


    stage = sleep_score.get(
        "stage_summary",
        {}
    )


    total_sleep_ms = (

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


    sleep_hours = round(
        total_sleep_ms / 3600000,
        2
    )


    sleep_performance = sleep_score.get(
        "sleep_performance_percentage",
        0
    )


    sleep_efficiency = sleep_score.get(
        "sleep_efficiency_percentage",
        0
    )


    sleep_consistency = sleep_score.get(
        "sleep_consistency_percentage",
        0
    )



    # =====================
    # Workout
    # =====================


    workout_records = workout.get(
        "records",
        []
    )


    latest_workout = (

        workout_records[0]

        if workout_records

        else {}

    )


    workout_score = latest_workout.get(
        "score",
        {}
    )


    strain = workout_score.get(
        "strain",
        0
    )


    avg_hr = workout_score.get(
        "average_heart_rate",
        0
    )


    max_hr = workout_score.get(
        "max_heart_rate",
        0
    )


    sport_name = latest_workout.get(
        "sport_name",
        "无训练"
    )



    workout_start = latest_workout.get(
        "start",
        ""
    )


    workout_end = latest_workout.get(
        "end",
        ""
    )



    # =====================
    # 状态判断
    # =====================


    if recovery_score >= 80:

        status = "🟢 良好"

    elif recovery_score >= 50:

        status = "🟡 需小心"

    else:

        status = "🔴 危险"



    if sleep_hours < 6:

        training_advice = (
            "恢复不错，但睡眠不足，"
            "建议降低训练容量"
        )

    elif recovery_score >= 80:

        training_advice = (
            "恢复优秀，可以进行正常训练，"
            "但注意不要连续高负荷"
        )

    else:

        training_advice = (
            "保持中低强度训练"
        )



    report = f"""

WHOOP 今日健康报告


【总览】

状态：
{status}

Recovery：
{recovery_score}%



【恢复】

HRV：
{hrv:.1f} ms

静息心率：
{resting_hr:.0f} bpm



【睡眠】

睡眠时长：
{sleep_hours} 小时

睡眠表现：
{sleep_performance}%

睡眠效率：
{sleep_efficiency}%

睡眠规律：
{sleep_consistency}%



【训练】

运动类型：
{sport_name}

训练 Strain：
{strain}

平均心率：
{avg_hr} bpm

最大心率：
{max_hr} bpm

开始：
{workout_start}

结束：
{workout_end}



【训练建议】

{training_advice}



【未来1-3天建议】

1. 保证充足睡眠恢复

2. 根据 Recovery 调整训练强度

3. 避免连续多天高 Strain


"""


    return report


# =========================
# START SERVER
# =========================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=10000

    )
