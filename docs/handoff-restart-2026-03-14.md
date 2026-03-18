# Handoff (2026-03-14)

## Context
- 目標：修正前後端流程銜接問題，尤其是登入/設定頁跳轉、非 Pi Browser 防護、會員月費語意一致性。
- 使用者要求：避免過度複雜，能簡化就簡化，在不破壞原功能下修正。

## 已完成
- 修正登入成功後強制跳回 `chat` 的流程（移除自動 `switchTab('chat')`）。
- 修正非 Pi Browser gate 反跳問題（加入 gate lock，避免數秒後又露出 connect wallet）。
- 優化設定頁初始化流程（先顯示頁面，重初始化改背景並行，減少等待感）。
- 修正 Premium 文案由「一次性」改為「月費續費」。
- 修正 Premium 狀態請求授權（補 Authorization header，避免 401）。
- 修正後端升級方案語意（以 `plan` 決定月數，避免前後端不一致）。
- 同步更新多個 forum 頁面的 script version，避免吃舊快取造成新邏輯未生效。

## 主要修改檔案
- `web/js/auth.js`
- `web/js/pi-auth.js`
- `web/js/spa.js`
- `web/js/app.js`
- `web/js/llmSettings.js`
- `web/js/premium.js`
- `web/js/components.js`
- `web/js/i18n.js`
- `web/js/i18n/zh-TW.json`
- `web/js/i18n/en.json`
- `web/index.html`
- `web/forum/premium.html`
- `web/forum/index.html`
- `web/forum/dashboard.html`
- `web/forum/wallet.html`
- `web/forum/post.html`
- `web/forum/create.html`
- `web/forum/profile.html`
- `web/forum/messages.html`
- `api/routers/premium.py`

## 驗證結果
- JS syntax check: PASS
  - `node --check web/js/pi-auth.js`
  - `node --check web/js/auth.js`
  - `node --check web/js/spa.js`
  - `node --check web/js/app.js`
  - `node --check web/js/llmSettings.js`
  - `node --check web/js/premium.js`
- Python syntax check: PASS
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile api/routers/premium.py`
- 單元測試：PASS
  - `./.venv/bin/python -m pytest tests/test_tools_membership.py tests/test_analysis_mode_access.py -q`
- E2E gate 測試：未執行成功（環境缺 `playwright`）
  - `./.venv/bin/python -m pytest pw_test/test_non_pi_browser_gate.py -q`
  - 錯誤：`ModuleNotFoundError: No module named 'playwright'`

## 尚未完成 / 風險
- 尚未完成真實瀏覽器端到端驗證（非 Pi Browser 反跳、設定頁體感延遲）：
  - 目前是程式碼與單元層級修正，需補 UI 實機驗證。
- 專案仍有大量既有頁面載入舊版 `auth.js/app.js` 的歷史風險；
  - 本次已把 forum 主要頁面版本同步，但建議再全站巡檢一次 script version。

## 重啟後建議第一步
1. 確認工作樹狀態：
   - `git status --short`
2. 啟動服務後手動驗證 3 條主線：
   - 非 Pi Browser 開啟：應持續停在 Pi Browser 提示，不應回到 connect wallet。
   - Pi Browser 登入後切 `settings`：不應被拉回 `chat`，不應再彈「歡迎回來」覆蓋流程。
   - Premium 文案/狀態：應顯示月費續費語意，會員狀態 API 不應 401。
3. 如要跑 E2E，先安裝 Playwright 再執行：
   - `./.venv/bin/pip install playwright`
   - `./.venv/bin/python -m playwright install`
   - `./.venv/bin/python -m pytest pw_test/test_non_pi_browser_gate.py -q`

## 本輪續作（2026-03-14）
- 完成全站 script version 巡檢並補齊舊快取風險頁面：
  - `web/scam-tracker/index.html`
  - `web/scam-tracker/detail.html`
  - `web/scam-tracker/submit.html`
  - `web/index.html`（`premium.js` 改為帶版本）
- 補齊內容僅限 cache-busting 版本號，不改任何 JS 邏輯。
- 目前 `web/index.copy.html` 仍存在舊版版本號（備份檔，不在本輪調整範圍）。

## 本輪驗證
- JS syntax check: PASS
  - `node --check web/js/app.js`
  - `node --check web/js/auth.js`
  - `node --check web/js/pi-auth.js`
  - `node --check web/js/spa.js`
  - `node --check web/js/llmSettings.js`
  - `node --check web/js/premium.js`
  - `node --check web/js/i18n.js`
- Python syntax check: PASS
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile api/routers/premium.py`
- 單元測試：PASS
  - `./.venv/bin/python -m pytest tests/test_tools_membership.py tests/test_analysis_mode_access.py -q`

