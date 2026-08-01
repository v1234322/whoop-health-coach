import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
WHOOP_REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")
API_SECRET = os.getenv("API_SECRET")

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
BASE_URL = "https://api.prod.whoop.com/developer/v2"

def refresh_token():
    r = requests.post(
        "https://api.prod.whoop.com/oauth/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": WHOOP_REFRESH_TOKEN,
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET,
            "redirect_uri": "https://oauth.pstmn.io/v1/callback"
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    print("WHOOP TOKEN RESPONSE:", r.text)

    r.raise_for_status()

    return r.json()["access_token"]
    
def whoop_get(endpoint, params=None):
    token = refresh_token()
    r = requests.get(
        BASE_URL + endpoint,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30
    )
    r.raise_for_status()
    return r.json()

def auth():
    if request.headers.get("X-API-Key") != API_SECRET:
        return False
    return True

@app.get("/health")
def health():
    return jsonify({"status":"ok"})

@app.get("/whoop/today")
def today():
    if not auth():
        return jsonify({"error":"unauthorized"}),401
    return jsonify({
        "cycles": whoop_get("/cycle"),
        "sleep": whoop_get("/activity/sleep"),
        "workouts": whoop_get("/activity/workout")
    })

@app.get("/whoop/trends")
def trends():
    if not auth():
        return jsonify({"error":"unauthorized"}),401
    return jsonify({
        "days": request.args.get("days",7),
        "cycles": whoop_get("/cycle"),
        "sleep": whoop_get("/activity/sleep"),
        "workouts": whoop_get("/activity/workout")
    })
