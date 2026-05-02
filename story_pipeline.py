import os
import io
import json
import traceback
import html
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from google import genai
from google.genai import types
from PIL import Image
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Базовый URL сайта на GitHub Pages
SITE_URL = "https://stratig006-gif.github.io/Story-from-Claude"
SITE_TITLE = "Инь и Янь. Психология отношений"
SITE_DESCRIPTION = "Юмористические рассказы о счастливых семьях"
SITE_AUTHOR = "Инь и Янь"

DOCS_DIR = Path("docs")
POSTS_DIR = DOCS_DIR / "posts"
POSTS_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_PARAMS = """
Сгенерируй детальный промт для написания юмористического рассказа о счастливой семье (1800 - 2200 слов).
Обязательные параметры для промта:
СЕМЬЯ:
- Муж: [профессия, характер]
- Жена: [профессия, характер]
- Дети (если есть): [возраст, яркая черта характера]
Фамилии у семьи необычные. Животные если есть, то экзотические.
Профессии у семьи контрастные, чтобы было интересно. Профессии подбираем самые разнообразные, но всегда контраст профессий должен быть заметен.
Случайно выбери следующие параметры для каждого запуска:
1. Социальный статус: (среднестатистическая семья ИЛИ состоятельная семья ИЛИ бедная семья).
2. Состав семьи: (молодая пара без детей ИЛИ родители с 1-3 детьми ИЛИ семья с домашним питомцем ИЛИ один из супругов очень рассеянный ИЛИ у супругов совсем разные профессии).
3. Локация/Сюжет: (необычный день ИЛИ приключение в путешествии ИЛИ день когда все идет наперекосяк ИЛИ неожиданный приезд родственников).
4. Для каждой истории есть внешний катализатор. Всегда есть триггер событий: приезд свекрови ИЛИ поездка на море ИЛИ дочь-подросток ИЛИ сын-хулиган ИЛИ бабушка в деревне. Семья сама по себе стабильна — её "раскачивают" обстоятельства.
Требования к рассказу, который должен получиться:
- Тон: добрый юмор, жизнеутверждающая атмосфера, семейное тепло.
- Стиль повествования: затягивающий, не скучный, имеющий интригу
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
        config=types.GenerateContentConfig(response_modalities=["IMAGE"])
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            print(f"Обложка получена ({len(part.inline_data.data) // 1024} KB)")
            return part.inline_data.data
    raise RuntimeError("Gemini не вернул изображение")


def compress_image(image_bytes, max_kb=800, max_dimension=1200, min_width=700):
    """Сжимаем картинку. Дзен требует ширину минимум 700px."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Ресайзим только если больше max_dimension, но не меньше min_width
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    if img.width < min_width:
        ratio = min_width / img.width
        new_size = (min_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    quality = 92
    while quality >= 60:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        size_kb = len(buffer.getvalue()) // 1024
        if size_kb <= max_kb:
            print(f"Сжато: {img.width}x{img.height}, {size_kb} KB (q={quality})")
            return buffer.getvalue()
        quality -= 8

    print(f"Финальный размер: {size_kb} KB")
    return buffer.getvalue()


def generate_story_with_claude(story_prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        system="Ты — мастер семейной комедии и душевных историй. Пиши в стиле современной юмористической прозы.",
        messages=[{"role": "user", "content": f"""Напиши рассказ по этому промту: {story_prompt}

Формат ответа:
ЗАГОЛОВОК: [придумай красивый вовлекающий заголовок рассказа]
ОПИСАНИЕ: [краткое описание рассказа в 1-2 предложениях для анонса]
РАССКАЗ:
[текст рассказа]"""}]
    )
    raw = message.content[0].text

    title = "Новый рассказ"
    description = ""
    story = raw

    if "ЗАГОЛОВОК:" in raw:
        try:
            after_title = raw.split("ЗАГОЛОВОК:")[1]
            if "ОПИСАНИЕ:" in after_title:
                title = after_title.split("ОПИСАНИЕ:")[0].strip()
                after_desc = after_title.split("ОПИСАНИЕ:")[1]
                if "РАССКАЗ:" in after_desc:
                    description = after_desc.split("РАССКАЗ:")[0].strip()
                    story = after_desc.split("РАССКАЗ:")[1].strip()
            elif "РАССКАЗ:" in after_title:
                title = after_title.split("РАССКАЗ:")[0].strip()
                story = after_title.split("РАССКАЗ:")[1].strip()
        except Exception:
            pass

    if not description:
        description = story[:200].replace("\n", " ").strip() + "..."

    return title, description, story


def make_slug(timestamp):
    """Уникальный идентификатор поста по времени"""
    return f"post-{timestamp.strftime('%Y-%m-%d-%H%M%S')}"


def save_post_html(slug, title, description, story, image_filename, timestamp):
    """Создаём HTML-страницу рассказа"""
    paragraphs = [p.strip() for p in story.split("\n") if p.strip()]
    body_html = "\n".join(f"  <p>{html.escape(p)}</p>" for p in paragraphs)

    date_str = timestamp.strftime("%d.%m.%Y")

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:image" content="{SITE_URL}/posts/{image_filename}">
<meta property="og:type" content="article">
<style>
body {{ font-family: Georgia, serif; max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.7; color: #222; }}
h1 {{ font-size: 2em; margin-bottom: 8px; }}
.date {{ color: #888; font-size: 0.9em; margin-bottom: 24px; }}
img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 20px 0; }}
p {{ margin: 16px 0; text-align: justify; }}
.back {{ display: inline-block; margin-top: 30px; color: #666; text-decoration: none; }}
.back:hover {{ color: #000; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="date">{date_str}</div>
<img src="{image_filename}" alt="{html.escape(title)}">
{body_html}
<a class="back" href="../index.html">← Все рассказы</a>
</body>
</html>
"""
    post_path = POSTS_DIR / f"{slug}.html"
    post_path.write_text(html_content, encoding="utf-8")
    print(f"HTML сохранён: {post_path}")


def update_index_and_feed(new_post_meta):
    """Обновляем index.html и feed.xml. new_post_meta = dict с инфо о новом посте."""

    # Загружаем существующий список постов
    meta_path = DOCS_DIR / "posts.json"
    if meta_path.exists():
        posts = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        posts = []

    posts.insert(0, new_post_meta)  # новый пост в начало
    meta_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    # Обновляем index.html
    cards_html = ""
    for p in posts:
        cards_html += f"""
  <article class="card">
    <a href="posts/{p['slug']}.html">
      <img src="posts/{p['image']}" alt="{html.escape(p['title'])}">
      <h2>{html.escape(p['title'])}</h2>
    </a>
    <div class="date">{p['date_display']}</div>
    <p>{html.escape(p['description'])}</p>
  </article>"""

    index_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{html.escape(SITE_TITLE)}</title>
<meta name="description" content="{html.escape(SITE_DESCRIPTION)}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_TITLE)}" href="feed.xml">
<style>
body {{ font-family: Georgia, serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; background: #fafafa; }}
h1.site-title {{ text-align: center; font-size: 2.2em; margin-bottom: 8px; }}
.tagline {{ text-align: center; color: #666; margin-bottom: 40px; }}
.card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; overflow: hidden; }}
.card a {{ text-decoration: none; color: inherit; }}
.card img {{ width: 100%; height: auto; display: block; }}
.card h2 {{ padding: 16px 20px 8px; margin: 0; font-size: 1.4em; }}
.card .date {{ color: #999; font-size: 0.9em; padding: 0 20px; }}
.card p {{ padding: 8px 20px 20px; color: #444; }}
.card a:hover h2 {{ color: #c2410c; }}
</style>
</head>
<body>
<h1 class="site-title">{html.escape(SITE_TITLE)}</h1>
<div class="tagline">{html.escape(SITE_DESCRIPTION)}</div>
{cards_html}
</body>
</html>
"""
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("index.html обновлён")

    # Генерируем feed.xml в формате Дзена
    items_xml = ""
    for p in posts[:50]:  # последние 50 постов
        post_url = f"{SITE_URL}/posts/{p['slug']}.html"
        image_url = f"{SITE_URL}/posts/{p['image']}"

        # Полный HTML контента для Дзена
        paragraphs = [pp.strip() for pp in p['story'].split("\n") if pp.strip()]
        content_html = f'<img src="{image_url}" alt="{xml_escape(p["title"])}"/>'
        for para in paragraphs:
            content_html += f"<p>{xml_escape(para)}</p>"

        items_xml += f"""
    <item>
      <title>{xml_escape(p['title'])}</title>
      <link>{post_url}</link>
      <guid isPermaLink="true">{post_url}</guid>
      <pubDate>{p['pub_date']}</pubDate>
      <description>{xml_escape(p['description'])}</description>
      <author>noreply@example.com ({xml_escape(SITE_AUTHOR)})</author>
      <enclosure url="{image_url}" type="image/jpeg"/>
      <content:encoded><![CDATA[{content_html}]]></content:encoded>
    </item>"""

    feed_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:atom="http://www.w3.org/2005/Atom"
     version="2.0">
  <channel>
    <title>{xml_escape(SITE_TITLE)}</title>
    <link>{SITE_URL}/</link>
    <description>{xml_escape(SITE_DESCRIPTION)}</description>
    <language>ru</language>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
{items_xml}
  </channel>
</rss>
"""
    (DOCS_DIR / "feed.xml").write_text(feed_xml, encoding="utf-8")
    print("feed.xml обновлён")


def send_to_telegram(title, image_bytes, post_url):
    """Отправляем фото с заголовком и ссылкой на статью"""
    compressed = compress_image(image_bytes, max_kb=900)

    caption = (
        f"📖 *{html.escape(title)}*\n\n"
        f"Читать рассказ полностью 👇\n"
        f"{post_url}"
    )

    photo_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    files = {"photo": ("cover.jpg", compressed, "image/jpeg")}
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
        timestamp = datetime.now(timezone.utc)
        slug = make_slug(timestamp)

        print("1. Генерирую промт через Gemini...")
        story_prompt = generate_prompt_with_gemini()

        print("2. Рисую обложку через Gemini...")
        cover_image = generate_cover_with_gemini(story_prompt)

        print("3. Пишу рассказ через Claude...")
        title, description, story = generate_story_with_claude(story_prompt)
        print(f"Заголовок: {title}")

        print("4. Сохраняю обложку (минимум 700px шириной)...")
        cover_compressed = compress_image(cover_image, max_kb=800, min_width=900)
        image_filename = f"{slug}.jpg"
        (POSTS_DIR / image_filename).write_bytes(cover_compressed)

        print("5. Создаю HTML-страницу рассказа...")
        save_post_html(slug, title, description, story, image_filename, timestamp)

        print("6. Обновляю index.html и feed.xml...")
        post_meta = {
            "slug": slug,
            "title": title,
            "description": description,
            "story": story,
            "image": image_filename,
            "date_display": timestamp.strftime("%d.%m.%Y"),
            "pub_date": timestamp.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        }
        update_index_and_feed(post_meta)

        post_url = f"{SITE_URL}/posts/{slug}.html"

        print("7. Отправляю в Telegram-канал...")
        send_to_telegram(title, cover_image, post_url)

        print(f"✅ Готово! Статья: {post_url}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        exit(1)
    