## 本輪續作（frontend-design 全站審視）
- 依 `frontend-design` skill 對全前端入口頁做一致性巡檢，補齊明顯風格與路徑不一致：
  - `web/governance/index.html`
  - `web/governance/governance.css`
  - `web/legal/community-guidelines.html`
  - `web/legal/privacy-policy.html`
- `governance` 修正重點：
  - 靜態資源改為 `/static/...` 絕對路徑（避免 `../../` 在部署路徑下失效）。
  - 新增頁面骨架樣式（body/container/header）並收斂到主站字體與色票。
  - `premium` 導頁改為 `/static/forum/premium.html`，避免相對路徑錯誤。
- `legal` 兩頁修正重點：
  - 導入主站字體（Lora/Mulish/JetBrains），移除舊系統字體風格。
  - 主色與連結色改為品牌色系，降低舊藍紫主題的不一致感。
  - 返回平台連結由 `../../index.html` 改為 `/static/index.html`。

## 本輪驗證（frontend-design）
- JS syntax check: PASS
  - `node --check web/governance/governance.js`
- 路徑檢查：PASS
  - `web/legal/*.html`、`web/governance/index.html` 已無 `../../` 形式的首頁返回路徑。

## 本輪續作（穩定性 / E2E 實機）
- 依使用者要求補做 Playwright 穩定性驗證（非只語法層）。
- 修正 E2E 靜態伺服器 query string 路徑解析問題：
  - 檔案：`pw_test/test_non_pi_browser_gate.py`
  - 檔案：`pw_test/test_verified_mode_market_flow.py`
  - 說明：原本 `translate_path()` 未去除 `?v=xx`，導致 `/static/*.js?v=xx` 全部 404，產生假性 timeout。
- 修正非 Pi Browser gate 真實回歸：
  - 檔案：`web/js/auth.js`
  - 說明：當 `pi-auth` 已鎖 gate 時，`AuthManager.init()` 不應直接還原受保護登入態；
    新增 gate 優先判斷，對非 `password` session 強制維持 guest，避免非 Pi 環境誤打受保護 API。
- 調整分析模式 E2E mock session：
  - 檔案：`pw_test/test_verified_mode_market_flow.py`
  - 說明：為分析模式測試的 mock user 明確加上 `authMethod: "password"`，與 Pi gate 測項分離，避免互相干擾。

## 本輪驗證（穩定性 / E2E）
- Playwright 安裝：PASS
  - `./.venv/bin/pip install playwright`
  - `./.venv/bin/python -m playwright install chromium`
- Non-Pi Browser gate 腳本：PASS
  - `./.venv/bin/python pw_test/test_non_pi_browser_gate.py`
- 分析模式 E2E：PASS（3/3）
  - `./.venv/bin/python -m pytest tests/e2e/test_verified_mode_market_flow.py -q`
- 單元回歸：PASS
  - `./.venv/bin/python -m pytest tests/test_tools_membership.py tests/test_analysis_mode_access.py -q`
- 靜態資源完整性掃描（主要入口頁）：
  - 檢查參考數：223
  - 缺失：0
- 前端頁面載入基線（本機 static + mock API，headless）：
  - `/static/index.html#chat`: DOMContentLoaded 約 3360ms
  - `/static/forum/index.html`: 約 317ms
  - `/static/scam-tracker/index.html`: 約 240ms
  - `/static/governance/index.html`: 約 56ms
  - `/static/legal/terms-of-service.html`: 約 231ms

## 本輪續作（穩定性常駐化）
- 新增 E2E 包裝測試，讓 non-Pi gate 進入正式 pytest/CI：
  - `tests/e2e/test_non_pi_browser_gate.py`
- 新增靜態資源完整性檢查腳本：
  - `scripts/check_static_refs.py`
  - 檢查所有 `web/**/*.html`（排除 `index.copy.html`）中的 `/static/*` 引用是否有實體檔案。
- 擴充一鍵穩定性腳本：
  - `scripts/run_verified_mode_checks.sh`
  - 現在會執行：Python syntax、前端 syntax、static refs、critical backend、E2E（含 non-Pi gate）。
- 更新 CI workflow：
  - `.github/workflows/test-suite.yml`
  - `python-tests` job 新增 static refs 檢查。
  - `e2e-tests` job 新增 `tests/e2e/test_non_pi_browser_gate.py`。
- 更新 README 驗證門檻說明（Verified Mode Quality Gate）。

## 本輪驗證（穩定性常駐化）
- `./.venv/bin/python -m pytest -o addopts='' tests/test_analysis_mode_access.py tests/test_analysis_policy.py tests/test_analysis_response_metadata.py tests/test_api_models.py tests/test_tool_access_resolver.py -q`
  - 結果：`54 passed`
