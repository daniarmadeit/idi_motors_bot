#!/bin/bash
# Автоматический деплой IDI Motors Bot на CPU сервер

set -e  # Остановка при ошибке

echo "🚀 Начинаю установку IDI Motors Bot..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Установка зависимостей
echo -e "${YELLOW}📦 Установка зависимостей...${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git chromium-browser chromium-chromedriver

# 2. Клонирование репозитория
echo -e "${YELLOW}📥 Клонирование репозитория...${NC}"
cd /opt
if [ -d "idi_motors_bot" ]; then
    echo "⚠️  Директория уже существует. Обновляю..."
    cd idi_motors_bot
    sudo git pull
else
    sudo git clone https://github.com/daniarmadeit/idi_motors_bot.git
    cd idi_motors_bot
fi

# 3. Создание venv и установка зависимостей
echo -e "${YELLOW}🐍 Настройка Python окружения...${NC}"
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements_bot.txt

# 4. Создание .env.local
if [ ! -f ".env.local" ]; then
    echo -e "${YELLOW}⚙️  Создание .env.local...${NC}"
    echo "Введите BOT_TOKEN:"
    read BOT_TOKEN
    echo "Введите RUNPOD_API_KEY:"
    read RUNPOD_API_KEY
    echo "Введите RUNPOD_ENDPOINT_ID:"
    read RUNPOD_ENDPOINT_ID

    sudo tee .env.local > /dev/null <<EOF
BOT_TOKEN=$BOT_TOKEN
RUNPOD_API_KEY=$RUNPOD_API_KEY
RUNPOD_ENDPOINT_ID=$RUNPOD_ENDPOINT_ID
EOF
    echo -e "${GREEN}✅ .env.local создан${NC}"
else
    echo -e "${GREEN}✅ .env.local уже существует${NC}"
fi

# 5. Создание systemd service
echo -e "${YELLOW}⚙️  Создание systemd service...${NC}"
sudo tee /etc/systemd/system/idibot.service > /dev/null <<'EOF'
[Unit]
Description=IDI Motors Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/idi_motors_bot
Environment="PATH=/opt/idi_motors_bot/venv/bin"
ExecStart=/opt/idi_motors_bot/venv/bin/python bot_local.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. Запуск сервиса
echo -e "${YELLOW}🚀 Запуск бота...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable idibot
sudo systemctl restart idibot

# 7. Проверка статуса
sleep 2
echo ""
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo ""
echo "📊 Статус бота:"
sudo systemctl status idibot --no-pager

echo ""
echo -e "${GREEN}Полезные команды:${NC}"
echo "  Логи:          sudo journalctl -u idibot -f"
echo "  Перезапуск:    sudo systemctl restart idibot"
echo "  Остановка:     sudo systemctl stop idibot"
echo "  Статус:        sudo systemctl status idibot"
echo ""
echo -e "${GREEN}🎉 Бот работает 24/7!${NC}"
