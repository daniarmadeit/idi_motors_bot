"""
RunPod Serverless Handler для BeForward Parser Bot
Принимает webhook запросы от Telegram и обрабатывает их
"""
import asyncio
import json
import logging
import os
import sys
import subprocess
import time

import runpod
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

import config
from rus_bot import TelegramBot, BeForwardParser

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для переиспользования между вызовами
bot_instance = None
application = None
iopaint_process = None


def start_iopaint():
    """Запускает IOPaint сервер с GPU поддержкой"""
    global iopaint_process

    try:
        logger.info("🎨 Запуск IOPaint сервера...")

        # Определяем device (cuda если доступен, иначе cpu)
        device = "cuda" if os.path.exists("/usr/local/cuda") else "cpu"
        logger.info(f"🖥️ Используется device: {device}")

        # Запускаем IOPaint в фоновом режиме
        iopaint_process = subprocess.Popen([
            "iopaint", "start",
            "--model=lama",
            f"--device={device}",
            "--port=8080",
            "--host=0.0.0.0"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Ждем 5 секунд для инициализации
        time.sleep(5)

        logger.info("✅ IOPaint сервер запущен на порту 8080")

    except Exception as e:
        logger.error(f"❌ Ошибка запуска IOPaint: {e}")
        raise


def initialize_bot():
    """Инициализация бота (вызывается один раз при холодном старте)"""
    global bot_instance, application

    if not config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен")
        raise ValueError("BOT_TOKEN is required")

    logger.info("🔧 Инициализация бота...")

    # Запускаем IOPaint сервер
    start_iopaint()

    # Создаем экземпляр парсера и бота
    bot_instance = TelegramBot(config.BOT_TOKEN)

    # Настраиваем Application для webhook режима
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot_instance.start_command))
    application.add_handler(CommandHandler("restart", bot_instance.restart_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_url))
    application.add_handler(CallbackQueryHandler(bot_instance.handle_download, pattern="^(download_|generate_)"))
    application.add_error_handler(bot_instance.error_handler)

    # Инициализируем application
    asyncio.run(application.initialize())

    logger.info("✅ Бот инициализирован")

    return application


async def process_update(update_data: dict):
    """
    Обрабатывает одно обновление от Telegram

    Args:
        update_data: JSON данные от Telegram webhook

    Returns:
        dict: Результат обработки
    """
    global application

    try:
        # Преобразуем JSON в Update объект
        update = Update.de_json(update_data, application.bot)

        if not update:
            logger.warning("⚠️ Пустое обновление")
            return {"status": "ignored", "reason": "empty update"}

        logger.info(f"📨 Получено обновление: {update.update_id}")

        # Обрабатываем обновление через application
        await application.process_update(update)

        logger.info(f"✅ Обновление {update.update_id} обработано")

        return {
            "status": "success",
            "update_id": update.update_id
        }

    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        import traceback
        logger.error(traceback.format_exc())

        return {
            "status": "error",
            "error": str(e)
        }


def handler(event):
    """
    RunPod serverless handler

    Args:
        event: Событие от RunPod с входными данными

    Returns:
        dict: Результат выполнения
    """
    global application

    # Инициализация при первом запуске (холодный старт)
    if application is None:
        try:
            initialize_bot()
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            return {
                "error": f"Initialization failed: {str(e)}"
            }

    # Получаем входные данные
    input_data = event.get("input", {})

    # Проверяем тип запроса
    if "telegram_update" in input_data:
        # Webhook от Telegram
        update_data = input_data["telegram_update"]

        # Обрабатываем обновление
        result = asyncio.run(process_update(update_data))

        return result

    elif "url" in input_data:
        # Прямой запрос на парсинг URL (для тестирования)
        url = input_data["url"]

        try:
            parser = BeForwardParser()
            car_data = parser.parse_car_data(url)
            formatted = parser.format_car_data(car_data)

            return {
                "status": "success",
                "car_data": car_data,
                "formatted": formatted
            }
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    else:
        return {
            "error": "Invalid input. Expected 'telegram_update' or 'url'"
        }


# Запуск RunPod serverless
if __name__ == "__main__":
    logger.info("🚀 Запуск RunPod Serverless Handler")
    runpod.serverless.start({"handler": handler})
