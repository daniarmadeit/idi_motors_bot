"""
Упрощенный handler для тестирования
"""
import runpod
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(event):
    """Простой тестовый handler"""
    logger.info(f"Received event: {event}")

    input_data = event.get("input", {})

    if "telegram_update" in input_data:
        update = input_data["telegram_update"]
        message = update.get("message", {})
        text = message.get("text", "")

        logger.info(f"Telegram message: {text}")

        return {
            "status": "success",
            "message": f"Received: {text}"
        }

    return {
        "status": "success",
        "message": "Handler working!"
    }

if __name__ == "__main__":
    logger.info("🚀 Starting simple handler...")
    runpod.serverless.start({"handler": handler})
