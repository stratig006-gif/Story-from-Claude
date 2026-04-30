import os
import time
import anthropic
import requests

CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def call_claude_with_retry(client, max_tokens, messages, retries=3, delay=10):
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=max_tokens,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            print(f"Попытка {attempt + 1} не удалась: {e}")
            if attempt < retries - 1:
                print(f"Жду {delay} секунд перед повтором...")
                time.sleep(delay)
            else:
                raise

def generate_prompt_and_story():
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)

    print("Генерирую промт...")
    story_prompt = call_claude_with_retry(
        client,
        max_tokens=300,
        messages=[{"role": "user", "content": """
Сгенерируй творческий промт для короткого рассказа (500-800 слов).
Параметры:
- Жанр: фантастика, мистика или приключения (выбери случайно)
- Обязательный элемент: неожиданная концовка
- Главный герой: обычный человек в необычных обстоятельствах
- Язык рассказа: русский
Верни ТОЛЬКО сам промт, без пояснений.
        """}]
    )

    print("Пауза перед следующим запросом...")
    time.sleep(5)  # пауза 5 секунд между запросами

    print("Пишу рассказ...")
    story = call_claude_with_retry(
        client,
        max_tokens=2000,
        messages=[{"role": "user", "content": story_prompt}]
    )

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
        time.sleep(1)  # пауза между частями если рассказ длинный

if __name__ == "__main__":
    print("Запускаю конвейер...")
    story_prompt, story = generate_prompt_and_story()
    print(f"Промт: {story_prompt}\n")
    print("Отправляю в Telegram...")
    send_to_telegram(f"📖 *Новый рассказ*\n\n*Промт:* _{story_prompt}_\n\n---\n\n{story}")
    print("Готово!")
