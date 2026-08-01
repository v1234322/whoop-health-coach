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

请根据 WHOOP 数据生成中文健康日报。

分析：

1. Recovery 恢复状态
2. HRV变化
3. 静息心率
4. 睡眠质量
5. Strain训练压力
6. 今日训练建议
7. 恢复建议


WHOOP 数据：

{json.dumps(
    whoop_data,
    ensure_ascii=False,
    indent=2
)}


输出格式：

🧠 WHOOP 健康教练日报


【今日恢复】

【睡眠分析】

【训练状态】

【今日建议】

【恢复建议】

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

        temperature=0.4

    )


    return (
        response
        .choices[0]
        .message
        .content
    )
