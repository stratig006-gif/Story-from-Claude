import os
import io
from google import genai
from google.genai import types
import anthropic
import requests

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CLAUDE_KEY = os.environ["ANTHROPIC_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

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
    """Генерация обложки с помощью Nano Banana 2 (Gemini 3 Flash Image)"""
    client = genai.Client(api_key=GEMINI_KEY)
    
    # Формируем промт именно для картинки на основе сюжета
    image_prompt = f"Professional book cover illustration, cinematic lighting, high detail, no text: {story_prompt}"
    
    print("Рисую обложку (Nano Banana)...")
    response = client.models.generate_image(
        model="gemini-3-flash-image", # Это и есть Nano Banana 2
        prompt=image_prompt,
        config=types.GenerateImageConfig(
            number_of_images=1,
            output_mime_type="image/jpeg"
        )
    )
    # Возвращаем байты изображения
    return response.generated_images[0].image_bytes
    
def generate_story_with_claude(story_prompt):
    client = anthropic.Anthropic(api_key=CLAUDE_KEY)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2500,
        system="Ты — мастер семейной комедии и душевных историй. Пиши в стиле современной юмористической прозы.",
        messages=[{"role": "user", "content": f"""Напиши рассказ по этому промту: {story_prompt}

Формат ответа:
ЗАГОЛОВОК: [придумай красивый вовлекающий заголовок рассказа]
РАССКАЗ:
[текст рассказа]"""}]
    )
    raw = message.content[0].text
    # Разбираем заголовок и текст
    if "ЗАГОЛОВОК:" in raw and "РАССКАЗ:" in raw:
        title = raw.split("ЗАГОЛОВОК:")[1].split("РАССКАЗ:")[0].strip()
        story = raw.split("РАССКАЗ:")[1].strip()
    else:
        title = "Новый рассказ"
        story = raw
    return title, story

def send_to_telegram(text, image_bytes, title):
    """Отправка фото и текста раздельными сообщениями"""
    
    # 1. Отправляем только картинку
    photo_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    files = {'photo': ('cover.jpg', image_bytes, 'image/jpeg')}
    
    # Можно оставить пустую подпись или просто заголовок
    photo_data = {
        'chat_id': TG_CHAT_ID, 
        'caption': "🎨 *Обложка к новому рассказу*",
        'parse_mode': 'Markdown'
    }
    
    try:
        requests.post(photo_url, data=photo_data, files=files)
        print("Фото отправлено.")
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")

    # 2. Отправляем текст рассказа (с разбивкой на части, если он длинный)
    # Формируем текст сообщения
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

# В блоке if __name__ == "__main__": теперь вызываем так:
if __name__ == "__main__":
    try:
        print("1. Генерирую промт...")
        story_prompt = generate_prompt_with_gemini()

        print("2. Рисую обложку (Nano Banana)...")
        cover_image = generate_cover_with_gemini(story_prompt)

        print("3. Пишу рассказ через Claude...")
        story = generate_story_with_claude(story_prompt)

        print("4. Отправляю в Telegram...")
        # Передаем саму историю, байты картинки и промт отдельно
        send_to_telegram(story, cover_image, story_prompt)
        
        print("✅ Готово!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
