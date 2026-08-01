import os
import requests

from flask import Flask, request, jsonify


app = Flask(__name__)


# =========================
# Environment
# =========================

WHOOP_CLIENT_ID = os.environ.get(
    "WHOOP_CLIENT_ID"
)

WHOOP_CLIENT_SECRET = os.environ.get(
    "WHOOP_CLIENT_SECRET"
)

WHOOP_REFRESH_TOKEN = os.environ.get(
    "WHOOP_REFRESH_TOKEN"
)

API_SECRET = os.environ.get(
    "API_SECRET"
)


print("DEBUG CLIENT ID:", WHOOP_CLIENT_ID)

print(
    "DEBUG SECRET LENGTH:",
    len(WHOOP_CLIENT_SECRET)
    if WHOOP_CLIENT_SECRET else 0
)
WHOOP_API = (
    "https://api.prod.whoop.com/developer/v2"
)


CALLBACK_URL = (
    "https://whoop-health-coach.onrender.com/callback"
)


# 缓存 access token
ACCESS_TOKEN_CACHE = None



# =========================
# Home
# =========================

@app.route("/")
def home():

    return jsonify({

        "status": "ok",

        "service": "WHOOP Health Coach"

    })



# =========================
# API Key Check
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

        return jsonify({

            "error":
            "missing code"

        }),400



    return jsonify({

        "message":
        "WHOOP authorization success",

        "code":
        code

    })



# =========================
# Exchange Code Token
# =========================

@app.route("/whoop/token")
def whoop_token():

    code = request.args.get(
        "code"
    )


    if not code:

        return jsonify({

            "error":
            "missing code"

        }),400



    if not WHOOP_CLIENT_ID or not WHOOP_CLIENT_SECRET:

        return jsonify({

            "error":
            "missing WHOOP client credentials"

        }),500



    r = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",

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
            CALLBACK_URL

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
# Refresh Access Token
# =========================

def get_access_token():

    global ACCESS_TOKEN_CACHE



    if ACCESS_TOKEN_CACHE:

        return ACCESS_TOKEN_CACHE



    if not WHOOP_REFRESH_TOKEN:

        raise Exception(
            "Missing WHOOP_REFRESH_TOKEN"
        )



    r = requests.post(

        "https://api.prod.whoop.com/oauth/oauth2/token",


        data={


            "grant_type":
            "refresh_token",


            "refresh_token":
            WHOOP_REFRESH_TOKEN,


            "client_id":
            WHOOP_CLIENT_ID,


            "client_secret":
            WHOOP_CLIENT_SECRET

        },


        headers={

            "Content-Type":
            "application/x-www-form-urlencoded"

        }

    )



    print(
        "REFRESH RESPONSE:"
    )

    print(
        r.text
    )



    r.raise_for_status()



    data = r.json()



    ACCESS_TOKEN_CACHE = (
        data["access_token"]
    )



    return ACCESS_TOKEN_CACHE




# =========================
# WHOOP API
# =========================

def whoop_get(endpoint):


    token = get_access_token()



    r = requests.get(

        WHOOP_API + endpoint,


        headers={

            "Authorization":
            f"Bearer {token}"

        }

    )



    print(
        "WHOOP RESPONSE:"
    )

    print(
        r.text
    )



    r.raise_for_status()



    return r.json()




# =========================
# Today Data
# =========================

@app.route("/whoop/today")
def today():


    if not check_api_key():

        return jsonify({

            "error":
            "unauthorized"

        }),401



    result = {


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
            "/sleep"
        ),



        "workout":

        whoop_get(
            "/workout"
        )


    }



    return jsonify(
        result
    )




# =========================
# Run
# =========================

if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=int(

            os.environ.get(
                "PORT",
                10000
            )

        )

    )
