---
name: telegram
description: Start Telegram bot via npx @grinev/opencode-telegram-bot
---

## Prerequisites

1. OpenCode Server must be running in a separate terminal:
```bash
opencode serve --port 4096
```

2. Telegram bot token must be configured in:
   `%APPDATA%/opencode-telegram-bot/.env`
   ```
   TELEGRAM_BOT_TOKEN=<your-bot-token>
   TELEGRAM_ALLOWED_USER_ID=941050130
   OPENCODE_SERVER_USERNAME=opencode
   OPENCODE_MODEL_PROVIDER=zai-coding-plan
   OPENCODE_MODEL_ID=glm-5-turbo
   ```

## Start Telegram Bot

### One-click (background, survives sleep):
```bash
start_telegram.bat
```

### Manual (two terminals):
Terminal 1:
```bash
opencode serve --port 4096
```
Terminal 2:
```bash
npx @grinev/opencode-telegram-bot
```

## Stop Telegram Bot

- **One-click**: Close the minimized windows from taskbar, or `taskkill /IM node.exe`
- **Manual**: Press `Ctrl+C` in each terminal

## Configuration Files

| File | Purpose |
|------|---------|
| `%APPDATA%/opencode-telegram-bot/.env` | Bot token, user ID, model settings |
| `%APPDATA%/opencode-telegram-bot/settings.json` | Session cache, current model, project |

## Troubleshooting

- **409 Conflict**: Kill all bot instances and restart only one
- **OpenCode server unreachable**: Ensure `opencode serve --port 4096` is running
- **Wrong model**: Check settings.json `currentModel` matches `.env` `OPENCODE_MODEL_PROVIDER` and `OPENCODE_MODEL_ID`
