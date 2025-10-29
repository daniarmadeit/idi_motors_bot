"""
BeForward Parser Bot - Telegram бот для парсинга автомобилей с BeForward.jp
"""
import asyncio
import base64
import glob
import io
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ChatAction

import config

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BeForwardParser:
    """Парсер для BeForward.jp с AI обработкой изображений"""

    def __init__(self):
        """Инициализация парсера"""
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.USER_AGENT})
        self.excluded_keywords = config.EXCLUDED_FIELDS

        # Инициализация OpenAI
        if not config.OPENAI_API_KEY:
            logger.warning("⚠️ OPENAI_API_KEY не установлен - генерация описаний будет недоступна")
            self.openai_client = None
        else:
            self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    def parse_car_data(self, url: str) -> Dict:
        """Парсит данные автомобиля с BeForward"""
        try:
            # Добавляем параметр для Замбии чтобы получить африканские порты
            url_with_zambia = self._add_zambia_country_param(url)
            logger.info(f"🌍 URL с параметром страны: {url_with_zambia}")
            
            response = self.session.get(url_with_zambia, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            car_data = {
                'car_name': None,
                'specs': {},
                'lusaka_price': None,  # Цена доставки (Dar es Salaam RORO)
                'photo_download_url': None,
                'photo_urls': [],  # Для второй версии
                'url': url
            }
            
            # Название автомобиля
            car_data['car_name'] = self._extract_car_name(soup)
            
            # Характеристики
            car_data['specs'] = self._extract_specs(soup)
            
            # Цена для Dar es Salaam (RORO)
            car_data['lusaka_price'] = self._extract_lusaka_price(soup)
            
            # Ссылка на скачивание фото
            car_data['photo_download_url'] = self._extract_photo_download_url(soup)
            
            # Если вторая версия, собираем ссылки на фото
            if car_data['photo_download_url'] == "COLLECT_PHOTOS":
                car_data['photo_urls'] = self._collect_photo_urls(soup)
            
            return car_data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return {'error': str(e)}
    
    def _extract_car_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлекает название автомобиля"""
        # Первая версия страницы
        h1_selector_v1 = "#list-detail > div.list-detail-right.list-detail-right-renewal > div.car-info-area.cf > div.car-info-flex-area > div > div > h1"
        h1_elem = soup.select_one(h1_selector_v1)
        
        if h1_elem:
            return h1_elem.get_text(strip=True)
        
        # Вторая версия страницы - раздельные селекторы
        make_elem = soup.select_one("#content > h1 > div.make")
        model_elem = soup.select_one("#content > h1 > div.model-year")
        
        if make_elem and model_elem:
            make = make_elem.get_text(strip=True)
            model_text = model_elem.get_text(strip=True)
            
            # Если есть "part model:", берем только первую строку
            if "part model:" in model_text.lower():
                model = model_text.split('\n')[0].strip()
            else:
                model = model_text
            
            return f"{make} {model}"
        
        # Если раздельные не найдены, попробовать общий h1
        h1_selector_v2 = "#content > h1"
        h1_elem = soup.select_one(h1_selector_v2)
        
        if h1_elem:
            return h1_elem.get_text(strip=True)
        
        return None
    
    def _add_zambia_country_param(self, url: str) -> str:
        """Добавляет параметр страны для Замбии (получение африканских цен)

        Args:
            url: URL страницы BeForward

        Returns:
            URL с добавленным параметром tp_country_id
        """
        country_param = f'tp_country_id={config.ZAMBIA_COUNTRY_ID}'

        if '?' in url:
            if 'tp_country_id' not in url:
                return f'{url}&{country_param}'
            return re.sub(r'tp_country_id=\d+', country_param, url)
        return f'{url}?{country_param}'
    
    def _extract_lusaka_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлекает цену для первого города в списке (DAR ES SALAAM)"""
        try:
            # Ищем все заголовки портов/городов
            port_titles = soup.select('p.port-list-title')
            logger.info(f"🔍 Найдено городов: {len(port_titles)}")
            
            if not port_titles:
                logger.warning("❌ Не найдено ни одного города")
                return None
            
            # БЕРЁМ САМЫЙ ПЕРВЫЙ ГОРОД
            first_port = port_titles[0]
            city_name = first_port.get_text(strip=True)
            logger.info(f"✅ Берём первый город: '{city_name}'")
            
            # Проверяем, что это DAR ES SALAAM
            if 'dar' not in city_name.lower() or 'salaam' not in city_name.lower():
                logger.warning(f"⚠️ Первый город не DAR ES SALAAM, а '{city_name}'")
                # Но всё равно берём его цену
            
            # Ищем родительский tr элемент
            tr_element = first_port.find_parent('tr')
            
            if not tr_element:
                logger.error("❌ Не найден родительский TR элемент!")
                return None
            
            logger.info(f"📄 HTML строки (первые 1000 символов):\n{tr_element.prettify()[:1000]}")
            
            # Ищем ячейку с ценой (table-total-price)
            price_cell = tr_element.select_one('td.table-total-price')
            
            if price_cell:
                logger.info("✅ Найдена ячейка table-total-price")
                # Ищем span с ценой
                price_span = price_cell.select_one('span.fn-total-price-display')
                
                if price_span:
                    price_text = price_span.get_text(strip=True)
                    logger.info(f"💰 Найдена цена: '{price_text}'")
                    
                    # Удаляем &nbsp; и лишние пробелы
                    price_text = price_text.replace('\xa0', '').replace('&nbsp;', '').replace(' ', '')
                    logger.info(f"✨ Очищенная цена: '{price_text}'")
                    return price_text
                else:
                    logger.warning("⚠️ Не найден span.fn-total-price-display")
                    logger.info(f"📄 HTML ячейки с ценой:\n{price_cell.prettify()}")
            else:
                logger.warning("⚠️ Не найдена ячейка td.table-total-price")
                # Выводим все td в строке
                all_tds = tr_element.find_all('td')
                logger.info(f"📦 Всего TD в строке: {len(all_tds)}")
                for idx, td in enumerate(all_tds):
                    td_classes = td.get('class', [])
                    logger.info(f"TD #{idx+1} классы: {td_classes}")
            
            return None
        except Exception as e:
            logger.error(f"Ошибка извлечения цены: {e}")
            return None
    
    def _extract_specs(self, soup: BeautifulSoup) -> Dict:
        """Извлекает характеристики"""
        specs = {}
        
        # Первая версия страницы
        table_elem = soup.select_one("#spec > table")
        
        if not table_elem:
            # Вторая версия страницы
            table_elem = soup.select_one("#content > div.specs > table")
        
        if table_elem:
            rows = table_elem.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                # Обрабатываем все ячейки парами
                i = 0
                while i < len(cells) - 1:
                    key = cells[i].get_text(strip=True)
                    value = cells[i + 1].get_text(strip=True)
                    
                    # Проверяем условия фильтрации
                    if key and value:
                        # Пропускаем исключенные поля (проверяем вхождение ключевых слов)
                        should_exclude = False
                        for keyword in self.excluded_keywords:
                            if keyword.lower() in key.lower():
                                should_exclude = True
                                break
                        
                        if should_exclude:
                            i += 2
                            continue
                        
                        # Пропускаем значения с "-"
                        if value == "-":
                            i += 2
                            continue
                        
                        # Удаляем "Find parts for this model code" из значений
                        if "Find parts for this model code" in value:
                            value = value.replace("Find parts for this model code", "").strip()
                        
                        # Добавляем только если значение не пустое после очистки
                        if value and value != "-":
                            specs[key] = value
                    
                    i += 2  # Переходим к следующей паре
        
        return specs

    def _extract_photo_download_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлекает ссылку на скачивание фото"""
        # Первая версия - прямая кнопка скачивания
        download_selector = "#list-detail > div.list-detail-left.list-detail-left-renewal > div.vehicle-share-content > div.dl-pic-area > a"
        download_link = soup.select_one(download_selector)
        
        if download_link:
            href = download_link.get('href')
            if href and href.startswith('/'):
                return "https://www.beforward.jp" + href
            return href
        
        # Вторая версия - собираем фото из слайдера
        slider_wrapper = soup.select_one("#vehicle-photo-slider > div.swiper-wrapper")
        if slider_wrapper:
            slides = slider_wrapper.select("div.swiper-slide")
            if slides:
                # Возвращаем специальный маркер, что нужно собирать фото
                return "COLLECT_PHOTOS"
        
        return None
    
    def _collect_photo_urls(self, soup: BeautifulSoup) -> list:
        """Собирает ссылки на фото из слайдера"""
        photo_urls = []
        slider_wrapper = soup.select_one("#vehicle-photo-slider > div.swiper-wrapper")
        
        if slider_wrapper:
            slides = slider_wrapper.select("div.swiper-slide")
            for slide in slides:
                # Ищем img в слайде
                img = slide.select_one("img")
                if img and img.get("src"):
                    img_src = img.get("src")
                    # Если относительная ссылка, делаем абсолютной
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src
                    elif img_src.startswith("/"):
                        img_src = "https://www.beforward.jp" + img_src
                    photo_urls.append(img_src)
                
                # Также ищем data-src (для lazy loading)
                if img and img.get("data-src"):
                    img_src = img.get("data-src")
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src
                    elif img_src.startswith("/"):
                        img_src = "https://www.beforward.jp" + img_src
                    photo_urls.append(img_src)
        
        return list(set(photo_urls))  # Убираем дубли
    
    def _check_iopaint_server(self, iopaint_url: str) -> bool:
        """Проверяет доступность IOPaint сервера

        Args:
            iopaint_url: URL IOPaint сервера

        Returns:
            True если сервер доступен, False иначе
        """
        try:
            response = self.session.get(
                f"{iopaint_url}{config.IOPAINT_CONFIG_ENDPOINT}",
                timeout=5
            )
            response.raise_for_status()
            logger.info("✅ IOPaint сервер доступен")
            return True
        except Exception as e:
            logger.error(f"❌ IOPaint сервер не доступен на {iopaint_url}")
            logger.error("Запустите start_iopaint.bat в отдельном окне!")
            return False

    def _create_watermark_mask(self, img_width: int, img_height: int) -> Image.Image:
        """Создаёт маску для водяного знака

        Args:
            img_width: Ширина изображения
            img_height: Высота изображения

        Returns:
            PIL Image с маской водяного знака
        """
        mask = Image.new('L', (img_width, img_height), 0)
        draw = ImageDraw.Draw(mask)

        x1 = (img_width - config.WATERMARK_WIDTH) // 2
        y1 = img_height - config.WATERMARK_HEIGHT
        x2 = x1 + config.WATERMARK_WIDTH
        y2 = img_height

        draw.rectangle([x1, y1, x2, y2], fill=255)
        return mask

    def _image_to_base64(self, img: Image.Image) -> str:
        """Конвертирует изображение в base64

        Args:
            img: PIL Image объект

        Returns:
            Base64 строка
        """
        buffer = io.BytesIO()
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _remove_watermark(
        self,
        img: Image.Image,
        iopaint_url: str
    ) -> Optional[Image.Image]:
        """Удаляет водяной знак с изображения через IOPaint

        Args:
            img: PIL Image объект
            iopaint_url: URL IOPaint сервера

        Returns:
            Изображение без водяного знака или None при ошибке
        """
        try:
            img_width, img_height = img.size

            # Конвертируем изображение и маску в base64
            img_base64 = self._image_to_base64(img)
            mask = self._create_watermark_mask(img_width, img_height)
            mask_base64 = self._image_to_base64(mask)

            # Отправляем в IOPaint
            payload = {
                'image': img_base64,
                'mask': mask_base64,
                'ldmSampler': 'plms',
                'hdStrategy': 'Original',
            }

            response = self.session.post(
                f"{iopaint_url}{config.IOPAINT_INPAINT_ENDPOINT}",
                json=payload,
                timeout=config.INPAINT_TIMEOUT
            )

            if response.status_code != 200:
                logger.error(f"❌ Ошибка удаления водяного знака: HTTP {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return None

            # IOPaint API возвращает изображение напрямую в виде байтов (PNG)
            # Согласно документации: сервер конвертирует BGR->RGB, добавляет альфа-канал
            # и возвращает закодированные байты изображения
            result_bytes = response.content
            logger.info(f"✅ Получено {len(result_bytes)} байт от IOPaint")

            return Image.open(io.BytesIO(result_bytes))

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении водяного знака: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _upscale_image(
        self,
        img: Image.Image,
        iopaint_url: str
    ) -> Optional[Image.Image]:
        """Увеличивает разрешение изображения через RealESRGAN

        Args:
            img: PIL Image объект
            iopaint_url: URL IOPaint сервера

        Returns:
            Апскейленное изображение или None при ошибке
        """
        try:
            img_base64 = self._image_to_base64(img)

            payload = {
                'image': img_base64,
                'name': 'RealESRGAN',
                'upscale': config.UPSCALE_FACTOR
            }

            response = self.session.post(
                f"{iopaint_url}{config.IOPAINT_UPSCALE_ENDPOINT}",
                json=payload,
                timeout=config.UPSCALE_TIMEOUT
            )

            if response.status_code != 200:
                logger.warning(f"⚠️ Upscaling не удался (HTTP {response.status_code})")
                logger.warning(f"Response: {response.text[:500]}")
                return None

            # IOPaint API возвращает изображение напрямую в виде байтов
            result_bytes = response.content
            return Image.open(io.BytesIO(result_bytes))

        except Exception as e:
            logger.warning(f"⚠️ Ошибка upscaling: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            return None

    def _process_single_image(
        self,
        image_path: str,
        output_dir: str,
        iopaint_url: str,
        idx: int,
        total: int
    ) -> bool:
        """Обрабатывает одно изображение: удаление водяного знака + upscaling

        Args:
            image_path: Путь к исходному изображению
            output_dir: Директория для сохранения результата
            iopaint_url: URL IOPaint сервера
            idx: Индекс текущего изображения
            total: Общее количество изображений

        Returns:
            True если обработка успешна, False иначе
        """
        filename = os.path.basename(image_path)

        try:
            # Открываем изображение
            img = Image.open(image_path)
            img_width, img_height = img.size
            logger.info(f"📸 Фото {filename}: {img_width}x{img_height}")

            # ШАГ 1: Удаляем водяной знак
            logger.info(f"🎭 Удаляем водяной знак...")
            cleaned_img = self._remove_watermark(img, iopaint_url)

            if cleaned_img is None:
                logger.error(f"❌ Не удалось удалить водяной знак с {filename}")
                img.close()
                return False

            img.close()
            img = cleaned_img
            img_width, img_height = img.size
            logger.info(f"✅ Водяной знак удален")

            # ШАГ 2: Проверяем разрешение и делаем upscaling если нужно
            current_resolution = img_width * img_height

            if current_resolution < config.MIN_RESOLUTION:
                logger.info(f"🔍 Разрешение {img_width}x{img_height} < Full HD - делаем upscaling...")
                upscaled_img = self._upscale_image(img, iopaint_url)

                if upscaled_img is not None:
                    img.close()
                    img = upscaled_img
                    img_width, img_height = img.size
                    logger.info(f"✨ Upscaling выполнен: {img_width}x{img_height}")
                else:
                    logger.warning(f"⚠️ Сохраняем без upscaling")
            else:
                logger.info(f"✅ Разрешение {img_width}x{img_height} - хорошее, upscaling не требуется")

            # ШАГ 3: Сохраняем результат
            output_path = os.path.join(output_dir, filename)
            final_buffer = io.BytesIO()

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(final_buffer, format='PNG')

            with open(output_path, 'wb') as f:
                f.write(final_buffer.getvalue())

            logger.info(f"💾 Сохранено {idx + 1}/{total}: {filename}")
            img.close()
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка обработки {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def download_and_process_photos(
        self,
        photo_download_url: str,
        bot=None,
        chat_id: int = None,
        progress_message=None,
        iopaint_url: str = None,
        car_data_text: str = None
    ) -> Optional[Tuple[bytes, List[str]]]:
        """Скачивает фото ZIP, удаляет водяные знаки через IOPaint HTTP API

        Args:
            photo_download_url: URL для скачивания ZIP архива с фото
            bot: Telegram Bot для отправки статуса
            chat_id: ID чата для отправки статуса
            progress_message: Сообщение для обновления прогресса
            iopaint_url: URL IOPaint сервера (по умолчанию из config)
            car_data_text: Текст с данными автомобиля для добавления в ZIP

        Returns:
            Кортеж из (ZIP архив в байтах, список путей к обработанным фото) или None при ошибке
        """
        if iopaint_url is None:
            iopaint_url = config.IOPAINT_URL

        try:
            # Проверяем доступность IOPaint сервера
            if not self._check_iopaint_server(iopaint_url):
                return None

            # Создаём временные директории
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "photos.zip")
            extract_dir = os.path.join(temp_dir, "extracted")
            output_dir = os.path.join(temp_dir, "cleaned")

            os.makedirs(extract_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            # 1. Скачиваем ZIP
            logger.info(f"📥 Скачиваем фото: {photo_download_url}")

            # Выполняем синхронный HTTP запрос в executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(photo_download_url, timeout=config.PHOTO_DOWNLOAD_TIMEOUT)
            )
            response.raise_for_status()

            with open(zip_path, 'wb') as f:
                f.write(response.content)

            # 2. Распаковываем
            logger.info("📦 Распаковываем архив...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # 3. Находим все изображения
            image_files = []
            for ext in config.SUPPORTED_IMAGE_EXTENSIONS:
                image_files.extend(
                    glob.glob(os.path.join(extract_dir, '**', ext), recursive=True)
                )

            if not image_files:
                logger.warning("⚠️ Не найдено изображений в архиве")
                return None

            logger.info(f"📸 Найдено изображений: {len(image_files)}")

            # 4. Обрабатываем изображения (с лимитом)
            image_files_limited = image_files[:config.PHOTO_PROCESSING_LIMIT]
            logger.info(
                f"🎨 Обрабатываем {len(image_files_limited)} изображений "
                f"(из {len(image_files)})..."
            )

            for idx, image_path in enumerate(image_files_limited):
                # Обновляем прогресс-бар в сообщении
                if progress_message:
                    try:
                        # Создаём визуальный прогресс-бар
                        progress_percent = int((idx / len(image_files_limited)) * 100)
                        filled = int(progress_percent / 5)  # 20 блоков для 100%
                        empty = 20 - filled
                        progress_bar = "█" * filled + "░" * empty

                        progress_text = (
                            f"🎨 Обработка фото: {idx + 1}/{len(image_files_limited)}\n\n"
                            f"[{progress_bar}] {progress_percent}%\n\n"
                            f"⏳ Удаление водяных знаков + AI Upscaling..."
                        )

                        await progress_message.edit_text(progress_text)
                        logger.info(f"✉️ Обновлён прогресс: {idx + 1}/{len(image_files_limited)}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось обновить прогресс: {e}")

                # Отправляем chat action для визуального эффекта
                if bot and chat_id:
                    try:
                        await bot.send_chat_action(
                            chat_id=chat_id,
                            action=ChatAction.UPLOAD_PHOTO
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить chat action: {e}")

                # Запускаем обработку в executor, чтобы не блокировать event loop
                await loop.run_in_executor(
                    None,
                    self._process_single_image,
                    image_path,
                    output_dir,
                    iopaint_url,
                    idx,
                    len(image_files_limited)
                )

            logger.info("✅ IOPaint обработка завершена")

            # Обновляем прогресс на 100%
            if progress_message:
                try:
                    await progress_message.edit_text(
                        f"✅ Обработка завершена!\n\n"
                        f"[████████████████████] 100%\n\n"
                        f"📦 Создаём ZIP архив..."
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить финальный прогресс: {e}")

            # 5. Создаём ZIP с очищенными фото
            cleaned_zip_path = os.path.join(temp_dir, "cleaned_photos.zip")

            processed_files = os.listdir(output_dir)
            if not processed_files:
                logger.error("❌ Не удалось обработать ни одного изображения")
                return None

            # Получаем полные пути к обработанным фото
            cleaned_photo_paths = [
                os.path.join(output_dir, f)
                for f in processed_files
                if os.path.isfile(os.path.join(output_dir, f))
            ]

            with zipfile.ZipFile(cleaned_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Добавляем фото
                for file in processed_files:
                    file_path = os.path.join(output_dir, file)
                    if os.path.isfile(file_path):
                        zip_file.write(file_path, arcname=file)

                # Добавляем TXT файл с данными автомобиля если есть
                if car_data_text:
                    txt_content = car_data_text.replace('**', '').replace('*', '')
                    zip_file.writestr("car_data.txt", txt_content.encode('utf-8'))
                    logger.info("✅ TXT файл добавлен в архив")

            # Читаем ZIP в память
            with open(cleaned_zip_path, 'rb') as f:
                zip_bytes = f.read()

            logger.info(
                f"📦 Создан ZIP с {len(processed_files)} очищенными фото: "
                f"{len(zip_bytes)} байт"
            )
            return (zip_bytes, cleaned_photo_paths)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки фото: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Уведомляем пользователя об ошибке
            if progress_message:
                try:
                    error_text = "❌ Ошибка при обработке фото\n\n"
                    if "timeout" in str(e).lower():
                        error_text += "⏰ Превышен таймаут скачивания.\nПопробуйте ещё раз."
                    else:
                        error_text += f"Причина: {str(e)[:200]}"

                    await progress_message.edit_text(error_text)
                except Exception:
                    pass

            return None

    def format_car_data(self, car_data: Dict) -> str:
        """Форматирует данные для отправки в Telegram"""
        if 'error' in car_data:
            return f"❌ Ошибка: {car_data['error']}"
        
        car_name = car_data.get('car_name', 'Неизвестный автомобиль')
        result = f"🚗 {car_name}\n\n"
        
        # Добавляем цену
        lusaka_price = car_data.get('lusaka_price')
        if lusaka_price:
            result += f"Price - {lusaka_price}\n\n"
        else:
            result += "ℹ️ Цена не найдена\n\n"
        
        if car_data.get('specs'):
            result += "📋 Характеристики:\n"
            for key, value in car_data['specs'].items():
                result += f"• {key}: {value}\n"
        else:
            result += "ℹ️ Характеристики не найдены\n"
        
        return result
    
    def generate_sales_description(self, car_data: Dict) -> Optional[str]:
        """Генерирует продающее описание через OpenAI

        Args:
            car_data: Словарь с данными автомобиля

        Returns:
            Сгенерированное описание или None при ошибке
        """
        if self.openai_client is None:
            logger.error("❌ OpenAI клиент не инициализирован")
            return None

        try:
            logger.info(f"🤖 Генерируем продающее описание через {config.OPENAI_MODEL}...")

            car_name = car_data.get('car_name', 'Unknown vehicle')
            specs = car_data.get('specs', {})
            price = car_data.get('lusaka_price', 'Price available on request')

            logger.info(f"📋 Данные автомобиля: {car_name}")
            logger.info(f"💰 Цена: {price}")
            logger.info(f"📊 Характеристик: {len(specs)}")

            # Формируем промпт
            specs_text = "\n".join([f"- {key}: {value}" for key, value in specs.items()])

            prompt = config.OPENAI_USER_PROMPT_TEMPLATE.format(
                car_name=car_name,
                price=price,
                specs_text=specs_text
            )

            logger.info(f"📝 Промпт готов, длина: {len(prompt)} символов")
            logger.info("🚀 Отправляем запрос в OpenAI...")

            # Отправляем запрос в OpenAI с таймаутом
            response = self.openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": config.OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                timeout=config.OPENAI_TIMEOUT
            )

            logger.info("✅ Получен ответ от OpenAI")
            logger.info(f"📊 Usage: {response.usage}")

            description = response.choices[0].message.content.strip()
            logger.info(f"📝 Описание сгенерировано, длина: {len(description)} символов")
            logger.info("✅ Описание сгенерировано успешно")
            return description

        except Exception as e:
            logger.error(f"❌ Ошибка генерации описания: {e}")
            import traceback
            logger.error(traceback.format_exc())

            if "timeout" in str(e).lower():
                logger.error("⏰ Таймаут при генерации описания")
            return None

class TelegramBot:
    """Telegram бот для работы с BeForward парсером"""

    def __init__(self, token: str):
        """Инициализация бота

        Args:
            token: Токен Telegram бота
        """
        self.token = token
        self.parser = BeForwardParser()
        self.application = None
        self.url_queue = asyncio.Queue()
        self.is_processing = False
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        # Устанавливаем статус при первом запуске
        await self.set_bot_status("🟢 Онлайн")
        
        welcome_text = (
            "👋 Привет, Рус!\n\n"
            "Я бот для парсинга BeForward.jp\n\n"
            "📋 Доступные команды:\n"
            "• /start - запуск бота\n"
            "• /restart - перезапуск бота\n\n"
            "📝 Как использовать:\n"
            "Просто отправь мне ссылку на BeForward.jp и получи данные автомобиля!"
        )
        
        await update.message.reply_text(welcome_text)
        
    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /restart"""
        restart_text = (
            "🔄 Перезапуск бота\n\n"
            "Бот успешно перезапущен, Рус!\n"
            "Готов к работе. Отправляй ссылки на BeForward.jp 🚗"
        )
        
        await update.message.reply_text(restart_text)
        
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL - добавляет в очередь"""
        url = update.message.text.strip()

        # Проверяем, что это ссылка на BeForward
        if 'beforward.jp' not in url.lower():
            await update.message.reply_text(
                "❌ Пожалуйста, отправь ссылку на BeForward.jp",
                parse_mode='Markdown'
            )
            return

        # Добавляем в очередь
        await self.url_queue.put({
            'url': url,
            'update': update,
            'context': context
        })

        queue_size = self.url_queue.qsize()

        if queue_size == 1 and not self.is_processing:
            await update.message.reply_text("✅ Начинаю обработку...")
        else:
            await update.message.reply_text(f"✅ Добавлено в очередь (позиция: {queue_size})")

        # Запускаем обработчик очереди, если он не запущен
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

                logger.info(f"📋 Обрабатываю URL из очереди: {url}")

                # Показываем статус "печатает"
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

                # Отправляем сообщение о начале парсинга
                status_message = await update.message.reply_text("⏳ Парсинг данных...", parse_mode='Markdown')

                try:
                    # Парсим данные
                    car_data = self.parser.parse_car_data(url)

                    # Обновляем статус
                    await status_message.edit_text("📊 Обработка данных...", parse_mode='Markdown')

                    # Форматируем результат
                    result_text = self.parser.format_car_data(car_data)

                    # АВТОМАТИЧЕСКАЯ ОЧИСТКА ФОТО
                    cleaned_zip = None
                    cleaned_photos_paths = None

                    if car_data.get('photo_download_url') and car_data['photo_download_url'] != "COLLECT_PHOTOS":
                        await status_message.edit_text("🎨 Очистка фото от водяных знаков...\n\n[░░░░░░░░░░░░░░░░░░░░] 0%")

                        photo_url = car_data['photo_download_url']
                        result = await self.parser.download_and_process_photos(
                            photo_url,
                            bot=context.bot,
                            chat_id=update.effective_chat.id,
                            progress_message=status_message,
                            car_data_text=result_text
                        )

                        if result:
                            cleaned_zip, cleaned_photos_paths = result
                            logger.info(f"✅ Фото очищены ({len(cleaned_photos_paths)} шт.)")

                    # Создаем кнопку скачивания фото (только одна кнопка)
                    keyboard = []

                    if car_data.get('photo_download_url'):
                        if car_data['photo_download_url'] == "COLLECT_PHOTOS":
                            # Вторая версия - собираем фото через бота
                            keyboard.append([InlineKeyboardButton("📷 Скачать все фото", callback_data=f"download_photos_{update.message.message_id}")])
                        else:
                            # Первая версия - фото УЖЕ очищены, просто скачиваем
                            if cleaned_zip:
                                keyboard.append([InlineKeyboardButton("📷 Скачать фото", callback_data=f"download_ready_photos_{update.message.message_id}")])

                    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

                    # Сохраняем данные для скачивания и генерации описания
                    context.user_data[f"car_data_{update.message.message_id}"] = result_text
                    context.user_data[f"car_full_data_{update.message.message_id}"] = car_data

                    # Сохраняем фото URLs если есть (вторая версия)
                    if car_data.get('photo_urls'):
                        context.user_data[f"photo_data_{update.message.message_id}"] = car_data['photo_urls']

                    # Сохраняем ОЧИЩЕННЫЕ фото если есть
                    if cleaned_zip and cleaned_photos_paths:
                        context.user_data[f"cleaned_zip_{update.message.message_id}"] = cleaned_zip
                        context.user_data[f"cleaned_photos_{update.message.message_id}"] = cleaned_photos_paths

                        # Сохраняем путь к временной директории для очистки
                        if cleaned_photos_paths:
                            temp_dir = os.path.dirname(os.path.dirname(cleaned_photos_paths[0]))
                            context.user_data[f"temp_dir_{update.message.message_id}"] = temp_dir

                    # Отправляем результат (спеки)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=result_text,
                        disable_web_page_preview=True
                    )

                    # Отправляем ПРЕВЬЮ (первые 3 фото) если они есть
                    if cleaned_photos_paths and len(cleaned_photos_paths) > 0:
                        try:
                            preview_count = min(3, len(cleaned_photos_paths))
                            logger.info(f"📸 Отправка превью ({preview_count} фото)...")

                            media_group = []
                            for idx in range(preview_count):
                                photo_path = cleaned_photos_paths[idx]
                                if os.path.exists(photo_path):
                                    with open(photo_path, 'rb') as photo_file:
                                        photo_bytes = photo_file.read()
                                        media_group.append(InputMediaPhoto(media=photo_bytes))

                            if media_group:
                                await context.bot.send_media_group(
                                    chat_id=update.effective_chat.id,
                                    media=media_group
                                )
                                logger.info(f"✅ Превью отправлено ({len(media_group)} фото)")
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки превью: {e}")

                    # Отправляем кнопку скачивания если есть
                    if reply_markup:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=".",  # Минимальный текст (точка)
                            reply_markup=reply_markup
                        )

                    # Удаляем статусное сообщение
                    try:
                        await status_message.delete()
                    except:
                        pass

                except Exception as e:
                    logger.error(f"Ошибка обработки URL: {e}")
                    await status_message.edit_text(f"❌ Ошибка: {str(e)}", parse_mode='Markdown')

                # Помечаем задачу как выполненную
                self.url_queue.task_done()

            except Exception as e:
                logger.error(f"❌ Ошибка в обработчике очереди: {e}")
                import traceback
                logger.error(traceback.format_exc())

        self.is_processing = False
        logger.info("✅ Обработчик очереди завершён")
    
    async def handle_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки скачивания"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data

        if callback_data.startswith('download_cleaned_photos_'):
            # Скачивание фото с очисткой водяных знаков через IOPaint
            message_id = callback_data.split('_')[3]
            photo_url_key = f"photo_url_{message_id}"
            
            if photo_url_key in context.user_data:
                photo_url = context.user_data[photo_url_key]
                
                progress_msg = await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="⏳ Подготовка к обработке фото...\n\n[░░░░░░░░░░░░░░░░░░░░] 0%"
                )

                # Запускаем обработку с передачей progress_message
                result = await self.parser.download_and_process_photos(
                    photo_url,
                    bot=context.bot,
                    chat_id=query.message.chat_id,
                    progress_message=progress_msg
                )
                
                if result:
                    cleaned_zip, cleaned_photos_paths = result

                    # Отправляем фото альбомом
                    if cleaned_photos_paths:
                        try:
                            logger.info(f"📤 Отправка {len(cleaned_photos_paths)} фото (максимум 10 в альбоме)")

                            # Создаем список медиа файлов (максимум 10 в альбоме)
                            media_group = []
                            for idx, photo_path in enumerate(cleaned_photos_paths[:config.TELEGRAM_MEDIA_GROUP_LIMIT]):
                                try:
                                    # Проверяем что файл существует
                                    if not os.path.exists(photo_path):
                                        logger.warning(f"⚠️ Файл не найден: {photo_path}")
                                        continue

                                    # Читаем файл
                                    with open(photo_path, 'rb') as photo_file:
                                        photo_bytes = photo_file.read()
                                        media_group.append(InputMediaPhoto(media=photo_bytes))
                                        logger.info(f"✅ Добавлено фото {idx + 1}/{min(len(cleaned_photos_paths), config.TELEGRAM_MEDIA_GROUP_LIMIT)}")
                                except Exception as e:
                                    logger.error(f"❌ Ошибка чтения фото {photo_path}: {e}")
                                    continue

                            if media_group:
                                logger.info(f"📨 Отправка медиа-группы из {len(media_group)} фото...")
                                await context.bot.send_media_group(
                                    chat_id=query.message.chat_id,
                                    media=media_group
                                )
                                logger.info("✅ Медиа-группа отправлена")
                            else:
                                logger.error("❌ Нет фото для отправки")
                                await context.bot.send_message(
                                    chat_id=query.message.chat_id,
                                    text="❌ Не удалось загрузить обработанные фото"
                                )

                            # Если фото больше 10, отправляем уведомление
                            if len(cleaned_photos_paths) > config.TELEGRAM_MEDIA_GROUP_LIMIT:
                                await context.bot.send_message(
                                    chat_id=query.message.chat_id,
                                    text=f"ℹ️ Показаны первые {config.TELEGRAM_MEDIA_GROUP_LIMIT} фото из {len(cleaned_photos_paths)}"
                                )
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки медиа-группы: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=f"❌ Ошибка отправки фото: {str(e)[:200]}"
                            )
                    
                    # Сохраняем ZIP в памяти и путь к temp dir для очистки
                    zip_key = f"cleaned_zip_{message_id}"
                    temp_dir_key = f"temp_dir_{message_id}"
                    
                    # Получаем путь к временной директории из первого файла
                    if cleaned_photos_paths:
                        temp_dir = os.path.dirname(os.path.dirname(cleaned_photos_paths[0]))
                        context.user_data[temp_dir_key] = temp_dir
                    
                    context.user_data[zip_key] = cleaned_zip
                    
                    keyboard = [[InlineKeyboardButton("📦 Скачать ZIP архив", callback_data=f"download_zip_{message_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="✨ Все фото очищены от водяных знаков!",
                        reply_markup=reply_markup
                    )
                    
                    # Удаляем данные из памяти
                    del context.user_data[photo_url_key]
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="❌ Ошибка при обработке фото. Проверьте логи."
                    )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Данные фото не найдены или устарели"
                )

        elif callback_data.startswith('download_ready_photos_'):
            # Скачивание УЖЕ ГОТОВЫХ очищенных фото (без повторной обработки)
            message_id = callback_data.split('_')[3]
            cleaned_zip_key = f"cleaned_zip_{message_id}"
            cleaned_photos_key = f"cleaned_photos_{message_id}"
            temp_dir_key = f"temp_dir_{message_id}"

            if cleaned_zip_key in context.user_data and cleaned_photos_key in context.user_data:
                cleaned_zip = context.user_data[cleaned_zip_key]
                cleaned_photos_paths = context.user_data[cleaned_photos_key]

                # Отправляем фото альбомом
                if cleaned_photos_paths:
                    try:
                        logger.info(f"📤 Отправка {len(cleaned_photos_paths)} очищенных фото (максимум 10 в альбоме)")

                        # Создаем список медиа файлов (максимум 10 в альбоме)
                        media_group = []
                        for idx, photo_path in enumerate(cleaned_photos_paths[:config.TELEGRAM_MEDIA_GROUP_LIMIT]):
                            try:
                                # Проверяем что файл существует
                                if not os.path.exists(photo_path):
                                    logger.warning(f"⚠️ Файл не найден: {photo_path}")
                                    continue

                                # Читаем файл
                                with open(photo_path, 'rb') as photo_file:
                                    photo_bytes = photo_file.read()
                                    media_group.append(InputMediaPhoto(media=photo_bytes))
                                    logger.info(f"✅ Добавлено фото {idx + 1}/{min(len(cleaned_photos_paths), config.TELEGRAM_MEDIA_GROUP_LIMIT)}")
                            except Exception as e:
                                logger.error(f"❌ Ошибка чтения фото {photo_path}: {e}")
                                continue

                        if media_group:
                            logger.info(f"📨 Отправка медиа-группы из {len(media_group)} фото...")
                            await context.bot.send_media_group(
                                chat_id=query.message.chat_id,
                                media=media_group
                            )
                            logger.info("✅ Медиа-группа отправлена")
                        else:
                            logger.error("❌ Нет фото для отправки")
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text="❌ Не удалось загрузить обработанные фото"
                            )

                        # Если фото больше 10, отправляем уведомление
                        if len(cleaned_photos_paths) > config.TELEGRAM_MEDIA_GROUP_LIMIT:
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=f"ℹ️ Показаны первые {config.TELEGRAM_MEDIA_GROUP_LIMIT} фото из {len(cleaned_photos_paths)}"
                            )
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки медиа-группы: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"❌ Ошибка отправки фото: {str(e)[:200]}"
                        )

                # Предлагаем скачать ZIP
                keyboard = [[InlineKeyboardButton("📦 Скачать ZIP архив", callback_data=f"download_zip_{message_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="✅ Фото отправлены!",
                    reply_markup=reply_markup
                )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Очищенные фото не найдены или устарели"
                )

        elif callback_data.startswith('download_zip_'):
            # Скачивание ZIP архива с очищенными фото
            message_id = callback_data.split('_')[2]
            zip_key = f"cleaned_zip_{message_id}"
            temp_dir_key = f"temp_dir_{message_id}"
            
            if zip_key in context.user_data:
                cleaned_zip = context.user_data[zip_key]
                
                # Отправляем ZIP архив
                zip_buffer = io.BytesIO(cleaned_zip)
                zip_buffer.name = "cleaned_photos.zip"
                
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=zip_buffer,
                    caption="📦 Архив с очищенными фото"
                )
                
                # Очищаем временную директорию
                if temp_dir_key in context.user_data:
                    temp_dir = context.user_data[temp_dir_key]
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"🗑️ Удалена временная директория: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось удалить временную директорию: {e}")
                    del context.user_data[temp_dir_key]
                
                # Удаляем данные из памяти
                del context.user_data[zip_key]
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Архив не найден или устарел"
                )
                
        elif callback_data.startswith('download_photos_'):
            # Скачивание фото для второй версии
            message_id = callback_data.split('_')[2]
            photo_data_key = f"photo_data_{message_id}"
            
            if photo_data_key in context.user_data:
                photo_urls = context.user_data[photo_data_key]
                
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"📷 Скачиваю {len(photo_urls)} фото..."
                )
                
                # Создаем ZIP архив с фото
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, photo_url in enumerate(photo_urls):
                        try:
                            # Скачиваем фото
                            photo_response = self.parser.session.get(photo_url, timeout=10)
                            if photo_response.status_code == 200:
                                # Определяем расширение файла
                                if '.jpg' in photo_url or '.jpeg' in photo_url:
                                    ext = '.jpg'
                                elif '.png' in photo_url:
                                    ext = '.png'
                                else:
                                    ext = '.jpg'  # по умолчанию
                                
                                # Добавляем фото в архив
                                filename = f"photo_{i+1:02d}{ext}"
                                zip_file.writestr(filename, photo_response.content)
                                
                        except Exception as e:
                            logger.error(f"Ошибка скачивания фото {i+1}: {e}")
                
                # Отправляем ZIP файл
                zip_buffer.seek(0)
                zip_buffer.name = "photos.zip"
                
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=zip_buffer,
                    caption="📷 Все фото автомобиля"
                )
                
                # Удаляем данные из памяти
                del context.user_data[photo_data_key]
                
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ Данные фото не найдены или устарели"
                )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                parse_mode='Markdown'
            )
    
    async def set_bot_status(self, status: str):
        """Устанавливает статус бота"""
        try:
            # Динамический статус через команды бота
            await self.application.bot.set_my_commands([
                {"command": "start", "description": f"Запуск бота | {status}"},
                {"command": "restart", "description": "Перезапуск бота"}
            ])
            logger.info(f"Статус бота изменен на: {status}")
        except Exception as e:
            logger.error(f"Ошибка установки статуса: {e}")
    
    def setup_application(self):
        """Настройка приложения"""
        self.application = Application.builder().token(self.token).build()
        
        # Добавляем обработчики
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("restart", self.restart_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url))
        self.application.add_handler(CallbackQueryHandler(self.handle_download, pattern="^(download_|generate_)"))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def post_init(self, application):
        """Выполняется после запуска бота"""
        await self.set_bot_status("🟢 Онлайн")
        logger.info("Бот запущен и готов к работе")
    
    async def post_shutdown(self, application):
        """Выполняется при завершении работы бота"""
        await self.set_bot_status("🔴 Офлайн")
        logger.info("Бот завершил работу")
    
    def run(self):
        """Запуск бота"""
        self.setup_application()
        
        logger.info("Запуск бота...")
        
        # Простой запуск без async операций
        self.application.run_polling(drop_pending_updates=True)

def main():
    """Главная функция запуска бота"""
    # Получаем токен из конфигурации
    if not config.BOT_TOKEN:
        logger.error("❌ Ошибка: BOT_TOKEN не найден в .env файле")
        print("❌ Ошибка: BOT_TOKEN не установлен")
        print("Создайте .env файл и добавьте: BOT_TOKEN=your_token_here")
        return

    logger.info("🚀 Запуск BeForward Parser Bot...")

    # Создаем и запускаем бота
    bot = TelegramBot(config.BOT_TOKEN)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
