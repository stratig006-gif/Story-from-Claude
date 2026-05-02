import os
import traceback
from google import genai
from google.genai import types
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # @yin_yan_psychology

PROMPT_PARAMS = """
Сгенерируй детальный промт для написания юмористического рассказа о счастливой семье (не более 2000 слов).
Обязательные параметры для промта:
СЕМЬЯ:
- Муж: [профессия, характер]
- Жена: [профессия, характер]
- Дети (если есть): [возраст, яркая черта характера]
Профессии у семьи контрастные, чтобы было интересно
Случайно выбери следующие параметры для каждого запуска:
1. Социальный статус: (среднестатистическая семья ИЛИ состоятельная семья ИЛИ бедная семья).
2. Состав семьи: (молодая пара без детей ИЛИ родители с 1-3 детьми ИЛИ семья с домашним питомцем ИЛИ один из супругов очень рассеянный ИЛИ у супругов совсем разные профессии).
3. Локация/Сюжет: (необычный день ИЛИ приключение в путешествии ИЛИ день когда все идет наперекосяк ИЛИ неожиданный приезд родственников).
4. Для каждой истории есть внешний катализатор. Всегда есть триггер событий: приезд свекрови, поездка на море, дочь-подросток, сын-хулиган, бабушка в деревне. Семья сама по себе стабильна — её "раскачивают" обстоятельства.
Требования к рассказу, который должен получиться:
- Тон: добрый юмор, жизнеутверждающая атмосфера, семейное тепло.
- Конфликт: бытовой или приключенческий, но без негатива. Семья всегда действует как команда.
- Финал: счастливое завершение или забавный семейный вывод.

Верни ТОЛЬКО инструкцию для написания самого рассказа на русском языке, без лишних вступлений.
"""


def generate_prompt_with_gemini():
    """Генерация промта для рассказа через Gemini"""
    client = genai.Client(api_key=GEMINI_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=PROMPT_PARAMS
    )
    return response.text.strip()


def generate_cover_with_gemini(story_prompt):
    """Генерация обложки через Gemini Image (gemini-2.5-flash-image)"""
    client = genai.Client(api_key=GEMINI_KEY)

    image_prompt = (
        f"Professional book cover illustration, cinematic lighting, "
        f"warm cozy atmosphere, high detail, no text, no letters. "
        f"Scene: {story_prompt}"
    )

    print("Рисую обложку через Gemini...")
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=image_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"]
        )
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            print(f"Обложка получена ({len(part.inline_data.data) // 1024} KB)")
            return part.inline_data.data

    raise RuntimeError("Gemini не вернул изображение")


def generate_story_with_claude(story_prompt):
    """Генерация рассказа с заголовком через Claude"""
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10000,
        system="Ты — мастер семейной комедии и душевных историй. Пиши в стиле современной юмористической прозы.",
        messages=[{"role": "user", "content": f"""Напиши рассказ по этому промту: {story_prompt}

Формат ответа:
ЗАГОЛОВОК: [придумай красивый вовлекающий заголовок рассказа]
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


def send_to_telegram(title, image_bytes, story):
    """Отправляем: фото с заголовком, затем текст рассказа"""
    base_url = f"https://api.telegram.org/bot{TG_TOKEN}"

    # 1. Фото с заголовком в подписи
    print("Отправляю фото...")
    photo_resp = requests.post(
        f"{base_url}/sendPhoto",
        data={
            "chat_id": TG_CHAT_ID,
            "caption": f"📖 *{title}*",
            "parse_mode": "Markdown"
        },
        files={"photo": ("cover.jpg", image_bytes, "image/jpeg")},
        timeout=60
    )
    if photo_resp.status_code != 200:
        print(f"Ошибка отправки фото: {photo_resp.text[:200]}")

    # 2. Текст рассказа — разбиваем на части по 4000 символов
    print("Отправляю текст рассказа...")
    chunks = [story[i:i+4000] for i in range(0, len(story), 4000)]
    for i, chunk in enumerate(chunks):
        resp = requests.post(
            f"{base_url}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown"
            },
            timeout=60
        )
        if resp.status_code != 200:
            print(f"Ошибка отправки части {i+1}: {resp.text[:200]}")

    print(f"✅ Отправлено {len(chunks)} часть(ей) текста.")


if __name__ == "__main__":
    try:
        print("1. Генерирую промт через Gemini...")
        story_prompt = generate_prompt_with_gemini()

        print("2. Рисую обложку через Gemini...")
        cover_image = generate_cover_with_gemini(story_prompt)

        print("3. Пишу рассказ через Claude...")
        story_title, story = generate_story_with_claude(story_prompt)

        print("4. Отправляю в Telegram-канал...")
        send_to_telegram(story_title, cover_image, story)

        print("✅ Готово!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
