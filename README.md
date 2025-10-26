# IDI Motors Bot

Telegram бот для парсинга автомобилей с BeForward.jp с автоматической обработкой изображений (удаление водяных знаков, апскейлинг) и генерацией описаний через OpenAI.

## Быстрый деплой на Ubuntu сервере

### Шаг 1: Клонировать репозиторий на сервере

```bash
git clone https://github.com/daniarmadeit/idi_motors_bot.git
cd idi_motors_bot
```

### Шаг 2: Запустить скрипт деплоя

```bash
sudo bash deploy.sh
```

Скрипт автоматически:
- Обновит систему
- Установит Python и зависимости
- Создаст виртуальное окружение
- Установит все пакеты из requirements.txt
- Настроит systemd сервисы для автозапуска
- Запустит IOPaint и бота

### Шаг 3: Настроить .env файл

```bash
nano .env
```

Добавьте:
```env
BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Шаг 4: Перезапустить сервисы

```bash
sudo systemctl restart iopaint.service
sudo systemctl restart rusbot.service
```

## Управление

```bash
# Проверить статус
sudo systemctl status rusbot.service
sudo systemctl status iopaint.service

# Посмотреть логи
sudo journalctl -u rusbot.service -f
sudo journalctl -u iopaint.service -f

# Перезапустить
sudo systemctl restart rusbot.service

# Остановить
sudo systemctl stop rusbot.service
```

## Обновление

```bash
cd ~/idi_motors_bot
sudo bash deploy.sh
```

## Требования

- Ubuntu 20.04+ (рекомендуется 22.04)
- Python 3.10+
- Минимум 2GB RAM
- Telegram Bot Token
- OpenAI API Key

## Технологии

- **IOPaint** (MIGAN модель) - удаление водяных знаков
- **RealESRGAN** - апскейлинг изображений
- **OpenAI GPT** - генерация описаний
- **BeautifulSoup** - парсинг BeForward.jp
- **python-telegram-bot** - Telegram API
