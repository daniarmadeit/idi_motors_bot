"""
RunPod Serverless Worker - только обработка фото
Принимает список base64 фото → очищает через IOPaint → возвращает ZIP
"""
import asyncio
import base64
import glob
import io
import logging
import os
import subprocess
import tempfile
import time
import zipfile

import requests
import runpod
from PIL import Image, ImageDraw

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы (из config.py)
IOPAINT_URL = "http://127.0.0.1:8080"
IOPAINT_INPAINT_ENDPOINT = "/api/v1/inpaint"
IOPAINT_UPSCALE_ENDPOINT = "/api/v1/run_plugin_gen_image"
WATERMARK_WIDTH = 300
WATERMARK_HEIGHT = 30
INPAINT_TIMEOUT = 120
UPSCALE_TIMEOUT = 180
UPSCALE_FACTOR = 2
MIN_RESOLUTION_WIDTH = 1920
MIN_RESOLUTION_HEIGHT = 1080

iopaint_process = None


def create_watermark_mask(img_width: int, img_height: int) -> Image.Image:
    """Создает маску для удаления водяного знака BeForward (внизу по центру)"""
    mask = Image.new('L', (img_width, img_height), 0)
    draw = ImageDraw.Draw(mask)

    x1 = (img_width - WATERMARK_WIDTH) // 2
    y1 = img_height - WATERMARK_HEIGHT
    x2 = x1 + WATERMARK_WIDTH
    y2 = img_height

    draw.rectangle([x1, y1, x2, y2], fill=255)
    return mask


