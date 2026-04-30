import os
import time
import requests
from google import genai

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def call_gemini_with_retry(client, prompt, retries=3, delay=10):
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt < retries - 1:
                print(f"Жду {delay} секунд...")
                time.sleep(delay)
            else:
                raise

def generate_prompt_and_story():
    client = genai.Client(api_key=GEMINI_KEY)

    print("Генерирую промт...")
    story_prompt = call_gemini_with_retry(client, """
Сгенерируй творческий промт для короткого рассказа (500-800 слов).
Параметры:
- Жанр: фантастика, мистика или приключения (выбери случайно)
- Обязательный элемент: неожиданная концовка
- Главный герой: обычный человек в необычных обстоятельствах
- Язык рассказа: русский
Верни ТОЛЬКО сам промт, без пояснений.
    """)

    print(f"Промт готов: {story_prompt}\n")
    print("Пауза 5 секунд...")
    time.sleep(5)

    print("Пишу рассказ...")
    story = call_gemini_with_retry(client, story_prompt)

    return story_prompt, story

def send_to_telegram(text):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    for chunk in chunks:
        requests.post(url, json={
            "chat_id": TG_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        })
        time.sleep(1)

if __name__ == "__main__":
    print("Запускаю конвейер...")
    story_prompt, story = generate_prompt_and_story()
    print("Отправляю в Telegram...")
    send_to_telegram(f"📖 *Новый рассказ*\n\n*Промт:* _{story_prompt}_\n\n---\n\n{story}")
    print("Готово!")
