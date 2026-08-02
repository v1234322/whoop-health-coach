import os
import time
import threading
import requests

from flask import Flask, request, jsonify


from database import (
    init_db,
    save_refresh_token,
    load_refresh_token,
    save_daily_data
)


from coach import (
    generate_health_report
)



app = Flask(__name__)


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


# =========================
# REFRESH ACCESS TOKEN
# =========================

def refresh_access_token(force=False):

    global ACCESS_TOKEN
    global ACCESS_TOKEN_EXPIRE
    global WHOOP_REFRESH_TOKEN



    print(
        "REFRESH CHECK:",
        force,
        ACCESS_TOKEN is not None
    )



    if (

        not force

        and ACCESS_TOKEN

        and time.time()
        <
        ACCESS_TOKEN_EXPIRE - 300

    ):

        return ACCESS_TOKEN




    with TOKEN_LOCK:



        # =====================
        # Token来源
        #
        # 1. PostgreSQL 最新token
        # 2. Environment备用
        #
        # =====================


        refresh_token = ""

        db_token = None



        try:

            db_token = load_refresh_token()

        except Exception as e:

            print(
                "LOAD TOKEN ERROR:",
                e
            )



        if db_token:


            refresh_token = (
                db_token.strip()
            )


            source = "DATABASE"



        else:


            refresh_token = (
                WHOOP_REFRESH_TOKEN.strip()
            )


            source = "ENVIRONMENT"





        if not refresh_token:

            raise Exception(
                "Missing WHOOP refresh token"
            )




        print(
            "TOKEN SOURCE:",
            source
        )


        print(
            "REFRESH TOKEN LENGTH:",
            len(refresh_token)
        )



        print(
            "START WHOOP REFRESH"
        )





        r = requests.post(


            WHOOP_TOKEN_URL,


            data={


                "grant_type":
                "refresh_token",


                "refresh_token":
                refresh_token,


                "client_id":
                WHOOP_CLIENT_ID,


                "client_secret":
                WHOOP_CLIENT_SECRET


            },


            headers={


                "Content-Type":
                "application/x-www-form-urlencoded",


                "Accept":
                "application/json"

            },


            timeout=30

        )




        print(
            "REFRESH STATUS:",
            r.status_code
        )


        print(
            "REFRESH RESPONSE:",
            r.text[:500]
        )



        r.raise_for_status()




        result = r.json()




        ACCESS_TOKEN = result["access_token"]



        ACCESS_TOKEN_EXPIRE = (

            time.time()

            +

            int(
                result.get(
                    "expires_in",
                    3600
                )
            )

        )




        # WHOOP refresh token rotation

        new_refresh_token = result.get(
            "refresh_token"
        )



        if new_refresh_token:


            WHOOP_REFRESH_TOKEN = (
                new_refresh_token
            )


            save_refresh_token(
                new_refresh_token
            )


            print(
                "NEW REFRESH TOKEN SAVED"
            )



        print(
            "WHOOP TOKEN REFRESH SUCCESS"
        )



        return ACCESS_TOKEN







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


# =========================
# TODAY REPORT
# =========================

@app.route("/whoop/today")
def today():


    # =====================
    # 获取 WHOOP 数据
    # =====================


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



    # =====================
    # 保存每日数据
    # =====================


    try:


        metrics = extract_daily_metrics(
            data
        )


        save_daily_data(
            metrics
        )


        print(
            "DAILY DATA SAVED"
        )


    except Exception as e:


        print(
            "SAVE DAILY DATA ERROR:",
            e
        )







    # =====================
    # AI 健康报告
    # =====================


    report = generate_health_report(

        data

    )






    return jsonify(


        {


            "whoop_data":

            data,



            "coach_report":

            report


        }

    )







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
