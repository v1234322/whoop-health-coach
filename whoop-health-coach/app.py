import os
import time
import threading
import requests

from flask import Flask, request, jsonify


app = Flask(__name__)


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
# Token cache
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
# OAuth callback
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
# First token exchange
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

        }

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
# Refresh access token
# =========================

def refresh_access_token(force=False):

    global ACCESS_TOKEN
    global ACCESS_TOKEN_EXPIRE
    global WHOOP_REFRESH_TOKEN


    print(
        "REFRESH CHECK:",
        "force=",
        force,
        "cached=",
        ACCESS_TOKEN is not None
    )


    # token 未过期，直接使用
    if (
        not force
        and ACCESS_TOKEN
        and time.time() < ACCESS_TOKEN_EXPIRE - 300
    ):

        print(
            "USING CACHED ACCESS TOKEN"
        )

        return ACCESS_TOKEN



    with TOKEN_LOCK:


        if (
            not force
            and ACCESS_TOKEN
            and time.time() < ACCESS_TOKEN_EXPIRE - 300
        ):

            return ACCESS_TOKEN



        print(
            "CLIENT ID:",
            WHOOP_CLIENT_ID[:8]
        )

        print(
            "SECRET LENGTH:",
            len(WHOOP_CLIENT_SECRET)
        )

        print(
            "REFRESH TOKEN LENGTH:",
            len(WHOOP_REFRESH_TOKEN.strip())
        )


       if not WHOOP_REFRESH_TOKEN:
           raise RuntimeError(
               "Missing WHOOP_REFRESH_TOKEN"
           )


       refresh_token = WHOOP_REFRESH_TOKEN.strip()


        print(
            "REFRESH TOKEN LENGTH:",
            len(refresh_token)
        )


        payload = {

            "grant_type": "refresh_token",

            "refresh_token": refresh_token,

            "client_id": WHOOP_CLIENT_ID,
     
            "client_secret": WHOOP_CLIENT_SECRET
        }



        print(
            "START WHOOP REFRESH"
        )


        r = requests.post(

            WHOOP_TOKEN_URL,


            data=payload,


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


        if r.status_code != 200:

            print(
                "REFRESH ERROR:",
                r.text
            )

            raise RuntimeError(
                "WHOOP refresh failed: "
                + r.text
            )



        data = r.json()



        ACCESS_TOKEN = (
            data["access_token"]
        )


        ACCESS_TOKEN_EXPIRE = 0



        # WHOOP 会返回新的 refresh_token
        if data.get(
            "refresh_token"
        ):


            WHOOP_REFRESH_TOKEN = (
                data["refresh_token"]
            )


            print(
                "REFRESH TOKEN ROTATED"
            )



        print(
            "WHOOP TOKEN REFRESH SUCCESS"
        )


        return ACCESS_TOKEN



# =========================
# WHOOP GET
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


        }


    )



    if r.status_code == 401:


        token = refresh_access_token(
            force=True
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


            }

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

@app.route("/")
def home():

    return "WHOOP Health Coach Running"



if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
    )
