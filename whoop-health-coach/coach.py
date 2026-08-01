import os
import json

from openai import OpenAI

from database import load_last_7_days



# =========================
# DeepSeek Client
# =========================

client = OpenAI(

    api_key=os.environ.get(
        "DEEPSEEK_API_KEY"
    ),

    base_url="https://api.deepseek.com"

)



# =========================
# WHOOP HEALTH COACH
# =========================

def generate_health_report(whoop_data):


    # =====================
    # 获取真实7天数据
    # =====================

    history = load_last_7_days()



    history_data = []



    for row in history:

        history_data.append(

            {

                "date":
                str(row[0]),


                "recovery_score":
                row[1],


                "hrv":
                row[2],


                "resting_heart_rate":
                row[3],


                "sleep_score":
                row[4],


                "sleep_duration":
                row[5],


                "cycle_strain":
                row[6]

            }

        )




    prompt = f"""


你是一名专业 WHOOP 健康教练。


你的任务：

根据：

1. 今日 WHOOP 数据

2. 最近7天真实历史数据


生成健康日报。



========================

严格规则

========================


1.

所有数字必须来自输入数据。



2.

禁止创造：

- 昨日数据
- 7天平均
- 趋势变化

如果历史数据不足，必须说明：

"历史数据不足，无法判断趋势。"



3.

只能分析提供的数据。



4.

Workout Strain 与 Cycle Strain 必须区分。



Workout Strain:
单次训练压力。


Cycle Strain:
全天累计压力。



========================

今日 WHOOP 数据

========================


{json.dumps(

    whoop_data,

    ensure_ascii=False,

    indent=2

)}



========================

最近7天历史数据

========================


{json.dumps(

    history_data,

    ensure_ascii=False,

    indent=2

)}



========================

输出格式

========================



🧠 WHOOP 健康教练日报



📅 日期：



━━━━━━━━━━━━━━



【今日恢复】


Recovery Score:


HRV:


静息心率:


分析:




【7天恢复趋势】


Recovery趋势:


HRV趋势:


睡眠趋势:


训练负荷趋势:




【睡眠分析】


睡眠时间:


睡眠质量:


分析:




【训练状态】


训练情况:


Strain分析:




【今日建议】


训练建议:


恢复建议:




【注意事项】


只根据 WHOOP 数据分析。


"""


    response = client.chat.completions.create(


        model="deepseek-chat",


        messages=[


            {


                "role":
                "system",


                "content":

                "你是一名严格的数据驱动型WHOOP健康教练。"


            },


            {


                "role":

                "user",


                "content":

                prompt

            }


        ],


        temperature=0.2


    )



    return (

        response

        .choices[0]

        .message

        .content

    )
