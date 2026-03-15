# 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

import os
import requests

openAPI_KEY = "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"

print("💬 ChatGPT 터미널 챗앱 💬")

while True:
    question = input("\n👤 ")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {openAPI_KEY}"},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": question}],
        },
    )

    answer = response.json()["choices"][0]["message"]["content"]

    print("🤖", answer)