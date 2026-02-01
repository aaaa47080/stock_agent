@echo off
REM ========================================
REM Cloudflare Tunnel 啟動腳本 (Windows)
REM 將本地 8080 端口暴露到公網
REM ========================================

set PORT=8080

echo ==========================================
echo   Cloudflare Tunnel 啟動器
echo ==========================================
echo.

REM 檢查 cloudflared 是否安裝
where cloudflared >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [X] cloudflared 未安裝
    echo.
    echo 請先安裝 cloudflared:
    echo   winget install Cloudflare.cloudflared
    echo   或從 https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ 下載
    pause
    exit /b 1
)

echo [OK] cloudflared 已安裝
cloudflared --version
echo.

echo 啟動臨時 Tunnel (會生成隨機 URL)...
echo.
echo 請將生成的 URL 用於 Pi Browser 測試
echo.

cloudflared tunnel --url http://localhost:%PORT%
