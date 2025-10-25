# 🚀 Быстрый старт

## 1. Установка

```bash
install.bat
```

## 2. Настройка токена

Создайте файл `.env`:
```
BOT_TOKEN=ваш_токен_от_BotFather
```

## 3. Запуск

### Окно 1: IOPaint (не закрывать!)
```bash
start_iopaint.bat
```
Дождитесь: "Running on http://127.0.0.1:8085"

### Окно 2: Telegram Bot
```bash
run.bat
```

## 4. Готово! 🎉

Отправьте боту ссылку на BeForward.jp

---

## ⚠️ Устранение неполадок

### IOPaint не запускается
```bash
# Проверьте установку
venv\Scripts\activate
pip install iopaint
```

### Бот не подключается к IOPaint
- Убедитесь, что IOPaint запущен первым
- Проверьте, что порт 8085 свободен

### Ошибка "Bot token not found"
- Создайте файл `.env` с вашим токеном
- Или измените токен в rus_bot.py (строка 699)

