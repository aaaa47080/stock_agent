# Cloudflare Tunnel 設置指南

## 1. 安裝 cloudflared

### Windows
```powershell
# 使用 winget
winget install Cloudflare.cloudflared

# 或下載安裝包
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
```

### Linux
```bash
# Debian/Ubuntu
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

## 2. 登入 Cloudflare

```bash
cloudflared tunnel login
```
這會開啟瀏覽器讓你授權，並下載憑證到 `~/.cloudflared/cert.pem`

## 3. 創建 Tunnel

```bash
# 創建名為 pi-crypto 的 tunnel
cloudflared tunnel create pi-crypto

# 這會生成一個 Tunnel ID 和憑證文件
# 例如: ~/.cloudflared/<TUNNEL_ID>.json
```

## 4. 配置 DNS

```bash
# 將你的域名指向 tunnel
cloudflared tunnel route dns pi-crypto your-domain.com
```

## 5. 配置文件

創建 `~/.cloudflared/config.yml`:

```yaml
tunnel: <YOUR_TUNNEL_ID>
credentials-file: /home/user/.cloudflared/<YOUR_TUNNEL_ID>.json

ingress:
  # 主應用 - 轉發到 8080 端口
  - hostname: your-domain.com
    service: http://localhost:8080

  # API 路徑
  - hostname: api.your-domain.com
    service: http://localhost:8080

  # 默認 - 必須有
  - service: http_status:404
```

## 6. 啟動 Tunnel

### 手動啟動
```bash
cloudflared tunnel run pi-crypto
```

### 作為服務運行 (Linux)
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

### Windows 服務
```powershell
cloudflared service install
net start cloudflared
```

## 7. 快速測試命令 (無需配置)

如果只是臨時測試，可以使用：

```bash
# 直接轉發 8080 端口，會生成臨時 URL
cloudflared tunnel --url http://localhost:8080
```

這會輸出類似：
```
Your quick Tunnel has been created! Visit it at:
https://random-name.trycloudflare.com
```

## 8. 完整啟動腳本

請使用下面創建的 `run_cloudflare.sh` 或 `run_cloudflare.bat`
