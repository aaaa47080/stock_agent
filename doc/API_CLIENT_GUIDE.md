# 醫療諮詢系統 API 使用指南

## API 位址

```
http://172.23.37.2:8100
```

## 可用資料庫

| 資料源 ID | 名稱 | 內容說明 |
|-----------|------|----------|
| `medical_kb_jsonl` | 醫療知識庫(JSONL) | 核心問答庫，包含感染控制、傳染病處理指引。支援動態 PDF 關聯檢索。 |
| `public_health` | 衛教園地 | 醫院官方衛教單張內容，涵蓋慢性病管理、用藥指導、檢查流程等。 |
| `dialysis_education` | 洗腎衛教專區 | 針對血液透析、腹膜透析患者的專業照護指引與營養建議（含表格）。 |
| `educational_images` | 衛教圖片檢索 | 檢索相關的視覺化衛教圖片，提供步驟圖示或症狀對照。 |

## 安裝

```bash
pip install requests
```

## 執行範例

```bash
python example_infection.py    # 感染科
python example_dialysis.py     # 洗腎衛教
python example_health_edu.py   # 衛教
```
