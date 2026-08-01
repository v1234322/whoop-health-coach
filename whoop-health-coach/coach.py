import os
import json
from openai import OpenAI


client = OpenAI(
    api_key=os.environ.get(
        "OPENAI_API_KEY"
    )
)


def generate_health_report(whoop_data):


    prompt = f"""
你是一名专业 WHOOP 健康教练。

请根据以下 WHOOP 数据生成中文健康报告。

要求：

1. 分析恢复状态
2. 分析睡眠质量
3. 分析训练负荷
4. 给出今天训练建议
5. 给出恢复建议

数据：

{json.dumps(
    whoop_data,
    ensure_ascii=False,
    indent=2
)}


输出格式：

🧠 WHOOP 健康教练日报

【恢复】

【睡眠】

【训练】

【今日建议】

【注意事项】

"""


    response = client.chat.completions.create(

        model="gpt-5-mini",

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
