# RunPod Serverless - Полный гайд для IDI Motors Bot

## 📋 Что нужно перед началом

1. Аккаунт на [RunPod.io](https://runpod.io)
2. Telegram Bot Token (от @BotFather)
3. OpenAI API Key
4. Репозиторий на GitHub: `https://github.com/daniarmadeit/idi_motors_bot`

---

## 🚀 Шаг 1: Создание Serverless Endpoint

### 1.1 Открыть RunPod Console

1. Зайти на https://www.console.runpod.io
2. В левом меню выбрать **Serverless**
3. Нажать **+ New Endpoint**

### 1.2 Настроить Hub Configuration

Прокрутить вниз до секции **Hub Configuration** (шаг 1 на скриншоте):

```
Title: idi_motors_bot
Description: Telegram bot for BeForward.jp car parsing
Type: serverless
Category: Image
```

**runpod/hub.json** (создать в корне проекта):
```json
{
  "title": "idi_motors_bot",
  "description": "Telegram bot for parsing cars from BeForward.jp with image processing",
  "type": "serverless",
  "category": "image",
  "iconUrl": "https://example.com/icon.png",
  "config": {
    "runpod": "GPU",
    "containerDiskInGb": 20,
    "presets": []
  }
}
```

### 1.3 Настроить Writing Tests (опционально)

**runpod/tests.json** (для тестирования):
```json
{
  "tests": [
    {
      "name": "validation_url_input",
      "input": {
        "url": "https://beforward.jp/detail/123456"
      },
      "timeout": 30000
    }
  ]
}
```

### 1.4 Убедиться что Dockerfile готов

✅ Уже создан в корне проекта (`Dockerfile`)

---

## 🚀 Шаг 2: Заполнить форму создания Endpoint

### 2.1 Основные настройки

**Endpoint Name**: `idi-motors-bot`

**Select a Template**: Выбрать **"Custom"** → **"Build from GitHub"**

### 2.2 GitHub Configuration

- **GitHub URL**: `https://github.com/daniarmadeit/idi_motors_bot`
- **Branch**: `master`
- **Dockerfile Path**: `./Dockerfile`

### 2.3 Environment Variables

Нажать **Add Environment Variable** и добавить:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | `ваш_telegram_bot_token` |
| `IOPAINT_HOST` | `http://127.0.0.1:8080` |

### 2.4 Compute Configuration

**GPU Type**:
- Для тестирования: **CPU** (дешевле)
- Для продакшена: **NVIDIA RTX 4090** (быстрее обработка фото)

**Container Disk**: `20 GB`

**Idle Timeout**: `5 seconds` (как быстро завершать неактивные воркеры)

**Max Workers**: `3` (максимум одновременных запросов)

**Active Workers**: `0` (не держать воркеры постоянно, только при запросах)

### 2.5 Advanced Settings (опционально)

**FlashBoot**: Включить ✅ (ускоряет холодный старт)

**GPUs per Worker**: `1`

---

## 🚀 Шаг 3: Deploy и получить Endpoint URL

1. Нажать **Deploy** внизу страницы
2. Подождать 5-10 минут (RunPod соберет Docker образ из GitHub)
3. После успешной сборки получите **Endpoint ID**

Ваш endpoint URL будет:
```
https://api.runpod.ai/v2/{endpoint_id}/run
```

Для синхронных запросов (webhook):
```
https://api.runpod.ai/v2/{endpoint_id}/runsync
```

---

## 🔗 Шаг 4: Настроить Telegram Webhook

### 4.1 Установить webhook

Замените `{BOT_TOKEN}` и `{endpoint_id}`:

```bash
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.runpod.ai/v2/{endpoint_id}/runsync",
    "allowed_updates": ["message", "callback_query"]
  }'
```

**Пример**:
```bash
curl -X POST "https://api.telegram.org/bot7234567890:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.runpod.ai/v2/abc123xyz/runsync",
    "allowed_updates": ["message", "callback_query"]
  }'
```

### 4.2 Проверить webhook

```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
```

Ответ должен быть:
```json
{
  "ok": true,
  "result": {
    "url": "https://api.runpod.ai/v2/{endpoint_id}/runsync",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

---

## ✅ Шаг 5: Проверить работу

1. Открыть Telegram
2. Отправить боту: `/start`
3. Отправить ссылку на BeForward: `https://beforward.jp/detail/123456`

### Проверить логи на RunPod

1. Зайти в **Serverless** → **Endpoints**
2. Выбрать `idi-motors-bot`
3. Перейти на вкладку **Logs**
4. Смотреть логи в реальном времени

---

## 🔧 Troubleshooting

### Проблема 1: Webhook не работает

**Проверить статус**:
```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
```

**Удалить webhook** (вернуться на polling):
```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
```

### Проблема 2: Timeout при обработке фото

**Решение**: Увеличить **Idle Timeout** в настройках endpoint до `300 seconds`

### Проблема 3: Бот не отвечает

1. Проверить логи в RunPod Dashboard
2. Проверить Environment Variables (BOT_TOKEN, IOPAINT_HOST)
3. Убедиться что endpoint в статусе **Running**

### Проблема 4: Ошибка сборки Docker

1. Проверить что `Dockerfile` и `handler.py` есть в корне репозитория
2. Проверить что репозиторий публичный на GitHub
3. Пересобрать endpoint (кнопка **Rebuild**)

---

## 💰 Стоимость

RunPod Serverless работает по модели **Pay-as-you-go** (платите только за использование):

- **CPU**: ~$0.0002 за секунду
- **RTX 4090**: ~$0.0014 за секунду
- **Idle время**: $0 (не платите когда бот не используется)

**Пример расчета**:
- 100 запросов в день
- Каждый запрос обрабатывается 30 секунд
- GPU RTX 4090

```
100 запросов × 30 сек × $0.0014 = $4.20/день = ~$126/месяц
```

Для экономии используйте **CPU** для тестирования и **GPU** только для продакшена.

---

## 📊 Мониторинг

### Проверить статус endpoint

```bash
curl "https://api.runpod.ai/v2/{endpoint_id}/health" \
  -H "Authorization: Bearer {your_api_key}"
```

### Посмотреть логи

RunPod Console → Serverless → Endpoints → idi-motors-bot → **Logs**

### Метрики

RunPod Console → Serverless → Endpoints → idi-motors-bot → **Analytics**:
- Requests per minute
- Average response time
- Cold starts
- Error rate

---

## 🔄 Обновление бота

### Обновить код на GitHub

```bash
git add .
git commit -m "Update bot"
git push origin master
```

### Пересобрать endpoint на RunPod

1. RunPod Console → Serverless → Endpoints
2. Выбрать `idi-motors-bot`
3. Нажать **Rebuild** (пересоберет из GitHub)
4. Подождать 5-10 минут

**Webhook останется работать** без дополнительных настроек.

---

## 📚 Полезные ссылки

- [RunPod Serverless Docs](https://docs.runpod.io/serverless/overview)
- [RunPod Handler Functions](https://docs.runpod.io/serverless/workers/handler-functions)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [GitHub Repository](https://github.com/daniarmadeit/idi_motors_bot)

---

## 🎯 Итого: Что получили

✅ **Serverless бот** - работает только при запросах
✅ **Автомасштабирование** - RunPod запускает больше воркеров при нагрузке
✅ **Оплата за использование** - $0 когда бот не используется
✅ **Автообновление** - пересборка за 1 клик из GitHub
✅ **Webhook режим** - мгновенная обработка сообщений

**Следующий шаг**: Отправить `/start` боту в Telegram! 🚀
