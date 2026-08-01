import os
import json

from openai import OpenAI


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
# WHOOP Health Coach
# =========================

def generate_health_report(whoop_data):


    prompt = f"""

你是一名专业 WHOOP 健康教练。

你的任务：
根据 WHOOP 数据生成每日健康报告。



========================
数据规则（必须严格遵守）
========================


1.
只能使用 WHOOP JSON 中存在的数据。


2.
禁止创造任何数字。


3.
禁止编造：

- 昨日数据
- 7天平均
- 周趋势
- 月趋势
- 历史训练记录


4.
如果没有历史数据：

必须写：

"暂无历史数据，无法进行趋势分析。"



5.
所有指标必须来自 WHOOP：

包括：

- Recovery Score
- HRV
- Resting Heart Rate
- Sleep
- Workout
- Strain



6.
注意区分：

Workout Strain：

代表单次训练压力。


Cycle Strain：

代表全天累计压力。


两者不能混合。



========================
分析内容
========================


请输出：


🧠 WHOOP 健康教练日报



📅 日期：




【今日恢复】


Recovery Score：

HRV：

静息心率：


分析：




【睡眠分析】


睡眠时间：

睡眠效率：

睡眠结构：


分析：




【训练状态】


训练项目：

Workout Strain：

Cycle Strain：


分析：




【今日建议】


训练建议：


恢复建议：




【注意事项】


只根据 WHOOP 数据分析。

没有数据不要推测。



========================
WHOOP 数据
========================


{json.dumps(

    whoop_data,

    ensure_ascii=False,

    indent=2

)}



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
