import os
import json

from openai import OpenAI


client = OpenAI(

    api_key=os.environ.get(
        "DEEPSEEK_API_KEY"
    ),

    base_url=
    "https://api.deepseek.com"

)



def generate_health_report(whoop_data):


    prompt = f"""
你是一名专业 WHOOP 健康教练。

你的任务是根据 WHOOP 提供的数据生成健康日报。

重要规则：

1. 只能使用输入数据中存在的内容。
2. 禁止编造昨日数据。
3. 禁止编造7天平均数据。
4. 禁止虚构训练记录。
5. 如果没有历史数据，请明确写：
   "暂无历史数据，无法进行趋势比较。"

分析内容：

- Recovery 恢复状态
- HRV
- 静息心率
- 睡眠质量
- Workout训练情况
- 今日训练建议
- 恢复建议


WHOOP 当前数据：

{json.dumps(
    whoop_data,
    ensure_ascii=False,
    indent=2
)}


输出格式：

🧠 WHOOP 健康教练日报


📅 日期：




【今日恢复】

Recovery Score：

HRV：

静息心率：

分析：




【睡眠分析】

睡眠时间：

睡眠质量：

分析：




【训练状态】

今日训练：

Strain：

分析：




【今日建议】

训练建议：

恢复建议：




【注意事项】

只根据数据判断。
不要猜测。
"""



    response = client.chat.completions.create(

        model="deepseek-chat",

        messages=[

            {
                "role":
                "system",

                "content":
                "你是一名专业运动恢复教练。"
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
