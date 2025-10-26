#!/bin/bash

# Скрипт автоматического развертывания IDI Motors Bot на Ubuntu сервере
# Запуск: sudo bash deploy.sh

set -e  # Остановка при ошибке

echo "🚀 Начало развертывания IDI Motors Bot..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Получить текущего пользователя (не root)
if [ "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
else
    REAL_USER=$(whoami)
fi

HOME_DIR=$(eval echo ~$REAL_USER)
PROJECT_DIR="$HOME_DIR/idi_motors_bot"

echo -e "${YELLOW}Пользователь: $REAL_USER${NC}"
echo -e "${YELLOW}Домашняя директория: $HOME_DIR${NC}"
echo -e "${YELLOW}Директория проекта: $PROJECT_DIR${NC}"

# 1. Обновление системы
echo -e "\n${GREEN}[1/8] Обновление системы...${NC}"
apt update && apt upgrade -y

# 2. Установка зависимостей
echo -e "\n${GREEN}[2/8] Установка системных зависимостей...${NC}"
apt install -y python3 python3-pip python3-venv git curl \
    libjpeg-dev zlib1g-dev libpng-dev libtiff-dev \
    libfreetype6-dev liblcms2-dev libwebp-dev \
    libgl1 libglib2.0-0 libgomp1

# 3. Проверка версии Python
echo -e "\n${GREEN}[3/8] Проверка версии Python...${NC}"
PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
echo "Версия Python: $PYTHON_VERSION"

# 4. Клонирование или обновление репозитория
echo -e "\n${GREEN}[4/8] Клонирование/обновление репозитория...${NC}"
if [ -d "$PROJECT_DIR" ]; then
    echo "Директория существует, обновление..."
    cd "$PROJECT_DIR"
    sudo -u $REAL_USER git pull origin master
else
    echo "Клонирование репозитория..."
    cd "$HOME_DIR"
    sudo -u $REAL_USER git clone https://github.com/daniarmadeit/idi_motors_bot.git
    cd "$PROJECT_DIR"
fi

# 5. Создание виртуального окружения и установка зависимостей
echo -e "\n${GREEN}[5/8] Настройка Python окружения...${NC}"

# Удаляем старое venv если есть проблемы с зависимостями
if [ -d "venv" ]; then
    echo "Удаление старого виртуального окружения..."
    rm -rf venv
fi

echo "Создание виртуального окружения..."
sudo -u $REAL_USER python3 -m venv venv

echo "Установка зависимостей..."
sudo -u $REAL_USER bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# 6. Настройка .env файла
echo -e "\n${GREEN}[6/8] Настройка переменных окружения...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Файл .env не найден. Создание из .env.example...${NC}"
    sudo -u $REAL_USER cp .env.example .env
    echo -e "${RED}⚠️  ВАЖНО: Отредактируйте файл .env и добавьте токены!${NC}"
    echo -e "${RED}    nano $PROJECT_DIR/.env${NC}"
    echo -e "${RED}    Добавьте BOT_TOKEN и OPENAI_API_KEY${NC}"
else
    echo ".env файл уже существует"
fi

# 7. Создание systemd сервисов
echo -e "\n${GREEN}[7/8] Создание systemd сервисов...${NC}"

# IOPaint сервис
cat > /etc/systemd/system/iopaint.service << EOF
[Unit]
Description=IOPaint Image Processing Service
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/iopaint start --model=migan --device=cpu --port=8085 --host=127.0.0.1 --enable-realesrgan --realesrgan-model=realesr-general-x4v3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Создан iopaint.service"

# Telegram Bot сервис
cat > /etc/systemd/system/rusbot.service << EOF
[Unit]
Description=IDI Motors Telegram Bot
After=network.target iopaint.service
Requires=iopaint.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python rus_bot.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Создан rusbot.service"

# 8. Запуск сервисов
echo -e "\n${GREEN}[8/8] Запуск сервисов...${NC}"

# Перезагрузка systemd
systemctl daemon-reload

# Остановка старых сервисов (если запущены)
systemctl stop rusbot.service 2>/dev/null || true
systemctl stop iopaint.service 2>/dev/null || true

# Включение автозапуска
systemctl enable iopaint.service
systemctl enable rusbot.service

# Запуск IOPaint
echo "Запуск IOPaint..."
systemctl start iopaint.service

# Ожидание загрузки IOPaint (модели могут грузиться долго)
echo "Ожидание загрузки IOPaint (15 секунд)..."
sleep 15

# Запуск бота
echo "Запуск Telegram бота..."
systemctl start rusbot.service

# Проверка статуса
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Статус сервисов:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

systemctl status iopaint.service --no-pager -l
echo ""
systemctl status rusbot.service --no-pager -l

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Развертывание завершено!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -s "$PROJECT_DIR/.env" ] || ! grep -q "BOT_TOKEN=.\+" "$PROJECT_DIR/.env" 2>/dev/null; then
    echo -e "\n${RED}⚠️  НЕ ЗАБУДЬТЕ настроить .env файл:${NC}"
    echo -e "${YELLOW}1. Отредактируйте: nano $PROJECT_DIR/.env${NC}"
    echo -e "${YELLOW}2. Добавьте BOT_TOKEN и OPENAI_API_KEY${NC}"
    echo -e "${YELLOW}3. Перезапустите сервисы:${NC}"
    echo -e "${YELLOW}   sudo systemctl restart iopaint.service${NC}"
    echo -e "${YELLOW}   sudo systemctl restart rusbot.service${NC}"
fi

echo -e "\n${GREEN}Полезные команды:${NC}"
echo "Логи IOPaint:      sudo journalctl -u iopaint.service -f"
echo "Логи бота:         sudo journalctl -u rusbot.service -f"
echo "Перезапуск:        sudo systemctl restart rusbot.service"
echo "Остановка:         sudo systemctl stop rusbot.service"
echo "Статус:            sudo systemctl status rusbot.service"