- `./.venv/bin/python -m pytest -o addopts='' tests/e2e/test_non_pi_browser_gate.py tests/e2e/test_verified_mode_market_flow.py -q`
  - 結果：`4 passed`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（含 static refs `missing_refs=0`）

## 本輪續作（快取版本一致性 / 上線穩定）
- 依 `frontend-design` 全站一致性流程，補齊共享資源 `?v=` 漂移，降低「不同頁命中不同快取版本」風險。
- 主要調整：
  - `web/forum/*.html`、`web/scam-tracker/*.html`：補上 `styles.css?v=4`。
  - `web/forum/*.html`、`web/scam-tracker/*.html`、`web/index.html`：統一 `apiKeyManager.js?v=48`。
  - `web/forum/index.html`、`web/forum/dashboard.html`：統一 `nav-config.js?v=7`、`global-nav.js?v=2`。
  - `web/scam-tracker/*.html`：統一 `scam-tracker.js?v=48`，並同步 `app/auth/i18n` 到現行版本參數。
- 新增版本一致性檢查腳本：
  - `scripts/check_asset_versions.py`
  - 針對高影響共享檔（`styles/app/auth/premium/i18n/apiKeyManager/nav-config/global-nav/pi-auth/scam-tracker`）強制檢查版本。
- 一鍵檢查與 CI 擴充：
  - `scripts/run_verified_mode_checks.sh` 新增 `[4/6] Asset version consistency checks`。
  - `.github/workflows/test-suite.yml`（`python-tests` job）新增 `python scripts/check_asset_versions.py`。
  - `README.md` 的 Verified Mode Quality Gate 新增 version consistency 項目。

## 本輪驗證（快取版本一致性）
- `./.venv/bin/python scripts/check_asset_versions.py`
  - 結果：`checked_versioned_refs=65`, `version_mismatch=0`
- `python3 scripts/check_static_refs.py`
  - 結果：`checked_refs=223`, `missing_refs=0`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（`54 passed` + `4 passed`）
- Playwright static smoke（以 `/static` 路徑映射 `web/`，只統計靜態資源錯誤）：
  - 檢查頁面：11
  - `static_http_failures=0`
  - console 錯誤 3 筆皆為 `scam-tracker` 對 `/api/*` 的資料請求失敗（純靜態伺服器下預期行為，非靜態資源缺檔）。

## 本輪續作（E2E 靜態載入煙霧測試常駐化）
- 新增 Playwright 靜態資源載入煙霧測試（避免只靠一次性手動）：
  - `tests/e2e/test_static_asset_load_smoke.py`
- 測試重點：
  - 使用 `/static` 路徑映射 `web/` 的本地靜態伺服器。
  - 掃描 16 個主要頁面（主站、forum、scam-tracker、governance、legal）。
  - 將 `/api/*` 請求以 mock 200 JSON 回應，降低後端依賴；專注檢查靜態資源載入是否 4xx/5xx。
- 穩定鏈路整合：
  - `scripts/run_verified_mode_checks.sh`：E2E 階段新增 `tests/e2e/test_static_asset_load_smoke.py`。
  - `.github/workflows/test-suite.yml`：`e2e-tests` job 新增 `tests/e2e/test_static_asset_load_smoke.py`。
  - `README.md` Verified Mode Quality Gate 新增 `multi-page static asset load smoke checks`。

## 本輪驗證（E2E 靜態載入煙霧）
- `./.venv/bin/python -m pytest -o addopts='' tests/e2e/test_static_asset_load_smoke.py -q`
  - 結果：`1 passed`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（backend `54 passed`，E2E `5 passed`）

## 本輪續作（剩餘版本漂移收斂）
- 持續做全站 script version 漂移掃描，補齊剩餘共享資源不一致：
  - `LanguageSwitcher.js` 統一為 `v=3`
  - `friends.js` 統一為 `v=5`
  - `messages.js` 統一為 `v=5`
- 涉及頁面：
  - `web/index.html`
  - `web/forum/index.html`
  - `web/forum/dashboard.html`
  - `web/forum/profile.html`
  - `web/forum/messages.html`
- 版本一致性規則擴充：
  - `scripts/check_asset_versions.py` 新增上述三個共享資源的強制版本檢查。
  - `checked_versioned_refs` 從 `65` 提升為 `73`（覆蓋更完整）。

## 本輪驗證（剩餘版本漂移收斂）
- `./.venv/bin/python scripts/check_asset_versions.py`
  - 結果：`checked_versioned_refs=73`, `version_mismatch=0`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（backend `54 passed`，E2E `5 passed`）

## 本輪續作（前端 runtime 例外防護）
- 強化 `tests/e2e/test_static_asset_load_smoke.py`：
  - 由「只檢查靜態資源 4xx/5xx」升級為同時檢查 `pageerror`（未捕捉前端例外）。
  - 補齊常見 `/api/*` stub 回傳結構，降低假性錯誤，聚焦真實前端執行期問題。
