# RunPod Serverless Deployment Guide

## Быстрый старт

### 1. Подготовка Docker образа

```bash
# Залогиниться в Docker Hub
docker login

# Собрать образ
docker build -t yourusername/idi-motors-bot:latest .

# Загрузить на Docker Hub
docker push yourusername/idi-motors-bot:latest
```

### 2. Создание Serverless Endpoint на RunPod

1. Зайти на https://runpod.io
2. Перейти в **Serverless** → **New Endpoint**
3. Заполнить:
   - **Name**: `idi-motors-bot`
   - **Docker Image**: `yourusername/idi-motors-bot:latest`
   - **GPU Type**: CPU (не требуется GPU)
   - **Container Disk**: 10 GB
   - **Environment Variables**:
     ```
     BOT_TOKEN=your_telegram_bot_token
     OPENAI_API_KEY=your_openai_api_key
     IOPAINT_HOST=http://127.0.0.1:8080
     ```

4. Нажать **Deploy**

### 3. Настройка Telegram Webhook

После создания endpoint получите URL вида:
```
https://api.runpod.ai/v2/{endpoint_id}/run
```

Установите webhook для Telegram бота:

```bash
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.runpod.ai/v2/{endpoint_id}/runsync",
    "allowed_updates": ["message", "callback_query"]
  }'
```

**Важно**: используйте `/runsync` для синхронных запросов!

### 4. Проверка работы

Отправьте `/start` вашему боту в Telegram.

## Структура запроса от Telegram

RunPod получает webhook от Telegram в формате:

```json
{
  "input": {
    "telegram_update": {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {...},
        "chat": {...},
        "text": "https://beforward.jp/..."
      }
    }
  }
}
```

## Тестирование локально

```bash
# Запустить handler локально
python handler.py

# В другом терминале отправить тестовый запрос
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "url": "https://beforward.jp/detail/123456"
    }
  }'
```

## Особенности serverless режима

- ✅ **Холодный старт**: бот инициализируется при первом запросе (~5-10 сек)
- ✅ **Автомасштабирование**: RunPod автоматически создает копии при нагрузке
- ✅ **Оплата за использование**: платите только за время выполнения
- ⚠️ **Timeout**: максимальное время выполнения - 5 минут (настраивается)

## Мониторинг

Логи доступны в RunPod Dashboard:
- **Serverless** → **Endpoints** → **Your Endpoint** → **Logs**

## Troubleshooting

### Webhook не работает

Проверить статус webhook:
```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
```

Удалить webhook (вернуться на polling):
```bash
curl "https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
```

### Логи показывают ошибки инициализации

Проверить переменные окружения в RunPod Dashboard.

### Timeout при обработке фото

Увеличить **Max Execution Time** в настройках endpoint (до 300 секунд).
