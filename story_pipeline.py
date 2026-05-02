import os
import traceback
import urllib.parse
import anthropic
import requests

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


def generate_prompt_with_claude():
    """Генерация промта для рассказа через Claude"""
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": PROMPT_PARAMS}]
    )
    return message.content[0].text.strip()


def shorten_prompt_for_image(story_prompt):
    """Сжимаем длинный промт в короткое описание для обложки через Claude"""
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": f"""На основе этого описания рассказа сформулируй краткий промт (не более 40 английских слов) для генерации обложки книги. 
Опиши только визуальную сцену: персонажей, обстановку, настроение. Без текста на изображении. 
Верни ТОЛЬКО английский промт, без вступлений.

Описание рассказа:
{story_prompt}"""}]
    )
    return message.content[0].text.strip()


def generate_cover_with_pollinations(story_prompt):
    """Генерация обложки через Pollinations.ai, возвращает (bytes, url)"""
    print("Сжимаю промт для обложки...")
    short_prompt = shorten_prompt_for_image(story_prompt)
    print(f"Промт обложки: {short_prompt[:120]}...")

    full_prompt = (
        f"Professional book cover illustration, cinematic lighting, "
        f"warm cozy atmosphere, high detail, no text, no letters: {short_prompt}"
    )

    encoded_prompt = urllib.parse.quote(full_prompt)
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width=1024&height=768&nologo=true&enhance=true&model=flux"
    )

    print("Рисую обложку через Pollinations.ai...")
    response = requests.get(image_url, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Pollinations вернул ошибку {response.status_code}")

    if not response.content or len(response.content) < 1000:
        raise RuntimeError("Pollinations вернул пустое изображение")

    print(f"Обложка получена ({len(response.content) // 1024} KB)")
    # Возвращаем и байты (для Telegram), и URL (для Telegraph)
    return response.content, image_url


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


def publish_to_telegraph(title, story, image_url):
    """Публикуем статью на Telegraph, картинку вставляем по прямому URL Pollinations"""

    paragraphs = [p.strip() for p in story.split("\n") if p.strip()]

    content = [{"tag": "img", "attrs": {"src": image_url}}]
    for para in paragraphs:
        content.append({"tag": "p", "children": [para]})

    print("Публикую на Telegraph...")
    page_resp = requests.post(
        "https://api.telegra.ph/createPage",
        json={
            "access_token": "b968da509bb76866c35425099bc0989a5ec3b32997d55286c657e6a1e3b",
            "title": title,
            "author_name": "Инь и Янь",
            "content": content,
            "return_content": False
        },
        timeout=60
    )

    page_data = page_resp.json()
    if not page_data.get("ok"):
        raise RuntimeError(f"Ошибка создания страницы Telegraph: {page_data}")

    page_url = page_data["result"]["url"]
    print(f"Telegraph статья: {page_url}")
    return page_url


def send_to_telegram(title, image_bytes, telegraph_url):
    """Отправляем одно сообщение: фото + ссылка на Telegraph"""

    caption = (
        f"📖 *{title}*\n\n"
        f"Читать полностью 👇\n"
        f"{telegraph_url}"
    )

    photo_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    files = {"photo": ("cover.jpg", image_bytes, "image/jpeg")}
    data = {
        "chat_id": TG_CHAT_ID,
        "caption": caption,
        "parse_mode": "Markdown"
    }

    resp = requests.post(photo_url, data=data, files=files, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Ошибка отправки в Telegram: {resp.text[:200]}")

    print("✅ Пост отправлен в Telegram-канал.")


if __name__ == "__main__":
    try:
        print("1. Генерирую промт через Claude...")
        story_prompt = generate_prompt_with_claude()

        print("2. Рисую обложку...")
        cover_image, cover_url = generate_cover_with_pollinations(story_prompt)

        print("3. Пишу рассказ через Claude...")
        story_title, story = generate_story_with_claude(story_prompt)

        print("4. Публикую на Telegraph...")
        telegraph_url = publish_to_telegraph(story_title, story, cover_url)

        print("5. Отправляю в Telegram-канал...")
        send_to_telegram(story_title, cover_image, telegraph_url)

        print("✅ Готово!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
