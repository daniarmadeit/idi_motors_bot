"""
Configuration file for BeForward Parser Bot
"""
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


# ============================================================================
# TELEGRAM BOT SETTINGS
# ============================================================================
BOT_TOKEN = os.getenv('BOT_TOKEN', '')


# ============================================================================
# OPENAI SETTINGS
# ============================================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = "gpt-5-nano"
OPENAI_TIMEOUT = 30  # секунд


# ============================================================================
# IOPAINT SETTINGS
# ============================================================================
IOPAINT_URL = "http://127.0.0.1:8085"
IOPAINT_INPAINT_ENDPOINT = "/api/v1/inpaint"
IOPAINT_UPSCALE_ENDPOINT = "/api/v1/run_plugin_gen_image"
IOPAINT_CONFIG_ENDPOINT = "/api/v1/server-config"


# ============================================================================
# IMAGE PROCESSING SETTINGS
# ============================================================================
# Лимит фото для обработки
PHOTO_PROCESSING_LIMIT = 20  # Продакшен лимит

# Telegram лимит фото в альбоме
TELEGRAM_MEDIA_GROUP_LIMIT = 10

# Минимальное разрешение для upscaling
MIN_RESOLUTION_WIDTH = 1920
MIN_RESOLUTION_HEIGHT = 1080
MIN_RESOLUTION = MIN_RESOLUTION_WIDTH * MIN_RESOLUTION_HEIGHT

# Upscaling множитель
UPSCALE_FACTOR = 2

# Настройки водяного знака
WATERMARK_WIDTH = 300
WATERMARK_HEIGHT = 30

# Поддерживаемые форматы изображений
SUPPORTED_IMAGE_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']


# ============================================================================
# BEFORWARD PARSER SETTINGS
# ============================================================================
# Исключаемые поля при парсинге
EXCLUDED_FIELDS = ['Chassis', 'Sub Ref', 'Ref. No', 'Ref No']

# ID страны для Замбии (используется для получения цен доставки в африканские порты)
ZAMBIA_COUNTRY_ID = 88

# User Agent для запросов
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Таймауты для HTTP запросов
REQUEST_TIMEOUT = 10  # секунд
PHOTO_DOWNLOAD_TIMEOUT = 120  # секунд (ZIP с фото может быть большой)
INPAINT_TIMEOUT = 120  # секунд
UPSCALE_TIMEOUT = 180  # секунд


# ============================================================================
# OPENAI PROMPT SETTINGS
# ============================================================================
OPENAI_SYSTEM_PROMPT = "You are a professional car sales copywriter specializing in the African automotive market, creating Facebook posts for IDI MOTORS."

OPENAI_USER_PROMPT_TEMPLATE = """Create a Facebook sales post for this vehicle using the EXACT structure shown in the example below.

Vehicle: {car_name}
Price: {price}

Specifications:
{specs_text}

REQUIRED STRUCTURE (follow this format exactly):

🚗 [YEAR MAKE MODEL] — [Catchy Tagline with Key Benefits]! ⚡

[Opening paragraph highlighting main appeal and vehicle origin]

🔹 Engine: [engine details]
🔹 Transmission: [transmission type]
🔹 Mileage: [mileage]
🔹 Drive: [drive type]
🔹 Color: [color]
🔹 Year: [year]
🔹 [Add other key specs if available]

[Middle paragraph emphasizing reliability, fuel economy, practicality for African roads, and ideal use cases - families, professionals, businesses]

[Third paragraph about interior comfort, features, or passenger capacity if relevant]

💰 PRICE: [PRICE IN LARGE CAPS]
📞 Contact: +260970100101
🚚 Reliable shipping from Japan to anywhere in Africa with IDI MOTORS

[Closing line with call to action - create urgency]

Why Choose IDI MOTORS?
✅ Direct imports from Japan
✅ Trusted shipping across Africa
✅ Quality vehicles at competitive prices
✅ Based in Lusaka, Zambia — serving all of Africa

#JapaneseUsedCars #CarForSale #LusakaZambia #ZambiaCars #AfricanMarket #IDI_Motors #ToyotaForSale #ReliableCars #JapanToAfrica #UsedCarsZambia

IMPORTANT:
- Write in English
- Use emojis for visual appeal
- Make price stand out
- Include contact number +260970100101
- Mention IDI MOTORS
- Emphasize Japan to Africa shipping reliability
- Add relevant hashtags for Zambia/Lusaka/Africa
- Keep it professional but bold and persuasive"""
