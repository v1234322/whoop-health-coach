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

@app.route("/whoop/report")
def report():

    if not check_api_key():

        return jsonify({
            "error":"unauthorized"
        }),401


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


    from coach import generate_report


    report = generate_report(data)


    return jsonify({

        "report": report

    })



# =========================
# Refresh Access Token
# =========================

def get_access_token():

    global ACCESS_TOKEN_CACHE
    global WHOOP_REFRESH_TOKEN


    # 已经获取过，直接使用
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


    print("REFRESH RESPONSE:")
    print(r.text)



    r.raise_for_status()



    data = r.json()



    # 保存新的 access_token
    ACCESS_TOKEN_CACHE = data["access_token"]



    # WHOOP 会轮换 refresh_token
    if "refresh_token" in data:

        WHOOP_REFRESH_TOKEN = data["refresh_token"]


        print(
            "NEW REFRESH TOKEN RECEIVED"
        )



    return ACCESS_TOKEN_CACHE



# =========================
# WHOOP API
# =========================

def whoop_get(endpoint):

    token = os.environ.get(
        "WHOOP_ACCESS_TOKEN"
    )


    if not token:

        raise Exception(
            "Missing WHOOP_ACCESS_TOKEN"
        )


    print(
        "TOKEN CHECK:",
        token[:20]
    )


    r = requests.get(

        "https://api.prod.whoop.com/developer/v2"
        + endpoint,


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
           
            "/activity/sleep"
        ),



        "workout":

        whoop_get(
            "/activity/workout"
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
