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
RUNPOD_API_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/runsync"


class LocalBot:
    """Локальный бот с вызовом RunPod для обработки фото"""

    def __init__(self, token: str):
        self.token = token
        self.parser = BeForwardParser()
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = (
            "👋 Привет!\n\n"
            "Я бот для парсинга BeForward.jp\n\n"
            "Просто отправь мне ссылку на авто и получи:\n"
            "✅ Данные машины\n"
            "✅ Очищенные фото (без водяных знаков)\n\n"
            "Обработка фото на GPU в облаке! ⚡"
        )
        await update.message.reply_text(welcome_text)

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL BeForward"""
        url = update.message.text.strip()

        if 'beforward.jp' not in url.lower():
            await update.message.reply_text(
                "❌ Пожалуйста, отправь ссылку на BeForward.jp"
            )
            return

        status_msg = await update.message.reply_text("⏳ Парсинг данных...")

        try:
            # 1. Парсим данные машины
            logger.info(f"📋 Парсинг: {url}")
            car_data = self.parser.parse_car_data(url)
            result_text = self.parser.format_car_data(car_data)

            # 2. Получаем список фото
            photo_download_url = car_data.get('photo_download_url')

            if not photo_download_url or photo_download_url == "COLLECT_PHOTOS":
                # Нет фото - просто отправляем данные
                await status_msg.edit_text(result_text, disable_web_page_preview=True)
                return

            # 3. Скачиваем фото через парсер (он умеет обходить защиту BeForward)
            await status_msg.edit_text("📥 Скачивание фото...")
            logger.info(f"📥 Скачиваю фото через парсер")

            import zipfile
            import tempfile

            temp_dir = tempfile.mkdtemp()
            photo_paths = []

            try:
                # Используем метод парсера для скачивания
                response = self.parser.session.get(
                    photo_download_url,
                    timeout=120,
                    headers={'Referer': url}
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
            await status_msg.edit_text(
                f"🎨 Обработка {len(photo_paths)} фото на GPU...\n"
                f"Это займет ~30-60 сек"
            )

            logger.info(f"🚀 Отправка {len(photo_paths)} фото на RunPod...")

            # Конвертируем локальные файлы в base64 для отправки
            photo_data = []
            for photo_path in photo_paths[:10]:  # Лимит 10 фото
                with open(photo_path, 'rb') as f:
                    photo_base64 = base64.b64encode(f.read()).decode('utf-8')
                    photo_data.append(photo_base64)

            # Вызываем RunPod API
            runpod_response = requests.post(
                RUNPOD_API_URL,
                json={
                    "input": {
                        "photo_urls": photo_data  # Отправляем base64 вместо URL
                    }
                },
                headers={
                    "Authorization": f"Bearer {RUNPOD_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=300
            )

            logger.info(f"RunPod ответ: {runpod_response.status_code}")

            if runpod_response.status_code != 200:
                logger.error(f"RunPod error: {runpod_response.text}")
                await status_msg.edit_text(
                    result_text + "\n\n❌ Ошибка обработки фото на сервере",
                    disable_web_page_preview=True
                )
                return

            result = runpod_response.json()

            if result.get("status") == "success":
                # Получаем ZIP с очищенными фото
                zip_base64 = result.get("zip_base64")
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
                error = result.get("error", "Unknown error")
                logger.error(f"RunPod error: {error}")
                await status_msg.edit_text(
                    result_text + f"\n\n❌ Ошибка: {error}",
                    disable_web_page_preview=True
                )

            # Очистка temp_dir
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())

            try:
                await status_msg.delete()
            except:
                pass

            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

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
