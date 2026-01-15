import requests
from bs4 import BeautifulSoup
from pathlib import Path
import sys# 添加父目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))
from core.config import taiwan_infectious_diseases


def get_disease_name(disease_name):
    try:
        content = taiwan_infectious_diseases.get(disease_name)
        return content
    except Exception as e:
        print(e)
        return ""

def scrape_disease_description(disease_name):
    """
    通用函數：根據傳入的疾病頁面 URL，抓取並返回其描述文字。
    適用於百日咳、屈公病等所有疾病頁面。
    """
    # 設定 User-Agent，模擬瀏覽器請求
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    }


    try:
        url = get_disease_name(disease_name=disease_name)
        # 發送 GET 請求到網站
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 檢查 HTTP 錯誤
        response.encoding = 'utf-8'   # 設定正確的編碼

        # 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 定位到包含疾病描述的 <div class="infectiousCon">
        infectious_con_div = soup.find('div', class_='infectiousCon')

        if infectious_con_div:
            # 方法：提取該 div 內「所有」文字，並智能清理
            # 1. 獲取所有文字，用空格連接換行
            raw_text = infectious_con_div.get_text(separator=' ', strip=False)
            # 2. 移除多餘空白（包括 &nbsp; 造成的）
            clean_text = ' '.join(raw_text.split())
            # 3. 返回乾淨文字
            return clean_text + f"參考資料來源：臺灣衛生福利部疾病管制署：{url}"
        else:
            return "錯誤：未找到 class='infectiousCon' 的區塊。"

    except requests.exceptions.RequestException as e:
        return f"網路請求錯誤：{e}"
    except Exception as e:
        return f"解析或處理錯誤：{e}"


# ===== 使用範例 =====
if __name__ == "__main__":
    # disease_url = get_disease_name("屈公病")
    print(scrape_disease_description("新冠併發重症"))
    # for name, url_pertussis in taiwan_infectious_diseases.items():
    #     content = scrape_disease_description(url_pertussis)
    #     if content:
    #         pass
    #     else:
    #        print(name)
    #        print("Not found")
           

    # 測試百日咳
    # url_pertussis = "https://www.cdc.gov.tw/Disease/SubIndex/gJ7r9uf6cgWWczRSeMRibA"
    # print("=== 百日咳描述內容 ===")
    # print(scrape_disease_description(url_pertussis))
    # print("\n" + "="*50 + "\n")

    # # 測試屈公病
    # url_chikungunya = "https://www.cdc.gov.tw/Disease/SubIndex/NvKXcB74Wh3-1vGaYMigDw"
    # print("=== 屈公病描述內容 ===")
    # print(scrape_disease_description(url_chikungunya))