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



# 初始化数据库

init_db()



# ======================
# ENV
# ======================


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



# ======================
# TOKEN CACHE
# ======================


ACCESS_TOKEN = None

ACCESS_TOKEN_EXPIRE = 0

TOKEN_LOCK = threading.Lock()



# ======================
# API KEY
# ======================


def check_api_key():

    key = request.headers.get(
        "X-API-Key"
    )

    return key == API_SECRET



# ======================
# REFRESH TOKEN
# ======================


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



        refresh_token = load_refresh_token()



        if not refresh_token:

            refresh_token = (
                WHOOP_REFRESH_TOKEN
            )



        if not refresh_token:

            raise Exception(
                "Missing refresh token"
            )



        print(
            "REFRESH TOKEN LENGTH:",
            len(refresh_token)
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
                "application/x-www-form-urlencoded"

            },

            timeout=30

        )



        print(
            "REFRESH STATUS:",
            r.status_code
        )


        print(
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



        if data.get(
            "refresh_token"
        ):


            WHOOP_REFRESH_TOKEN = (
                data["refresh_token"]
            )


            save_refresh_token(
                WHOOP_REFRESH_TOKEN
            )


            print(
                "REFRESH TOKEN SAVED"
            )



        print(
            "TOKEN REFRESH SUCCESS"
        )



        return ACCESS_TOKEN




# ======================
# WHOOP API
# ======================


def whoop_get(endpoint):


    token = refresh_access_token()



    r = requests.get(

        WHOOP_API_BASE
        +
        endpoint,

        headers={

            "Authorization":
            f"Bearer {token}"

        },

        timeout=30

    )



    if r.status_code == 401:


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



# ======================
# TODAY
# ======================


@app.route(
    "/whoop/today"
)

def today():



    if not check_api_key():

        return jsonify(
            {
                "error":
                "unauthorized"
            }
        ),401



    return jsonify(

        {

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

    )



# ======================
# HOME
# ======================


@app.route("/")

def home():

    return (
        "WHOOP Health Coach Running"
    )



if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=10000

    )
