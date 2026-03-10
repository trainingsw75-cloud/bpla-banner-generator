import base64
import json
import os
import io
import hashlib
import time
import boto3
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
from datetime import datetime
# Добавь этот импорт в начало файла, если его ещё нет
import urllib.parse
import urllib.request
import json

def shorten_url(long_url):
    """Сокращает длинный URL через сервис clck.ru."""
    try:
        # Кодируем URL для безопасной передачи в GET-запросе
        encoded_url = urllib.parse.quote(long_url, safe='')
        api_url = f"https://clck.ru/--?url={encoded_url}"

        # Отправляем GET-запрос к API clck.ru
        with urllib.request.urlopen(api_url) as response:
            if response.status == 200:
                short_url = response.read().decode('utf-8').strip()
                # API возвращает просто строку с короткой ссылкой
                return short_url
            else:
                print(f"Error from clck.ru: {response.status}")
                return long_url # В случае ошибки возвращаем оригинальную ссылку
    except Exception as e:
        print(f"Exception during URL shortening: {e}")
        return long_url # В случае исключения возвращаем оригинальную ссылку

# В функции handler, перед созданием QR-кода, добавь эти строки:
def handler(event, context):
    # ... (весь твой предыдущий код до этого места)
    
    # Получаем целевой URL из параметров
    target_url = params.get('url', 'https://оператор-бпла.рф')

    # --- НОВЫЙ БЛОК: СОКРАЩЕНИЕ ССЫЛКИ ---
    # Сокращаем ссылку (если это не ссылка на clck.ru, чтобы не сокращать уже сокращённое)
    if not target_url.startswith('https://clck.ru/'):
        short_target_url = shorten_url(target_url)
    else:
        short_target_url = target_url
    # --------------------------------------

    # Дальше в коде, при создании QR-кода, используй переменную short_target_url
    final_image = add_text_and_qr(image_data, title, author, short_target_url)

    # ... (остальной код, включая формирование ответа)
    # В ответе API можно вернуть обе ссылки:
    return {
        'statusCode': 200,
        'headers': { ... },
        'body': json.dumps({
            'image_url': image_url,
            'qr_url': short_target_url,  # <- короткая ссылка в QR
            'original_url': target_url,   # <- оригинальная ссылка (для информации)
            'filename': filename
        })
    }
def handler(event, context):
    ACCESS_KEY = os.environ.get('STORAGE_ACCESS_KEY')
    SECRET_KEY = os.environ.get('STORAGE_SECRET_KEY')
    BUCKET_NAME = os.environ.get('BUCKET_NAME')
    API_KEY = os.environ.get('API_KEY')
    FOLDER_ID = os.environ.get('FOLDER_ID')

    missing = []
    if not ACCESS_KEY: missing.append('STORAGE_ACCESS_KEY')
    if not SECRET_KEY: missing.append('STORAGE_SECRET_KEY')
    if not BUCKET_NAME: missing.append('BUCKET_NAME')
    if not API_KEY: missing.append('API_KEY')
    if not FOLDER_ID: missing.append('FOLDER_ID')
    if missing:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Missing environment variables: {", ".join(missing)}'})
        }

    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='ru-central1'
    )

    if 'body' in event and event['body']:
        try:
            body = json.loads(event['body'])
            params = body.get('queryStringParameters', {})
        except:
            params = event.get('queryStringParameters', {})
    else:
        params = event.get('queryStringParameters', {})

    title = params.get('title', 'Обучение операторов БПЛА')
    author = params.get('author', 'Минобороны РФ')
    target_url = params.get('url', 'https://оператор-бпла.рф')
    city = params.get('city', 'Москва')

    prompt = generate_prompt(title, city, API_KEY, FOLDER_ID)
    image_data = generate_image(prompt, API_KEY, FOLDER_ID)
    final_image = add_text_and_qr(image_data, title, author, target_url)

    filename = generate_filename(title)
    image_url = upload_to_storage(s3, BUCKET_NAME, final_image, filename)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'image_url': image_url,
            'qr_url': target_url,
            'filename': filename
        })
    }

def generate_prompt(title, city, api_key, folder_id):
    prompt_text = f"Создай промпт для генерации реалистичного изображения на тему: '{title}'. Город: {city}. Стиль: патриотичный, фотореализм, четкие линии."
    headers = {
        'Authorization': f'Api-Key {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        'modelUri': f'gpt://{folder_id}/yandexgpt-lite',
        'completionOptions': {
            'stream': False,
            'temperature': 0.3,
            'maxTokens': 100
        },
        'messages': [
            {
                'role': 'system',
                'text': 'Ты генератор промптов для нейросети. Создавай короткие, но детальные промпты на русском языке.'
            },
            {
                'role': 'user',
                'text': prompt_text
            }
        ]
    }
    try:
        response = requests.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            return result['result']['alternatives'][0]['message']['text']
        else:
            return f"Реалистичное фото FPV дрона в небе над городом {city}, патриотичный стиль, развевающийся флаг РФ на заднем плане, высокое качество"
    except:
        return f"Реалистичное фото FPV дрона в небе над городом {city}, патриотичный стиль, высокое качество"

def generate_image(prompt, api_key, folder_id):
    headers = {
        'Authorization': f'Api-Key {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        'modelUri': f'art://{folder_id}/yandex-art/latest',
        'messages': [
            {
                'role': 'user',
                'text': prompt
            }
        ]
    }
    try:
        response = requests.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync',
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            operation_id = response.json()['id']
            for _ in range(30):
                time.sleep(2)
                status_response = requests.get(
                    f'https://llm.api.cloud.yandex.net/operations/{operation_id}',
                    headers=headers,
                    timeout=5
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('done'):
                        image_base64 = status_data['response']['image']
                        return base64.b64decode(image_base64)
            return create_fallback_image(prompt)
        else:
            return create_fallback_image(prompt)
    except:
        return create_fallback_image(prompt)

def create_fallback_image(prompt):
    img = Image.new('RGB', (1200, 630), color=(10, 50, 100))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
    draw.text((100, 250), "Операторы БПЛА", fill=(255,255,255), font=font)
    return img

def add_text_and_qr(image_data, title, author, target_url):
    if isinstance(image_data, bytes):
        image = Image.open(io.BytesIO(image_data))
    else:
        image = image_data

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(target_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").resize((150,150))
    image.paste(qr_img, (image.width - 170, image.height - 170))
    return image

def generate_filename(title):
    return f"banners/{hashlib.md5(f'{title}_{datetime.now()}'.encode()).hexdigest()[:16]}.png"

def upload_to_storage(s3_client, bucket_name, image, filename):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    s3_client.put_object(
        Bucket=bucket_name,
        Key=filename,
        Body=img_byte_arr,
        ContentType='image/png',
        CacheControl='public, max-age=3600'
    )
    return f"https://storage.yandexcloud.net/{bucket_name}/{filename}"
