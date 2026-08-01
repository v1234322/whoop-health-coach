import os
import time
import threading
import requests

from flask import Flask, request, jsonify

from database import (
    init_db,
    save_refresh_token,
    load_refresh_token
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


# 这里只作为第一次初始化使用
# 后续使用 PostgreSQL 最新token

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
# CODE EXCHANGE TOKEN
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

import os
import time
import threading
import requests

from flask import Flask, request, jsonify

from database import (
    init_db,
    save_refresh_token,
    load_refresh_token
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


# 这里只作为第一次初始化使用
# 后续使用 PostgreSQL 最新token

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
# CODE EXCHANGE TOKEN
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
# 防止 refresh_token 失效
# 数据库优先
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



    # 使用缓存中的 access token

    if (

        not force

        and ACCESS_TOKEN

        and time.time()
        <
        ACCESS_TOKEN_EXPIRE - 300

    ):

        return ACCESS_TOKEN



    with TOKEN_LOCK:



        # =================================
        # Refresh Token 获取优先级
        #
        # 1. PostgreSQL 最新token
        # 2. Render Environment初始token
        #
        # =================================


        refresh_token = ""

        db_token = None



        # 先读取数据库

        try:

            db_token = load_refresh_token()

        except Exception as e:

            print(
                "DATABASE TOKEN READ ERROR:",
                e
            )



        if db_token:


            refresh_token = (
                db_token.strip()
            )


            token_source = "DATABASE"



        else:


            refresh_token = (
                WHOOP_REFRESH_TOKEN.strip()
            )


            token_source = "ENVIRONMENT"



        if not refresh_token:

            raise Exception(
                "Missing WHOOP refresh token"
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



        # 保存 access token

        ACCESS_TOKEN = (
            data["access_token"]
        )



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



        # =================================
        # WHOOP Token Rotation
        # 保存最新refresh_token
        # =================================


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
                "NEW TOKEN LENGTH:",
                len(new_refresh_token)
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

        WHOOP_API_BASE
        +
        endpoint,


        headers={

            "Authorization":
            f"Bearer {token}",


            "Accept":
            "application/json"

        },


        timeout=30

    )



    # Access Token 失效，强制刷新

    if r.status_code == 401:


        print(
            "ACCESS TOKEN EXPIRED"
        )


        token = refresh_access_token(
            True
        )


        r = requests.get(

            WHOOP_API_BASE
            +
            endpoint,


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



    print(
        "WHOOP RESPONSE:"
    )


    print(
        r.text[:500]
    )



    r.raise_for_status()



    return r.json()





# =========================
# TODAY HEALTH REPORT
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



    # 获取 WHOOP 数据


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



    # DeepSeek 健康分析

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
