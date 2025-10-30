"""
RunPod Serverless Worker - только обработка фото
Принимает список URL фото → очищает через IOPaint → возвращает ZIP
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
from PIL import Image

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

IOPAINT_URL = "http://127.0.0.1:8080"
iopaint_process = None


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
            "--host=0.0.0.0"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Ждем запуска
        time.sleep(10)
        logger.info("✅ IOPaint сервер запущен")

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
                logger.info(f"📥 Декодирую фото {idx + 1}/{len(photo_data_list)}")
                logger.info(f"📊 Размер base64 строки: {len(photo_base64)} символов")

                # Декодируем base64 в байты
                photo_bytes = base64.b64decode(photo_base64)
                logger.info(f"📊 Размер декодированного фото: {len(photo_bytes)} байт")

                # Сохраняем оригинал
                img = Image.open(io.BytesIO(photo_bytes))
                logger.info(f"📊 Размер изображения: {img.size}, формат: {img.format}")
                original_path = os.path.join(temp_dir, f"photo_{idx:03d}.jpg")
                img.save(original_path)
                logger.info(f"💾 Сохранено: {original_path}")

                # Очищаем через IOPaint
                logger.info(f"🧹 Очистка фото {idx + 1}...")

                with open(original_path, 'rb') as f:
                    files = {'image': f}
                    data = {'model': 'lama'}

                    logger.info(f"📡 Отправка запроса к IOPaint: {IOPAINT_URL}/api/v1/inpaint")
                    iopaint_response = requests.post(
                        f"{IOPAINT_URL}/api/v1/inpaint",
                        files=files,
                        data=data,
                        timeout=120
                    )

                    logger.info(f"📡 IOPaint ответ: статус {iopaint_response.status_code}, размер {len(iopaint_response.content)} байт")

                    if iopaint_response.status_code == 200:
                        cleaned_path = os.path.join(temp_dir, f"cleaned_{idx:03d}.jpg")
                        with open(cleaned_path, 'wb') as out:
                            out.write(iopaint_response.content)
                        cleaned_photos.append(cleaned_path)
                        logger.info(f"✅ Фото {idx + 1} очищено: {cleaned_path}")
                    else:
                        logger.error(f"❌ Ошибка IOPaint: {iopaint_response.status_code}, body: {iopaint_response.text[:200]}")

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
