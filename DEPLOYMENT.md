# 🚀 Deployment Guide - VPS Deployment with systemd

Полная инструкция по деплою BeForward Parser Bot на VPS с автозапуском через systemd.

## 📋 Требования

- Ubuntu/Debian VPS (рекомендуется Ubuntu 20.04+)
- Python 3.8+
- Git
- Минимум 1GB RAM (для IOPaint)
- Минимум 2GB дискового пространства

---

## 🎯 Быстрый деплой (автоматический)

### 1. Подключитесь к VPS

```bash
ssh your_username@your_vps_ip
```

### 2. Скачайте проект

```bash
cd ~
git clone YOUR_REPO_URL rus_bot
cd rus_bot
```

### 3. Настройте токены

```bash
cp .env.example .env
nano .env
```

Добавьте ваши токены:
```
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

Сохраните: `Ctrl+X`, `Y`, `Enter`

### 4. Запустите автоматический деплой

```bash
chmod +x deploy.sh
./deploy.sh
```

Скрипт автоматически:
- ✅ Проверит зависимости
- ✅ Создаст виртуальное окружение
- ✅ Установит Python пакеты
- ✅ Настроит systemd сервисы
- ✅ Запустит IOPaint и бота
- ✅ Включит автозапуск при перезагрузке

### 5. Проверьте статус

```bash
sudo systemctl status rusbot.service
sudo systemctl status iopaint.service
```

✨ **Готово!** Бот работает 24/7 с автозапуском.

---

## 🔧 Ручной деплой (пошагово)

Если хотите больше контроля, выполните шаги вручную:

### Шаг 1: Установка зависимостей

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y
```

### Шаг 2: Клонирование проекта

```bash
cd ~
git clone YOUR_REPO_URL rus_bot
cd rus_bot
```

### Шаг 3: Виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 4: Настройка .env

```bash
cp .env.example .env
nano .env
```

### Шаг 5: Настройка systemd

Отредактируйте service файлы (замените `YOUR_USERNAME` на ваш username):

```bash
USERNAME=$(whoami)
sed -i "s|YOUR_USERNAME|$USERNAME|g" systemd/iopaint.service
sed -i "s|YOUR_USERNAME|$USERNAME|g" systemd/rusbot.service
```

Скопируйте в systemd:

```bash
sudo cp systemd/iopaint.service /etc/systemd/system/
sudo cp systemd/rusbot.service /etc/systemd/system/
```

Создайте лог-файлы:

```bash
sudo touch /var/log/iopaint.log /var/log/iopaint-error.log
sudo touch /var/log/rusbot.log /var/log/rusbot-error.log
sudo chown $USER:$USER /var/log/iopaint*.log /var/log/rusbot*.log
```

### Шаг 6: Запуск сервисов

```bash
sudo systemctl daemon-reload
sudo systemctl enable iopaint.service
sudo systemctl enable rusbot.service
sudo systemctl start iopaint.service
sleep 3
sudo systemctl start rusbot.service
```

### Шаг 7: Проверка статуса

```bash
sudo systemctl status iopaint.service
sudo systemctl status rusbot.service
```

---

## 📊 Управление сервисами

### Просмотр логов в реальном времени

```bash
# Логи бота
sudo journalctl -u rusbot.service -f

# Логи IOPaint
sudo journalctl -u iopaint.service -f
```

### Перезапуск сервисов

```bash
# Перезапустить бота
sudo systemctl restart rusbot.service

# Перезапустить IOPaint
sudo systemctl restart iopaint.service

# Перезапустить оба
sudo systemctl restart iopaint.service && sleep 3 && sudo systemctl restart rusbot.service
```

### Остановка сервисов

```bash
sudo systemctl stop rusbot.service
sudo systemctl stop iopaint.service
```

### Запуск сервисов

```bash
sudo systemctl start iopaint.service
sleep 3
sudo systemctl start rusbot.service
```

### Отключение автозапуска

```bash
sudo systemctl disable rusbot.service
sudo systemctl disable iopaint.service
```

---

## 🔄 Обновление кода

### Автоматическое обновление

```bash
cd ~/rus_bot
./deploy.sh
```

### Ручное обновление

```bash
cd ~/rus_bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart iopaint.service
sleep 3
sudo systemctl restart rusbot.service
```

---

## 🐛 Troubleshooting

### Бот не запускается

1. Проверьте логи:
```bash
sudo journalctl -u rusbot.service -n 50
```

2. Проверьте .env файл:
```bash
cat .env
```

3. Проверьте статус IOPaint (бот требует IOPaint):
```bash
sudo systemctl status iopaint.service
```

### IOPaint не запускается

1. Проверьте логи:
```bash
sudo journalctl -u iopaint.service -n 50
```

2. Проверьте доступность порта 8085:
```bash
netstat -tuln | grep 8085
```

3. Попробуйте запустить вручную:
```bash
source ~/rus_bot/venv/bin/activate
iopaint start --model=lama --device=cpu --port=8085
```

### Ошибка "Permission denied"

Проверьте права на лог-файлы:
```bash
sudo chown $USER:$USER /var/log/iopaint*.log /var/log/rusbot*.log
```

### Высокое использование CPU

IOPaint на CPU может потреблять много ресурсов. Рассмотрите:
- Использование GPU (если доступно)
- Upgrade VPS до более мощного
- Уменьшение лимита обрабатываемых фото в `config.py`

---

## 🔐 Безопасность

### Защита .env файла

```bash
chmod 600 ~/rus_bot/.env
```

### Файрвол (опционально)

Если нужно открыть порты:
```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

IOPaint работает на локальном 127.0.0.1:8085 - порт закрыт извне.

---

## 📈 Мониторинг

### Проверка статуса всех сервисов

```bash
systemctl status iopaint.service rusbot.service
```

### Использование ресурсов

```bash
# CPU и память
top -p $(pgrep -f "iopaint|rus_bot.py" | tr '\n' ',' | sed 's/,$//')

# Дисковое пространство
df -h
```

---

## 📝 Полезные команды

```bash
# Просмотр всех логов бота
sudo journalctl -u rusbot.service

# Последние 100 строк логов IOPaint
sudo journalctl -u iopaint.service -n 100

# Логи с определённой даты
sudo journalctl -u rusbot.service --since "2024-10-25"

# Очистка старых логов (освобождение места)
sudo journalctl --vacuum-time=7d
```

---

## 🎉 Успешный деплой!

Теперь ваш бот:
- ✅ Работает 24/7
- ✅ Автоматически запускается при перезагрузке VPS
- ✅ Логи сохраняются в systemd journal
- ✅ Легко управляется через systemctl

**Для тестирования:** Отправьте боту ссылку на BeForward.jp в Telegram!
