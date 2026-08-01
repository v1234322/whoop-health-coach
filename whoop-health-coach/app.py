import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)


# =====================
# Environment Variables
# =====================

WHOOP_CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET")

WHOOP_REFRESH_TOKEN = os.environ.get("WHOOP_REFRESH_TOKEN")

API_SECRET = os.environ.get("API_SECRET")

REDIRECT_URI = "https://whoop-health-coach.onrender.com/callback"


# =====================
# Health Check
# =====================

@app.route("/")
def home():
    return {
        "status": "ok",
        "service": "WHOOP Health Coach"
    }


# =====================
# API Key Check
# =====================

def check_api_key():

    key = request.headers.get("X-API-Key")

    if key != API_SECRET:
        return False

    return True



# =====================
# OAuth Callback
# =====================

@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return jsonify({
            "error": "missing code"
        }), 400


    return jsonify({
        "message": "WHOOP authorization success",
        "code": code
    })



# =====================
# Exchange Code Token
# =====================

@app.route("/whoop/token")
def exchange_token():

    code = request.args.get("code")

    if not code:
        return jsonify({
            "error":"missing code"
        }),400


    r = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        data={
            "grant_type":"authorization_code",
            "code":code,
            "client_id":WHOOP_CLIENT_ID,
            "client_secret":WHOOP_CLIENT_SECRET,
            "redirect_uri":REDIRECT_URI
        },
        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        }
    )


    return jsonify(r.json())



# =====================
# Refresh Token
# =====================

WHOOP_ACCESS_TOKEN = None


def refresh_token():

    global WHOOP_ACCESS_TOKEN

    if WHOOP_ACCESS_TOKEN:
        return WHOOP_ACCESS_TOKEN


    r = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": WHOOP_REFRESH_TOKEN,
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )


    print("WHOOP TOKEN RESPONSE:")
    print(r.text)


    r.raise_for_status()


    WHOOP_ACCESS_TOKEN = r.json()["access_token"]

    return WHOOP_ACCESS_TOKEN

# =====================
# WHOOP API
# =====================

def whoop_get(endpoint):

    token = os.environ.get("WHOOP_ACCESS_TOKEN")

    print("TOKEN CHECK:")
    print(token[:20] if token else "NO TOKEN")


    if not token:
        return {
            "error": "missing WHOOP_ACCESS_TOKEN"
        }


    r = requests.get(
        "https://api.prod.whoop.com/developer/v2" + endpoint,
        headers={
            "Authorization": "Bearer " + token
        }
    )


    print("WHOOP STATUS:")
    print(r.status_code)

    print("WHOOP RESPONSE:")
    print(r.text)


    r.raise_for_status()

    return r.json()



# =====================
# Today Data
# =====================

@app.route("/whoop/today")
def today():

    if not check_api_key():

        return jsonify({
            "error": "unauthorized"
        }),401


    data = {

        "recovery":
        whoop_get("/recovery"),


        "cycle":
        whoop_get("/cycle"),


        "sleep":
        whoop_get("/sleep"),


        "workout":
        whoop_get("/workout")

    }


    return jsonify(data)



if __name__=="__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )
    )
