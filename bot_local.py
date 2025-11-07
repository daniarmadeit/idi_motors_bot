"""
Локальный Telegram бот - работает на ноутбуке
Обработку фото отправляет на RunPod Serverless
"""
import asyncio
import base64
import io
import logging
import os
import requests
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from rus_bot import BeForwardParser

# Загружаем локальную конфигурацию
load_dotenv('.env.local')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
RUNPOD_API_KEY = os.getenv('RUNPOD_API_KEY')
RUNPOD_ENDPOINT_ID = os.getenv('RUNPOD_ENDPOINT_ID')
RUNPOD_API_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
RUNPOD_STATUS_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status"


class LocalBot:
    """Локальный бот с вызовом RunPod для обработки фото"""

    def __init__(self, token: str):
        self.token = token
        self.parser = BeForwardParser()
        self.application = None
        self.url_queue = asyncio.Queue(maxsize=20)  # Очередь до 20 URL
        self.is_processing = False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = (
            "👋 Привет!\n\n"
            "Отправь ссылку на авто с BeForward.jp\n\n"
            "Ты получишь:\n"
            "✅ Полные данные автомобиля\n"
            "✅ Качественные фото без водяных знаков\n"
        )
        await update.message.reply_text(welcome_text)

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL - добавляет в очередь"""
        url = update.message.text.strip()

        if 'beforward.jp' not in url.lower():
            await update.message.reply_text(
                "❌ Пожалуйста, отправь ссылку на BeForward.jp"
            )
            return

        # Создаем статусное сообщение
        status_msg = await update.message.reply_text("⏳ В очереди...")

        # Добавляем в очередь
        await self.url_queue.put({
            'url': url,
            'update': update,
            'context': context,
            'status_msg': status_msg
        })

        # Запускаем обработчик очереди, если не запущен
        if not self.is_processing:
            asyncio.create_task(self.process_queue())

    async def process_queue(self):
        """Обработчик очереди URL"""
        if self.is_processing:
            return

        self.is_processing = True
        logger.info("🚀 Запущен обработчик очереди")

        while not self.url_queue.empty():
            try:
                # Получаем задачу из очереди
                task = await self.url_queue.get()
                url = task['url']
                update = task['update']
                context = task['context']
                status_msg = task['status_msg']

                logger.info(f"📋 Обрабатываю URL из очереди: {url}")

                # Обрабатываем
                await self._process_url(url, update, context, status_msg)

                # Помечаем как выполненную
                self.url_queue.task_done()

            except Exception as e:
                logger.error(f"❌ Ошибка в обработчике очереди: {e}")
                import traceback
                logger.error(traceback.format_exc())

        self.is_processing = False
        logger.info("✅ Обработчик очереди завершён")

    def _download_photos_sync(self, photo_download_url: str, referer_url: str):
        """Синхронное скачивание фото (для executor)"""
        import zipfile
        import tempfile

        temp_dir = tempfile.mkdtemp()
        photo_paths = []

        # Используем метод парсера для скачивания
        response = self.parser.session.get(
            photo_download_url,
            timeout=120,
            headers={'Referer': referer_url}
        )
        response.raise_for_status()

        zip_path = os.path.join(temp_dir, 'photos.zip')
        with open(zip_path, 'wb') as f:
            f.write(response.content)

        # Извлекаем фото
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Собираем пути к фото
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    photo_path = os.path.join(root, file)
                    photo_paths.append(photo_path)

        # Сортируем по имени файла, чтобы гарантировать порядок (001.jpg, 002.jpg, ...)
        photo_paths.sort()

        return photo_paths, temp_dir

    async def _process_url(self, url: str, update: Update, context: ContextTypes.DEFAULT_TYPE, status_msg):
        """Обработка одного URL"""
        await status_msg.edit_text("⏳ Получаю данные автомобиля...")

        temp_dir = None  # Для cleanup в finally
        try:
            # 1. Парсим данные машины (в отдельном потоке - не блокируем event loop)
            logger.info(f"📋 Парсинг: {url}")
            loop = asyncio.get_event_loop()

            # Запускаем парсинг в отдельном потоке чтобы не блокировать event loop
            # (Playwright внутри уже работает в потоке, но сам parse_car_data синхронный)
            car_data = await loop.run_in_executor(None, self.parser.parse_car_data, url)
            logger.info(f"✅ parse_car_data завершён")

            result_text = self.parser.format_car_data(car_data, url)
            logger.info(f"✅ format_car_data завершён")

            # 2. Получаем список фото
            photo_download_url = car_data.get('photo_download_url')
            logger.info(f"📸 Photo download URL: {photo_download_url}")

            if not photo_download_url or photo_download_url == "COLLECT_PHOTOS":
                # Нет фото - просто отправляем данные
                logger.info("⚠️ Нет фото, отправляю только данные")
                await status_msg.edit_text(result_text, disable_web_page_preview=True)
                return

            # 3. Скачиваем фото через парсер (в отдельном потоке)
            logger.info(f"📥 Начинаю скачивание фото...")
            try:
                photo_paths, temp_dir = await loop.run_in_executor(
                    None,
                    self._download_photos_sync,
                    photo_download_url,
                    url
                )
                logger.info(f"✅ Скачано {len(photo_paths)} фото")

            except Exception as e:
                logger.error(f"❌ Ошибка скачивания: {e}")
                await status_msg.edit_text(
                    result_text + f"\n\n❌ Не удалось скачать фото: {str(e)[:100]}",
                    disable_web_page_preview=True
                )
                return

            if not photo_paths:
                await status_msg.edit_text(
                    result_text + "\n\n⚠️ Фото не найдены",
                    disable_web_page_preview=True
                )
                return

            # 4. Отправляем фото на RunPod для обработки
            photo_count = min(len(photo_paths), 20)
            await status_msg.edit_text(f"🎨 Обработка {photo_count} фото...")

            # Конвертируем локальные файлы в base64 для отправки
            # Лимит: 20 фото
            MAX_PHOTOS = 20

            photo_data = []
            for photo_path in photo_paths[:MAX_PHOTOS]:
                with open(photo_path, 'rb') as f:
                    photo_base64 = base64.b64encode(f.read()).decode('utf-8')
                    photo_data.append(photo_base64)

            logger.info(f"🚀 Отправка {len(photo_data)} фото на RunPod...")

            # Освобождаем список путей (файлы будут удалены в finally)
            del photo_paths

            # 1. Запускаем async job
            run_response = requests.post(
                RUNPOD_API_URL,
                json={
                    "input": {
                        "photo_urls": photo_data
                    }
                },
                headers={
                    "Authorization": f"Bearer {RUNPOD_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if run_response.status_code != 200:
                logger.error(f"RunPod error: {run_response.text}")
                await status_msg.edit_text(
                    result_text + "\n\n❌ Ошибка запуска обработки",
                    disable_web_page_preview=True
                )
                return

            run_result = run_response.json()
            job_id = run_result.get("id")
            logger.info(f"✅ Job создан: {job_id}")

            # Освобождаем память от base64 данных
            del photo_data

            # 2. Polling результата
            max_wait = 300  # 5 минут
            poll_interval = 5  # Проверяем каждые 5 секунд
            waited = 0

            while waited < max_wait:
                await asyncio.sleep(poll_interval)
                waited += poll_interval

                # Обновляем статус для пользователя
                if waited % 15 == 0:  # Каждые 15 секунд
                    await status_msg.edit_text(f"🎨 Обработка фото... ({waited} сек)")

                # Проверяем статус
                status_response = requests.get(
                    f"{RUNPOD_STATUS_URL}/{job_id}",
                    headers={"Authorization": f"Bearer {RUNPOD_API_KEY}"},
                    timeout=10
                )

                if status_response.status_code != 200:
                    continue

                status_result = status_response.json()
                job_status = status_result.get("status")

                logger.info(f"📊 Job status: {job_status}")

                if job_status == "COMPLETED":
                    result = status_result
                    break
                elif job_status == "FAILED":
                    error = status_result.get("error", "Unknown error")
                    await status_msg.edit_text(
                        result_text + f"\n\n❌ Ошибка обработки: {error}",
                        disable_web_page_preview=True
                    )
                    return

            else:
                # Timeout
                await status_msg.edit_text(
                    result_text + "\n\n⏱️ Обработка заняла слишком много времени. Попробуй позже.",
                    disable_web_page_preview=True
                )
                return

            # RunPod возвращает {"status": "COMPLETED", "output": {...}}
            output = result.get("output", {})

            if output.get("status") == "success":
                # Получаем ZIP с очищенными фото
                zip_base64 = output.get("zip_base64")
                zip_bytes = base64.b64decode(zip_base64)

                logger.info(f"✅ Получен ZIP ({len(zip_bytes)} байт)")

                # Удаляем статусное сообщение
                await status_msg.delete()

                # Отправляем ZIP
                car_name = car_data.get('car_name', 'cleaned_photos').replace('/', '_')
                await update.message.reply_document(
                    document=io.BytesIO(zip_bytes),
                    filename=f"{car_name}.zip",
                    caption=result_text
                )

                logger.info("✅ Обработка завершена")

            else:
                error = output.get("error", result.get("error", "Unknown error"))
                logger.error(f"RunPod error: {error}")
                await status_msg.edit_text(
                    result_text + f"\n\n❌ Ошибка: {error}",
                    disable_web_page_preview=True
                )

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())

            try:
                await status_msg.delete()
            except:
                pass

            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

        finally:
            # Всегда очищаем временные файлы
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"🗑️ Очищена временная директория: {temp_dir}")

    def run(self):
        """Запуск бота"""
        self.application = Application.builder().token(self.token).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url))

        logger.info("🚀 Запуск локального бота (polling режим)...")
        logger.info(f"📡 RunPod endpoint: {RUNPOD_ENDPOINT_ID}")

        self.application.run_polling(drop_pending_updates=True)


def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в .env.local")
        return

    if not RUNPOD_API_KEY:
        logger.error("❌ RUNPOD_API_KEY не найден в .env.local")
        return

    bot = LocalBot(BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()
