import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import sys
import urllib.parse

def search_google_news(keyword: str, timeframe: str = "24h", limit: int = 10, region: str = "TW"):
    """
    自定義 Google News 查詢測試
    
    參數:
    - keyword: 關鍵字
    - timeframe: 時間範圍 (1h, 24h, 7d)
    - limit: 顯示筆數
    - region: 地區 ("TW" 為台灣中文, "US" 為美國英文)
    """
    
    # 根據地區設定參數
    if region.upper() == "TW":
        hl, gl, ceid = "zh-TW", "TW", "TW:zh-hant"
        region_name = "台灣/繁體中文"
    else:
        hl, gl, ceid = "en-US", "US", "US:en"
        region_name = "美國/英文"

    print(f"\n🔍 正在搜尋 Google News ({region_name}): [{keyword}] (時間範圍: {timeframe})...")
    
    # 對關鍵字進行 URL 編碼
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:{timeframe}&hl={hl}&gl={gl}&ceid={ceid}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        news_items = root.findall('.//item')
        print(f"✅ 找到 {len(news_items)} 條新聞 (顯示前 {limit} 條):\n")
        
        for i, item in enumerate(news_items[:limit], 1):
            title = item.find('title').text if item.find('title') is not None else "No Title"
            link = item.find('link').text if item.find('link') is not None else "No Link"
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else "N/A"
            source = item.find('source').text if item.find('source') is not None else "Unknown"
            
            print(f"{i}. [{source}] {title}")
            print(f"   📅 發佈時間: {pub_date}")
            print(f"   🔗 連結: {link}")
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ 搜尋失敗: {str(e)}")

if __name__ == "__main__":
    # 使用方式: python test_google_news.py <關鍵字> <地區: TW/US>
    target = "登革熱"
    region = "TW"
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
    if len(sys.argv) > 2:
        region = sys.argv[2]
    
    search_google_news(target, timeframe="5d", limit=10, region=region)