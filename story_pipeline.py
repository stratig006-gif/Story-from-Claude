import os
from google import genai
from google.genai import types
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # например @yin_yan_psychology

PROMPT_PARAMS = """
Сгенерируй детальный промт для написания юмористического рассказа о счастливой семье (20000 - 23000 символов).
Случайно выбери следующие параметры для каждого запуска:

1. Социальный статус: (среднестатистическая семья ИЛИ состоятельная семья).
2. Состав семьи: (молодая пара без детей ИЛИ родители с 1-3 детьми ИЛИ семья с домашним питомцем).
3. Локация/Сюжет: (необычное происшествие дома ИЛИ приключение в путешествии ИЛИ странный праздник).

Требования к рассказу, который должен получиться:
- Тон: добрый юмор, жизнеутверждающая атмосфера, семейное тепло.
- Конфликт: бытовой или приключенческий, но без негатива. Семья всегда действует как команда.
- Финал: счастливое завершение или забавный семейный вывод.

Верни ТОЛЬКО инструкцию для написания самого рассказа на русском языке, без лишних вступлений.
"""


def generate_prompt_with_gemini():
    client = genai.Client(api_key=GEMINI_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=PROMPT_PARAMS
    )
    return response.text.strip()


def generate_cover_with_gemini(story_prompt):
    """Генерация обложки через generate_content с модальностью Image"""
    client = genai.Client(api_key=GEMINI_KEY)

    image_prompt = f"Professional book cover illustration, cinematic lighting, high detail, no text: {story_prompt}"

    print("Рисую обложку...")
    response = client.models.generate_content(
        model="gemini-3-flash-image",
        contents=image_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"]
        )
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise RuntimeError("Gemini не вернул изображение")


def generate_story_with_claude(story_prompt):
    """Генерация рассказа с отдельным заголовком"""
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        system="Ты — мастер семейной комедии и душевных историй. Пиши в стиле современной юмористической прозы.",
        messages=[{"role": "user", "content": f"""Напиши рассказ по этому промту: {story_prompt}

Формат ответа:
ЗАГОЛОВОК: [придумай красивый заголовок рассказа]
РАССКАЗ:
[текст рассказа]"""}]
    )
    raw = message.content[0].text

    if "ЗАГОЛОВОК:" in raw and "РАССКАЗ:" in raw:
        title = raw.split("ЗАГОЛОВОК:")[1].split("РАССКАЗ:")[0].strip()
        story = raw.split("РАССКАЗ:")[1].strip()
    else:
        title = "Новый рассказ"
        story = raw

    return title, story


def send_to_telegram(text, image_bytes, title):
    """Отправка обложки и текста в Telegram-канал"""

    # 1. Отправляем обложку
    photo_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    files = {'photo': ('cover.jpg', image_bytes, 'image/jpeg')}
    photo_data = {
        'chat_id': TG_CHAT_ID,
        'caption': f"🎨 *{title}*",
        'parse_mode': 'Markdown'
    }

    try:
        requests.post(photo_url, data=photo_data, files=files)
        print("Фото отправлено.")
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")

    # 2. Отправляем текст рассказа (с разбивкой, если длинный)
    full_message = f"📖 *{title}*\n\n{text}"
    chunks = [full_message[i:i+4000] for i in range(0, len(full_message), 4000)]
    msg_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    for chunk in chunks:
        requests.post(msg_url, json={
            "chat_id": TG_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        })
    print("Текст отправлен.")


if __name__ == "__main__":
    try:
        print("1. Генерирую промт...")
        story_prompt = generate_prompt_with_gemini()

        print("2. Рисую обложку...")
        cover_image = generate_cover_with_gemini(story_prompt)

        print("3. Пишу рассказ через Claude...")
        story_title, story = generate_story_with_claude(story_prompt)

        print("4. Отправляю в Telegram-канал...")
        send_to_telegram(story, cover_image, story_title)

        print("✅ Готово!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
