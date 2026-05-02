import os
import traceback
import urllib.parse
from google import genai
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # например @yin_yan_psychology

PROMPT_PARAMS = """
Сгенерируй детальный промт для написания юмористического рассказа о счастливой семье (не более 1000 слов).
Случайно выбери следующие параметры для каждого запуска:

1. Социальный статус: (среднестатистическая семья ИЛИ состоятельная семья ИЛИ бедная семья).
2. Состав семьи: (молодая пара без детей ИЛИ родители с 1-3 детьми ИЛИ семья с домашним питомцем ИЛИ один из супругов очень рассеянный ИЛИ у супругов совсем разные профессии).
3. Локация/Сюжет: (необычный день ИЛИ приключение в путешествии ИЛИ день когда все идет наперекосяк ИЛИ неожиданный приезд родственников).

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


def shorten_prompt_for_image(story_prompt):
    """Сжимаем длинный промт рассказа в короткое описание для картинки через Gemini"""
    client = genai.Client(api_key=GEMINI_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"""На основе этого описания рассказа сформулируй краткий промт (не более 40 английских слов) для генерации обложки книги. 
Опиши только визуальную сцену: персонажей, обстановку, настроение. Без текста на изображении. 
Верни ТОЛЬКО английский промт, без вступлений.

Описание рассказа:
{story_prompt}"""
    )
    return response.text.strip()


def generate_cover_with_pollinations(story_prompt):
    """Генерация обложки через бесплатный Pollinations.ai (без API-ключа)"""
    print("Сжимаю промт для обложки...")
    short_prompt = shorten_prompt_for_image(story_prompt)
    print(f"Промт обложки: {short_prompt[:120]}...")

    # Добавляем стилевые модификаторы для качественной обложки
    full_prompt = (
        f"Professional book cover illustration, cinematic lighting, "
        f"warm cozy atmosphere, high detail, no text, no letters: {short_prompt}"
    )

    # Кодируем промт в URL
    encoded_prompt = urllib.parse.quote(full_prompt)

    # Pollinations.ai endpoint - параметры:
    # width/height - размеры (книжная обложка 768x1024)
    # nologo=true - убирает водяной знак
    # enhance=true - улучшает промт автоматически
    # model=flux - используем Flux (лучшее качество из бесплатных)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1024&height=768&nologo=true&enhance=true&model=flux"
    )

    print("Рисую обложку через Pollinations.ai...")
    response = requests.get(url, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(
            f"Pollinations вернул ошибку {response.status_code}: {response.text[:200]}"
        )

    if not response.content or len(response.content) < 1000:
        raise RuntimeError("Pollinations вернул пустое или некорректное изображение")

    print(f"Обложка получена ({len(response.content) // 1024} KB)")
    return response.content


def generate_story_with_claude(story_prompt):
    """Генерация рассказа с отдельным заголовком через Claude"""
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
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
        cover_image = generate_cover_with_pollinations(story_prompt)

        print("3. Пишу рассказ через Claude...")
        story_title, story = generate_story_with_claude(story_prompt)

        print("4. Отправляю в Telegram-канал...")
        send_to_telegram(story, cover_image, story_title)

        print("✅ Готово!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
