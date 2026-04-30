import os
from google import genai
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

PROMPT_PARAMS = """
Сгенерируй творческий промт для написания короткого рассказа (500-800 слов).
Параметры:
- Жанр: фантастика, мистика или приключения (выбери случайно)
- Обязательный элемент: неожиданная концовка
- Главный герой: обычный человек в необычных обстоятельствах
- Язык рассказа: русский
Верни ТОЛЬКО сам промт, без пояснений.
"""

def generate_prompt_with_gemini():
    client = genai.Client(api_key=GEMINI_KEY)
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=PROMPT_PARAMS
    )
    return response.text.strip()

def generate_story_with_claude(story_prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": story_prompt}]
    )
    return message.content[0].text

def send_to_telegram(text):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    for chunk in chunks:
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        })

if __name__ == "__main__":
    print("Генерирую промт через Gemini...")
    story_prompt = generate_prompt_with_gemini()
    print(f"Промт: {story_prompt}\n")

    print("Пишу рассказ через Claude...")
    story = generate_story_with_claude(story_prompt)

    print("Отправляю в Telegram...")
    send_to_telegram(f"📖 *Новый рассказ*\n\n*Промт:* _{story_prompt}_\n\n---\n\n{story}")
    print("Готово!")
