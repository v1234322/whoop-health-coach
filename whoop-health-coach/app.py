import os
import requests
from flask import Flask, request, jsonify


app = Flask(__name__)


# =========================
# Environment Variables
# =========================

WHOOP_ACCESS_TOKEN = os.environ.get(
    "WHOOP_ACCESS_TOKEN"
)

API_SECRET = os.environ.get(
    "API_SECRET"
)


WHOOP_API_BASE = (
    "https://api.prod.whoop.com/developer/v2"
)



# =========================
# 首页检测
# =========================

@app.route("/")
def home():

    return jsonify({

        "status": "ok",

        "service": "WHOOP Health Coach"

    })



# =========================
# API Key 验证
# =========================

def check_api_key():

    key = request.headers.get(
        "X-API-Key"
    )

    return key == API_SECRET



# =========================
# 获取 WHOOP 数据
# =========================

def whoop_get(endpoint):


    token = WHOOP_ACCESS_TOKEN


    if not token:

        return {

            "error":
            "WHOOP_ACCESS_TOKEN missing"

        }



    r = requests.get(

        WHOOP_API_BASE + endpoint,

        headers={

            "Authorization":
            f"Bearer {token}"

        }

    )


    print("WHOOP STATUS:")
    print(r.status_code)


    print("WHOOP RESPONSE:")
    print(r.text)



    r.raise_for_status()


    return r.json()



# =========================
# WHOOP 今日数据
# =========================

@app.route("/whoop/today")
def today():


    if not check_api_key():

        return jsonify({

            "error":
            "unauthorized"

        }),401



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
            "/sleep"
        ),



        "workout":

        whoop_get(
            "/workout"
        )


    }


    return jsonify(data)




# =========================
# 启动
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
