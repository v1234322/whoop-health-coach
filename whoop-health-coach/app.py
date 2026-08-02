import json
import os
import psycopg2

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
import requests
import threading
import time


app = Flask(__name__)


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


        cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (

            id SERIAL PRIMARY KEY,

            date TEXT,

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


# =========================
# CALLBACK
# =========================

@app.route("/callback")
def callback():


    code = request.args.get(
        "code"
    )


    if not code:

        return jsonify(
            {
                "error":
                "missing code"
            }
        )



    return jsonify(
        {
            "message":
            "code received",

            "code":
            code
        }
    )




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

    os.environ["WHOOP_REFRESH_TOKEN"] = token



def load_refresh_token():

    return os.environ.get(
        "WHOOP_REFRESH_TOKEN"
    )
    


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



    # Recovery

    try:

        recovery = (

            data

            .get(
                "recovery",
                {}
            )

            .get(
                "records",
                [{}]
            )[0]

        )


        score = recovery.get(
            "score",
            {}
        )


        result["recovery_score"] = (
            score.get(
                "recovery_score"
            )
        )


        result["hrv"] = (
            score.get(
                "hrv_rmssd_milli"
            )
        )


        result["resting_heart_rate"] = (
            score.get(
                "resting_heart_rate"
            )
        )


    except Exception:


        result["recovery_score"] = None

        result["hrv"] = None

        result["resting_heart_rate"] = None




    # Sleep


    try:

        sleep = (

            data

            .get(
                "sleep",
                {}
            )

            .get(
                "records",
                [{}]
            )[0]

        )


        sleep_score_data = (

            sleep

            .get(
                "score",
                {}
            )

        )


        # 睡眠评分

        result["sleep_score"] = (

            sleep_score_data

            .get(
                "sleep_performance_percentage"
            )

        )



        # 睡眠时长



        duration = (

            sleep_score_data

            .get(
                "stage_summary",
                {}
            )

            .get(
                "total_in_bed_time_milli"
            )

        )



        # 备用字段

        if not duration:


            duration = (

                sleep_score_data

                .get(
                    "total_sleep_time_milli"
                )

            )



        if duration:


            result["sleep_duration"] = (

                duration

                /

                3600000

            )


        else:


            result["sleep_duration"] = None



        # 睡眠效率



        result["sleep_efficiency"] = (

            sleep_score_data

            .get(
                "sleep_efficiency_percentage"
            )

        )


        # 深睡时间


        deep_sleep = (

            sleep_score_data

            .get(
                "stage_summary",
                {}
            )

            .get(
                "deep_sleep_time_milli"
            )

        )



        if deep_sleep:


            result["deep_sleep_duration"] = (

                deep_sleep

                /

                3600000

            )


        else:


            result["deep_sleep_duration"] = None



        # REM时间


        rem_sleep = (

            sleep_score_data

            .get(
                "stage_summary",
                {}
            )

            .get(
                "rem_sleep_time_milli"
            )

        )



        if rem_sleep:


            result["rem_sleep_duration"] = (

                rem_sleep

                /

                3600000

            )


        else:


            result["rem_sleep_duration"] = None




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



    # Cycle Strain

    try:


        cycle = (

            data

            .get(
                "cycle",
                {}
            )

            .get(
                "records",
                [{}]
            )[0]

        )


        result["cycle_strain"] = (

            cycle

            .get(
                "score",
                {}
            )

            .get(
                "strain"
            )

        )


    except Exception:


        result["cycle_strain"] = None





    # Workout

    result["workout_data"] = (

        data.get(
            "workout",
            {}
        )

    )



    return result

# =====================
# 保存每日历史数据 V3
# =====================

def save_daily_data(metrics):

    file = "history.json"


    history = []


    # 读取旧数据

    if os.path.exists(file):

        try:

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                history = json.load(f)


        except Exception:

            history = []



    # 添加日期

    metrics["date"] = datetime.now().strftime(
        "%Y-%m-%d"
    )



    history.append(metrics)



    # 保存最近30天

    history = history[-30:]



    with open(
        file,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2
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


    # 时间转换

    convert_utc_to_beijing(
        data
    )


    # 保存历史

    try:

        metrics = extract_daily_metrics(
            data
        )


        save_daily_data(
            metrics
        )


    except Exception as e:

        print(
            "SAVE ERROR:",
            e
        )



    report = generate_health_report(
        data
    )


    return jsonify({

        "date":
        datetime.now().strftime(
            "%Y-%m-%d"
        ),


        "timezone":
        "Asia/Shanghai UTC+8",


        "whoop_data":
        data,


        "coach_report":
        report

    })


# =========================
# HISTORY REPORT
# 最近7天
# =========================

@app.route("/whoop/history")
def history_report():


    file = "history.json"



    if not os.path.exists(file):

        return jsonify({

            "status":
            "empty",

            "message":
            "暂无历史数据"

        })



    with open(
        file,
        "r",
        encoding="utf-8"
    ) as f:

        history = json.load(f)



    last7 = history[-7:]



    return jsonify({

        "status":
        "success",


        "days":
        len(last7),


        "history":
        last7

    })



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
# HEALTH CHECK
# =========================


@app.route("/")
def home():


    return (

        "WHOOP Health Coach Running"

    )



# =========================
# START SERVER
# =========================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=10000

    )
