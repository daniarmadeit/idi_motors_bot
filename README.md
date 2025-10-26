# IDI Motors Bot

Telegram бот для парсинга автомобилей с BeForward.jp с автоматической обработкой изображений (удаление водяных знаков, апскейлинг) и генерацией описаний через OpenAI.

## 🚀 Быстрый деплой на Ubuntu сервере (один скрипт)

### Для первого развертывания:

```bash
# 1. Установить git (если нет)
apt update && apt install -y git

# 2. Клонировать и задеплоить
git clone https://github.com/daniarmadeit/idi_motors_bot.git
cd idi_motors_bot
bash deploy.sh

# 3. Настроить токены
nano .env
# Добавьте BOT_TOKEN и OPENAI_API_KEY, сохраните (Ctrl+O, Enter, Ctrl+X)

# 4. Перезапустить
systemctl restart iopaint.service
systemctl restart rusbot.service
```

### Для обновления на сервере:

```bash
cd ~/idi_motors_bot
bash deploy.sh
```

## Что делает deploy.sh автоматически:

- ✅ Обновляет систему (`apt update && upgrade`)
- ✅ Устанавливает все системные зависимости (Python, OpenCV, Pillow, OpenMP)
- ✅ Клонирует/обновляет код из GitHub
- ✅ Пересоздаёт виртуальное окружение с нуля
- ✅ Устанавливает Python пакеты (IOPaint, Telegram Bot, OpenAI и др.)
- ✅ Создаёт systemd сервисы для автозапуска
- ✅ Запускает IOPaint и бота
- ✅ Настраивает автозапуск при перезагрузке сервера

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

- Ubuntu 20.04+ (рекомендуется 22.04 или 24.04)
- Python 3.10+
- Минимум 2GB RAM (рекомендуется 4GB)
- Telegram Bot Token (получить у @BotFather)
- OpenAI API Key

## Решение проблем

### Если IOPaint не запустился

```bash
# Проверить логи
journalctl -u iopaint.service -n 100

# Убедиться что все зависимости установлены
apt install -y libgl1 libglib2.0-0 libgomp1

# Пересоздать окружение
cd ~/idi_motors_bot
rm -rf venv
bash deploy.sh
```

### Если бот не отвечает

```bash
# Проверить логи
journalctl -u rusbot.service -n 100

# Проверить .env файл
cat ~/idi_motors_bot/.env

# Перезапустить
systemctl restart rusbot.service
```

## Технологии

- **IOPaint** (MIGAN модель) - удаление водяных знаков
- **RealESRGAN** - апскейлинг изображений
- **OpenAI GPT** - генерация описаний
- **BeautifulSoup** - парсинг BeForward.jp
- **python-telegram-bot** - Telegram API