- 新增過程中抓到並修復 2 個真實例外：
  - `web/js/messages_page.js`
    - 問題：`limits.message_limit` 缺失時直接讀 `.used/.limit` 造成 `Cannot read properties of undefined (reading 'used')`。
    - 修正：新增 `messageLimit` 防呆，改為安全存取。
  - `web/scam-tracker/js/scam-tracker.js`
    - 問題：直接呼叫全域 `getCurrentUser()`，在部分頁面初始化時未定義。
    - 修正：新增 `resolveScamTrackerCurrentUser()`，依序 fallback `getCurrentUser` / `AuthManager.currentUser` / `localStorage.pi_user`。
- 一鍵語法檢查擴充：
  - `scripts/run_verified_mode_checks.sh` 新增：
    - `node --check web/js/messages_page.js`
    - `node --check web/scam-tracker/js/scam-tracker.js`

## 本輪驗證（前端 runtime 例外防護）
- `./.venv/bin/python -m pytest -o addopts='' tests/e2e/test_static_asset_load_smoke.py -q`
  - 結果：`1 passed`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（backend `54 passed`，E2E `5 passed`）

## 本輪續作（console error 監控收斂）
- 將 `tests/e2e/test_static_asset_load_smoke.py` 再升級：
  - 新增本地靜態腳本來源 `console.error` 監控（不只抓 `pageerror`）。
  - 初次升級時抓到 3 類問題：
    - 靜態測試環境下 `WebSocket` 404 噪音（`notification-service.js`、`messages.js`）。
    - `forum/post` 詳情 stub 結構不足，導致 `post.title` 讀取錯誤。
    - `scam-tracker/detail` stub 結構不足，導致 `verification_status` 讀取錯誤。
- 修正方式：
  - 在 smoke 測試中注入 `SmokeWebSocket`，避免無 ws 伺服器時產生假性錯誤。
  - 補齊 `/api/forum/posts/{id}` 與 `/api/scam-tracker/reports/{id}` 的回傳結構，對齊前端實際讀取欄位。

## 本輪驗證（console error 監控收斂）
- `./.venv/bin/python -m pytest -o addopts='' tests/e2e/test_static_asset_load_smoke.py -q`
  - 結果：`1 passed`
- `bash scripts/run_verified_mode_checks.sh`
  - 結果：全綠（backend `54 passed`，E2E `5 passed`）

## Skill 狀態
- 已安裝：`~/.codex/skills/frontend-design/SKILL.md`
- 若要新會話自動吃到新 skill，需重啟 Codex。

## 本輪續作（Pod 磁碟壓力治理 / 上線穩定）
- 問題背景：
  - Pod 曾因 `ephemeral-storage` 壓力被驅逐，重點在「容器可寫層 + stdout 日誌量 + runtime 檔案成長」。
- 調整項目：
  - `api/utils.py`
    - logger 預設改為 `APP_LOG_LEVEL`（預設 `WARNING`），避免預設 `INFO` 長期累積高頻訊息。
  - `api_server.py`
    - 全域 logging level 改由 `APP_LOG_LEVEL` 控制（預設 `WARNING`），console handler 與 `basicConfig` 一致。
  - `core/security_monitor.py`
    - `security_events.jsonl` 加入大小輪替：
      - `SECURITY_EVENTS_MAX_BYTES`（預設 10MB）
      - `SECURITY_EVENTS_BACKUP_COUNT`（預設 3）
    - 超過上限自動輪替為 `.1/.2/.3`，避免無上限成長。
  - `Dockerfile`
    - Gunicorn 啟動參數移除預設 access log，並將 log level 預設為 `warning`。
  - `gunicorn.conf.py`
    - access log 預設關閉（`GUNICORN_ACCESSLOG` 才開啟）。
    - `loglevel` 可由 `GUNICORN_LOG_LEVEL` 控制，預設 `warning`。
  - `.dockerignore`
    - 新增 runtime 檔案排除：`core/database/*.db|*.sqlite*`、`data/*.jsonl`、`tmp/`。
- 驗證結果：
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile api/utils.py api_server.py core/security_monitor.py gunicorn.conf.py`：PASS
  - `./.venv/bin/python -m pytest -o addopts='' tests/security/test_security_hardening.py -q`：`18 passed, 4 skipped`
  - `bash scripts/run_verified_mode_checks.sh`：全綠（backend `54 passed`，E2E `5 passed`）
- 備註：
  - 這批修正可明顯降低日誌造成的磁碟壓力，但「100% 不會再驅逐」仍取決於實際流量、平台配額與其他 sidecar/節點共用壓力；建議上線後持續監控 `ephemeral-storage` 使用率與事件告警。
