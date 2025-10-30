"""
IDI Motors Bot - Fast & Clean Version
Telegram бот для парсинга BeForward.jp с обработкой фото на RunPod
"""
import asyncio
import base64
import io
import logging
import os
import tempfile
import zipfile
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загрузка конфигурации
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

MAX_PHOTOS = 30
ZAMBIA_COUNTRY_ID = 88
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


class BeForwardParser:
    """Быстрый парсер BeForward.jp"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def parse(self, url: str) -> Dict:
        """Парсит данные автомобиля"""
        # Добавляем Zambia country ID для африканских портов
        url_with_zambia = f"{url}{'&' if '?' in url else '?'}tp_country_id={ZAMBIA_COUNTRY_ID}"
        logger.info(f"🌍 Парсинг: {url_with_zambia}")

        # Получаем HTML
        response = self.session.get(url_with_zambia, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Извлекаем данные
        data = {
            'url': url,
            'car_name': self._get_car_name(soup),
            'specs': self._get_specs(soup),
            'price': self._get_price_selenium(url_with_zambia),
            'photo_url': self._get_photo_url(soup)
        }

        return data

    def _get_car_name(self, soup) -> str:
        """Извлекает название автомобиля"""
        # Пробуем два варианта селектора (разные версии BeForward)
        h1 = soup.select_one('#list-detail > div.list-detail-right > div > h1')
        if not h1:
            h1 = soup.select_one('#content > h1')
        return h1.get_text(strip=True) if h1 else "Неизвестная модель"

    def _get_specs(self, soup) -> Dict:
        """Извлекает характеристики"""
        specs = {}
        for row in soup.select('.vehicle-detail-list tr'):
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td:
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                # Пропускаем служебные поля
                if key not in ['Chassis', 'Sub Ref', 'Ref. No', 'Ref No']:
                    specs[key] = value
        return specs

    def _get_price_selenium(self, url: str) -> str:
        """Извлекает цену через Selenium (быстрая версия)"""
        driver = None
        try:
            logger.info("⚡ Загрузка страницы...")

            # Настройка Chrome для максимальной скорости
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument(f'user-agent={USER_AGENT}')
            options.page_load_strategy = 'eager'  # Не ждём полной загрузки

            # Отключаем картинки
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)

            driver = webdriver.Chrome(options=options)
            driver.get(url)

            # Умное ожидание элемента с ценой
            wait = WebDriverWait(driver, 10)
            price_elem = wait.until(
                EC.presence_of_element_located((By.ID, "selected_total_price"))
            )

            price_text = price_elem.text.strip()
            logger.info(f"✅ Цена: {price_text}")
            return price_text if price_text else "ASK"

        except Exception as e:
            logger.warning(f"⚠️ Ошибка Selenium: {e}")
            return "ASK"
        finally:
            if driver:
                driver.quit()

    def _get_photo_url(self, soup) -> Optional[str]:
        """Извлекает ссылку на ZIP с фото"""
        link = soup.select_one('a.parts-shop-img')
        if link and 'href' in link.attrs:
            href = link['href']
            if href.startswith('/'):
                return f"https://www.beforward.jp{href}"
            return href
        return None

    def download_photos(self, photo_url: str) -> list:
        """Скачивает и извлекает фото из ZIP"""
        logger.info(f"📥 Скачивание фото...")
        response = self.session.get(photo_url, timeout=120)
        response.raise_for_status()

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'photos.zip')

        with open(zip_path, 'wb') as f:
            f.write(response.content)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Собираем пути к фото
        photos = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    photos.append(os.path.join(root, file))

        logger.info(f"✅ Скачано {len(photos)} фото")
        return photos

    def format_message(self, data: Dict) -> str:
        """Форматирует сообщение для Telegram"""
        lines = [f"🚗 {data['car_name']}", f"💰 Цена: {data['price']}", ""]

        for key, value in data['specs'].items():
            lines.append(f"▫️ {key}: {value}")

        lines.append(f"\n🔗 {data['url']}")
        return "\n".join(lines)


class RusBotFast:
    """Быстрый Telegram бот с RunPod обработкой"""

    def __init__(self):
        self.parser = BeForwardParser()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        await update.message.reply_text(
            "👋 Привет!\n\n"
            "Отправь ссылку на BeForward.jp и получи:\n"
            "✅ Данные автомобиля\n"
            "✅ Очищенные фото (без watermark)\n"
            "✅ Upscale до Full HD\n\n"
            "⚡ Обработка на GPU в облаке!"
        )

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка URL BeForward"""
        url = update.message.text.strip()

        if 'beforward.jp' not in url.lower():
            await update.message.reply_text("❌ Отправь ссылку на BeForward.jp")
            return

        status = await update.message.reply_text("⏳ Парсинг...")

        try:
            # 1. Парсим данные
            data = self.parser.parse(url)
            message_text = self.parser.format_message(data)

            # 2. Проверяем наличие фото
            if not data['photo_url']:
                await status.edit_text(message_text)
                return

            # 3. Скачиваем фото
            await status.edit_text("📥 Скачивание фото...")
            photos = self.parser.download_photos(data['photo_url'])

            if not photos:
                await status.edit_text(message_text + "\n\n⚠️ Фото не найдены")
                return

            # 4. Отправляем на RunPod для обработки
            await status.edit_text(
                f"🎨 Обработка {min(len(photos), MAX_PHOTOS)} фото на GPU...\n"
                f"Это займёт ~30-60 сек"
            )

            # Конвертируем в base64
            photo_data = []
            for photo_path in photos[:MAX_PHOTOS]:
                with open(photo_path, 'rb') as f:
                    photo_data.append(base64.b64encode(f.read()).decode('utf-8'))

            logger.info(f"🚀 Отправка {len(photo_data)} фото на RunPod...")

            # Вызов RunPod API
            response = requests.post(
                RUNPOD_API_URL,
                json={"input": {"photo_urls": photo_data}},
                headers={
                    "Authorization": f"Bearer {RUNPOD_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=300
            )

            if response.status_code != 200:
                raise Exception(f"RunPod error: {response.status_code}")

            result = response.json()
            output = result.get('output', {})

            if output.get('status') == 'success':
                # Декодируем ZIP
                zip_base64 = output.get('zip_base64')
                zip_bytes = base64.b64decode(zip_base64)

                logger.info(f"✅ Получен ZIP ({len(zip_bytes)} байт)")

                # Отправляем результат
                await status.delete()
                car_name = data['car_name'].replace('/', '_')
                await update.message.reply_document(
                    document=io.BytesIO(zip_bytes),
                    filename=f"{car_name}.zip",
                    caption=message_text
                )

                logger.info("✅ Готово!")

            else:
                error = output.get("error", "Unknown error")
                await status.edit_text(message_text + f"\n\n❌ Ошибка: {error}")

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            try:
                await status.delete()
            except:
                pass
            await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")

    def run(self):
        """Запуск бота"""
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url))

        logger.info("🚀 RusBotFast запущен!")
        logger.info(f"📡 RunPod endpoint: {RUNPOD_ENDPOINT_ID}")

        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в .env.local")
    elif not RUNPOD_API_KEY:
        logger.error("❌ RUNPOD_API_KEY не найден в .env.local")
    else:
        bot = RusBotFast()
        bot.run()
