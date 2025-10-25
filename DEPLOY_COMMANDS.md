# 🚀 Готовые команды для деплоя на ваш VPS

**VPS информация:**
- IP: 185.244.40.155
- Домен: 694203.cloud4box.ru
- Пользователь: root
- Путь проекта: /root/projects/idi_motors_bot

---

## 📋 Команды для копипасты

### 1️⃣ Подключение к VPS

```bash
ssh root@185.244.40.155
```

---

### 2️⃣ Установка зависимостей (если еще не установлены)

```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

---

### 3️⃣ Создание директории и клонирование проекта

```bash
mkdir -p /root/projects
cd /root/projects
git clone https://github.com/YOUR_USERNAME/rus_bot.git idi_motors_bot
cd idi_motors_bot
```

**⚠️ ЗАМЕНИТЕ `YOUR_USERNAME` на ваш GitHub username!**

Или если репозиторий уже на GitHub, используйте полный URL.

---

### 4️⃣ Настройка токенов

```bash
cp .env.example .env
nano .env
```

**Вставьте ваши токены:**
```
BOT_TOKEN=ваш_telegram_bot_token
OPENAI_API_KEY=ваш_openai_api_key
```

Сохранить: `Ctrl+X`, `Y`, `Enter`

---

### 5️⃣ Обновление systemd service файлов

```bash
sed -i 's|YOUR_USERNAME|root|g' systemd/iopaint.service
sed -i 's|/home/YOUR_USERNAME/rus_bot|/root/projects/idi_motors_bot|g' systemd/iopaint.service

sed -i 's|YOUR_USERNAME|root|g' systemd/rusbot.service
sed -i 's|/home/YOUR_USERNAME/rus_bot|/root/projects/idi_motors_bot|g' systemd/rusbot.service
```

---

### 6️⃣ Автоматический деплой

```bash
chmod +x deploy.sh
./deploy.sh
```

Скрипт автоматически:
- ✅ Создаст виртуальное окружение
- ✅ Установит зависимости
- ✅ Настроит systemd сервисы
- ✅ Запустит IOPaint и бота
- ✅ Включит автозапуск

---

### 7️⃣ Проверка статуса

```bash
systemctl status rusbot.service
systemctl status iopaint.service
```

---

## 📊 Полезные команды для управления

### Просмотр логов в реальном времени

```bash
# Логи бота
journalctl -u rusbot.service -f

# Логи IOPaint
journalctl -u iopaint.service -f

# Оба сразу
journalctl -u rusbot.service -u iopaint.service -f
```

### Перезапуск сервисов

```bash
# Перезапуск бота
systemctl restart rusbot.service

# Перезапуск IOPaint
systemctl restart iopaint.service

# Перезапуск обоих (правильный порядок)
systemctl restart iopaint.service && sleep 3 && systemctl restart rusbot.service
```

### Остановка сервисов

```bash
systemctl stop rusbot.service
systemctl stop iopaint.service
```

### Запуск сервисов

```bash
systemctl start iopaint.service
sleep 3
systemctl start rusbot.service
```

---

## 🔄 Обновление кода после изменений

```bash
cd /root/projects/idi_motors_bot
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
systemctl restart iopaint.service && sleep 3 && systemctl restart rusbot.service
```

---

## 🐛 Troubleshooting

### Если бот не запускается

```bash
# Проверить логи
journalctl -u rusbot.service -n 50 --no-pager

# Проверить статус IOPaint
systemctl status iopaint.service

# Проверить .env файл
cat /root/projects/idi_motors_bot/.env
```

### Если IOPaint не запускается

```bash
# Логи IOPaint
journalctl -u iopaint.service -n 50 --no-pager

# Проверить порт 8085
netstat -tuln | grep 8085

# Запустить вручную для отладки
cd /root/projects/idi_motors_bot
source venv/bin/activate
iopaint start --model=lama --device=cpu --port=8085 --host=127.0.0.1
```

### Проверка использования ресурсов

```bash
# CPU и RAM
htop

# Процессы бота
ps aux | grep -E "iopaint|rus_bot"

# Дисковое пространство
df -h
```

---

## ✅ Готово!

После выполнения всех команд ваш бот будет работать 24/7 на VPS с автозапуском при перезагрузке.

**Тестирование:** Отправьте боту в Telegram ссылку на BeForward.jp
