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


app = Flask(__name__)


# =========================
# Init Database
# =========================

init_db()



# =========================
# Environment
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
# Token Cache
# =========================

ACCESS_TOKEN = None

ACCESS_TOKEN_EXPIRE = 0

TOKEN_LOCK = threading.Lock()



# =========================
# API Key
# =========================

def check_api_key():

    key = request.headers.get(
        "X-API-Key"
    )

    return key == API_SECRET



# =========================
# OAuth Callback
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
# Exchange Code
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
# Refresh Access Token
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



        # =========================
        # Token Priority
        #
        # 1. Render Environment
        # 2. PostgreSQL backup
        # =========================


        refresh_token = (
            WHOOP_REFRESH_TOKEN.strip()
        )



        if not refresh_token:


            db_token = load_refresh_token()


            if db_token:

                refresh_token = (
                    db_token.strip()
                )



        if not refresh_token:

            raise Exception(
                "Missing WHOOP refresh token"
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



        # =========================
        # Save rotated refresh token
        # =========================

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
                "REFRESH TOKEN SAVED TO DATABASE"
            )



        print(
            "TOKEN REFRESH SUCCESS"
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



    if r.status_code == 401:


        print(
            "TOKEN EXPIRED"
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
# Today Data
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



    return jsonify(
        data
    )



# =========================
# Health Check
# =========================

@app.route("/")
def home():

    return (
        "WHOOP Health Coach Running"
    )



# =========================
# Run
# =========================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=10000

    )
