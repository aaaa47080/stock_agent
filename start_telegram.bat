@echo off
start "OpenCode Server" /MIN cmd /c "opencode serve --port 4096"
timeout /t 5 /nobreak >nul
start "Telegram Bot" /MIN cmd /c "npx @grinev/opencode-telegram-bot"
echo Both services started in background (minimized windows).
echo Computer sleep will NOT stop them.