def image_to_base64(img: Image.Image) -> str:
    """Конвертирует изображение в base64"""
    buffer = io.BytesIO()
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def remove_watermark(img: Image.Image) -> Image.Image:
    """Удаляет водяной знак с изображения через IOPaint"""
    try:
        img_width, img_height = img.size

        # Конвертируем изображение и маску в base64
        img_base64 = image_to_base64(img)
        mask = create_watermark_mask(img_width, img_height)
        mask_base64 = image_to_base64(mask)

        # Отправляем в IOPaint
        payload = {
            'image': img_base64,
            'mask': mask_base64,
            'ldmSampler': 'plms',
            'hdStrategy': 'Original',
        }

        response = requests.post(
            f"{IOPAINT_URL}{IOPAINT_INPAINT_ENDPOINT}",
            json=payload,
            timeout=INPAINT_TIMEOUT
        )

        if response.status_code != 200:
            logger.error(f"❌ Ошибка IOPaint: HTTP {response.status_code}")
            logger.error(f"Response body: {response.text}")
            logger.error(f"Request payload keys: image_len={len(img_base64)}, mask_len={len(mask_base64)}")
            return img  # Возвращаем оригинал при ошибке

        # IOPaint API возвращает изображение напрямую в виде байтов
        result_bytes = response.content
        logger.info(f"✅ Получено {len(result_bytes)} байт от IOPaint")

        return Image.open(io.BytesIO(result_bytes))

    except Exception as e:
        logger.error(f"❌ Ошибка удаления watermark: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return img  # Возвращаем оригинал при ошибке


def upscale_image(img: Image.Image) -> Image.Image:
    """Увеличивает разрешение изображения через RealESRGAN"""
    try:
        img_base64 = image_to_base64(img)

        payload = {
            'image': img_base64,
            'name': 'RealESRGAN',
            'upscale': UPSCALE_FACTOR
        }

        response = requests.post(
            f"{IOPAINT_URL}{IOPAINT_UPSCALE_ENDPOINT}",
            json=payload,
            timeout=UPSCALE_TIMEOUT
        )

        if response.status_code != 200:
            logger.warning(f"⚠️ Upscaling не удался (HTTP {response.status_code})")
            logger.warning(f"Response body: {response.text}")
            logger.warning(f"Request: {IOPAINT_URL}{IOPAINT_UPSCALE_ENDPOINT}")
            logger.warning(f"Payload: name=RealESRGAN, upscale={UPSCALE_FACTOR}")
            return img  # Возвращаем оригинал при ошибке

        # IOPaint API возвращает изображение напрямую в виде байтов
        result_bytes = response.content
        logger.info(f"✅ Upscale: получено {len(result_bytes)} байт")

        return Image.open(io.BytesIO(result_bytes))

    except Exception as e:
        logger.warning(f"⚠️ Ошибка upscaling: {e}")
        import traceback
        logger.warning(traceback.format_exc())
        return img  # Возвращаем оригинал при ошибке


def start_iopaint():
    """Запускает IOPaint сервер с GPU поддержкой"""
    global iopaint_process

    try:
        logger.info("🎨 Запуск IOPaint сервера...")

        device = "cuda" if os.path.exists("/usr/local/cuda") else "cpu"
        logger.info(f"🖥️ Используется device: {device}")

        iopaint_process = subprocess.Popen([
            "iopaint", "start",
            "--model=lama",
            f"--device={device}",
            "--port=8080",
            "--host=0.0.0.0",
            "--enable-realesrgan",
            "--realesrgan-model=realesr-general-x4v3"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Ждем запуска
        logger.info("⏳ Ожидание запуска IOPaint (10 сек)...")
        time.sleep(10)

        # Проверяем что сервер запустился
        try:
            test_response = requests.get(f"{IOPAINT_URL}/api/v1/server-config", timeout=5)
            if test_response.status_code == 200:
                logger.info("✅ IOPaint сервер запущен и отвечает")
                logger.info(f"📋 Конфиг: {test_response.text[:200]}")
            else:
                logger.warning(f"⚠️ IOPaint запущен, но вернул статус {test_response.status_code}")
        except Exception as e:
            logger.error(f"❌ IOPaint не отвечает на запросы: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска IOPaint: {e}")
        raise


def process_photos(photo_data_list: list) -> bytes:
    """
    Обрабатывает список фото через IOPaint

    Args:
        photo_data_list: Список base64-encoded фото

    Returns:
        bytes: ZIP архив с очищенными фото
    """
    logger.info(f"🎨 Обработка {len(photo_data_list)} фото...")

    temp_dir = tempfile.mkdtemp()
    cleaned_photos = []

    try:
        for idx, photo_base64 in enumerate(photo_data_list):
            try:
                logger.info(f"📥 Обработка фото {idx + 1}/{len(photo_data_list)}")

                # Декодируем base64 в изображение
                photo_bytes = base64.b64decode(photo_base64)
                img = Image.open(io.BytesIO(photo_bytes))
                img_width, img_height = img.size
                logger.info(f"📊 Размер изображения: {img.size}")

                # Удаляем водяной знак через IOPaint
                logger.info(f"🧹 Удаление watermark...")
                cleaned_img = remove_watermark(img)

                # Upscale если разрешение меньше Full HD
                if img_width * img_height < MIN_RESOLUTION_WIDTH * MIN_RESOLUTION_HEIGHT:
                    logger.info(f"📈 Upscaling {img_width}x{img_height} → {img_width*UPSCALE_FACTOR}x{img_height*UPSCALE_FACTOR}...")
                    cleaned_img = upscale_image(cleaned_img)
                else:
                    logger.info(f"✓ Upscale не требуется (разрешение {img_width}x{img_height})")

                # Сохраняем очищенное фото
                cleaned_path = os.path.join(temp_dir, f"cleaned_{idx:03d}.jpg")
                cleaned_img.save(cleaned_path, 'JPEG', quality=95)
                cleaned_photos.append(cleaned_path)

                logger.info(f"✅ Фото {idx + 1} обработано")

            except Exception as e:
                logger.error(f"❌ Ошибка обработки фото {idx + 1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue

        # Создаем ZIP архив
        logger.info(f"📦 Создание ZIP архива из {len(cleaned_photos)} фото...")

        if not cleaned_photos:
            logger.warning(f"⚠️ Нет очищенных фото для архивации! Обработано 0 из {len(photo_data_list)}")

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for photo_path in cleaned_photos:
                logger.info(f"📦 Добавление в архив: {photo_path}")
                zip_file.write(photo_path, os.path.basename(photo_path))

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()

        logger.info(f"✅ ZIP архив создан ({len(zip_bytes)} байт), файлов в архиве: {len(cleaned_photos)}")
        return zip_bytes

    finally:
        # Очистка временных файлов
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def handler(event):
    """
    RunPod handler - обработка фото

    Input:
        {
            "photo_urls": ["base64_1", "base64_2", ...]
        }

    Output:
        {
            "status": "success",
            "zip_base64": "..."  # ZIP архив в base64
        }
    """
    global iopaint_process

    # Запускаем IOPaint при первом запуске
    if iopaint_process is None:
        start_iopaint()

    input_data = event.get("input", {})
    photo_data = input_data.get("photo_urls", [])

    if not photo_data:
        return {"error": "No photo_urls provided"}

    try:
        # Обрабатываем фото
        zip_bytes = process_photos(photo_data)

        # Конвертируем в base64 для передачи
        zip_base64 = base64.b64encode(zip_bytes).decode('utf-8')

        return {
            "status": "success",
            "photo_count": len(photo_data),
            "zip_base64": zip_base64,
            "zip_size": len(zip_bytes)
        }

    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        import traceback
        logger.error(traceback.format_exc())

        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    logger.info("🚀 Запуск RunPod Photo Processing Worker")
    runpod.serverless.start({"handler": handler})
