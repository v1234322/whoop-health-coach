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
# INIT DATABASE
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



# 第一次初始化使用
# 后续使用数据库最新token

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
# GET TOKEN BY CODE
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



        refresh_token = ""


        db_token = None




        try:

            db_token = load_refresh_token()


        except Exception as e:

            print(
                "DB TOKEN ERROR:",
                e
            )





        if db_token:


            refresh_token = db_token.strip()

            token_source = "DATABASE"



        else:


            refresh_token = (
                WHOOP_REFRESH_TOKEN.strip()
            )

            token_source = "ENVIRONMENT"





        if not refresh_token:


            raise Exception(
                "Missing refresh token"
            )





        print(
            "TOKEN SOURCE:",
            token_source
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




        data = r.json()




        ACCESS_TOKEN = data["access_token"]




        ACCESS_TOKEN_EXPIRE = (

            time.time()

            +

            int(
                data.get(
                    "expires_in",
                    3600
                )
            )

        )





        new_refresh_token = data.get(
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
# WHOOP API
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


            }


        )





    print(
        "WHOOP STATUS:",
        r.status_code
    )



    r.raise_for_status()



    return r.json()







# =========================
# EXTRACT DAILY DATA
# =========================


def extract_daily_metrics(data):



    recovery_record = (

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



    score = recovery_record.get(
        "score",
        {}
    )



    return {


        "recovery_score":

        score.get(
            "recovery_score"
        ),



        "hrv":

        score.get(
            "hrv_rmssd_milli"
        ),



        "resting_heart_rate":

        score.get(
            "resting_heart_rate"
        ),



        "sleep_score":

        None,



        "sleep_duration":

        None,



        "cycle_strain":

        None,



        "workout_data":

        data.get(
            "workout",
            {}
        )

    }







# =========================
# TODAY REPORT
# =========================


@app.route("/whoop/today")
def today():



    if not check_api_key():


        return jsonify(

            {
                "error":
                "unauthorized"
            }

        ),401





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






    # 保存每日数据

    metrics = extract_daily_metrics(
        data
    )


    save_daily_data(
        metrics
    )






    # AI分析

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
# HOME
# =========================


@app.route("/")
def home():

    return "WHOOP Health Coach Running"







if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=10000

    )
