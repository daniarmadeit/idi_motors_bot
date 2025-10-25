#!/bin/bash

# BeForward Parser Bot - Deployment Script
# Автоматический деплой на VPS с systemd

set -e  # Остановка при ошибке

echo "🚀 Starting deployment for BeForward Parser Bot..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ!)
# ============================================================================
PROJECT_DIR="$HOME/rus_bot"  # Путь к проекту на VPS
REPO_URL="YOUR_GIT_REPO_URL"  # URL вашего Git репозитория
USERNAME="$USER"  # Текущий пользователь

# ============================================================================
# ФУНКЦИИ
# ============================================================================

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# ============================================================================
# ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ============================================================================

print_info "Checking dependencies..."

# Проверка Python 3
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi
print_success "Python 3 found"

# Проверка pip
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed"
    exit 1
fi
print_success "pip3 found"

# Проверка git
if ! command -v git &> /dev/null; then
    print_error "Git is not installed"
    echo "Install with: sudo apt install git -y"
    exit 1
fi
print_success "Git found"

# ============================================================================
# КЛОНИРОВАНИЕ/ОБНОВЛЕНИЕ ПРОЕКТА
# ============================================================================

if [ -d "$PROJECT_DIR" ]; then
    print_info "Project directory exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull origin main || git pull origin master
    print_success "Code updated"
else
    print_info "Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    print_success "Repository cloned"
fi

# ============================================================================
# ВИРТУАЛЬНОЕ ОКРУЖЕНИЕ
# ============================================================================

print_info "Setting up virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Активация и установка зависимостей
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies installed"

# ============================================================================
# НАСТРОЙКА .env
# ============================================================================

if [ ! -f ".env" ]; then
    print_info "Creating .env file from template..."
    cp .env.example .env
    print_error ".env file created. PLEASE EDIT IT WITH YOUR TOKENS!"
    echo "Edit with: nano $PROJECT_DIR/.env"
    exit 1
else
    print_success ".env file exists"
fi

# ============================================================================
# НАСТРОЙКА SYSTEMD SERVICES
# ============================================================================

print_info "Installing systemd services..."

# Замена плейсхолдеров в service файлах
sed -i "s|YOUR_USERNAME|$USERNAME|g" systemd/iopaint.service
sed -i "s|YOUR_USERNAME|$USERNAME|g" systemd/rusbot.service

# Копирование service файлов
sudo cp systemd/iopaint.service /etc/systemd/system/
sudo cp systemd/rusbot.service /etc/systemd/system/

# Создание лог-файлов
sudo touch /var/log/iopaint.log /var/log/iopaint-error.log
sudo touch /var/log/rusbot.log /var/log/rusbot-error.log
sudo chown $USERNAME:$USERNAME /var/log/iopaint*.log /var/log/rusbot*.log

print_success "Systemd services installed"

# ============================================================================
# ЗАПУСК СЕРВИСОВ
# ============================================================================

print_info "Starting services..."

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable iopaint.service
sudo systemctl enable rusbot.service

# Перезапуск сервисов
sudo systemctl restart iopaint.service
sleep 3  # Ждём запуска IOPaint
sudo systemctl restart rusbot.service

print_success "Services started"

# ============================================================================
# ПРОВЕРКА СТАТУСА
# ============================================================================

print_info "Checking service status..."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "IOPaint Service Status:"
sudo systemctl status iopaint.service --no-pager | head -n 10
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RusBot Service Status:"
sudo systemctl status rusbot.service --no-pager | head -n 10
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ============================================================================
# ПОЛЕЗНЫЕ КОМАНДЫ
# ============================================================================

echo ""
print_success "✨ Deployment completed!"
echo ""
echo "📋 Useful commands:"
echo "  • View bot logs:      sudo journalctl -u rusbot.service -f"
echo "  • View IOPaint logs:  sudo journalctl -u iopaint.service -f"
echo "  • Restart bot:        sudo systemctl restart rusbot.service"
echo "  • Restart IOPaint:    sudo systemctl restart iopaint.service"
echo "  • Stop bot:           sudo systemctl stop rusbot.service"
echo "  • Check status:       sudo systemctl status rusbot.service"
echo ""
print_info "Edit .env if needed: nano $PROJECT_DIR/.env"
