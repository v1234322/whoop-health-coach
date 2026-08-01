import os
from openai import OpenAI


client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)


def generate_report(whoop_data):

    prompt = f"""
你是一名专业 WHOOP 健康教练。

请根据以下 WHOOP 数据生成中文健康报告：

{whoop_data}

报告要求：

1. 今日恢复状态分析
2. 睡眠质量分析
3. 训练负荷分析
4. 今日运动建议
5. 饮食和生活建议

格式：

🧠 今日健康教练报告

恢复：
...

睡眠：
...

训练：
...

今日建议：
...

"""

    response = client.chat.completions.create(

        model="gpt-5-mini",

        messages=[

            {
                "role": "system",
                "content": "你是一名专业健康教练"
            },

            {
                "role": "user",
                "content": prompt
            }

        ]

    )


    return response.choices[0].message.content
