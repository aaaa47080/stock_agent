# scraper_cdc_search.py

import requests
from bs4 import BeautifulSoup
import urllib.parse
import trafilatura
import re
from pathlib import Path
import sys# 添加父目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

def search_cdc_keywords(keyword, k_value: int = 3):
    """
    Search for keywords on Taiwan CDC website using advanced search and return results list.
    :param keyword: User input search keyword
    :param k_value: Number of results to return (default: 3)
    :return: List of dictionaries containing title, link, date, and summary
    """
    session = requests.Session()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Referer': 'https://www.cdc.gov.tw/Search',
        'Origin': 'https://www.cdc.gov.tw',
        'Accept': 'text/html, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'X-Requested-With': 'XMLHttpRequest',
    }

    # Step 1: Get CSRF token
    initial_url = "https://www.cdc.gov.tw/Search"  # ✅ 移除末尾空格
    try:
        response = session.get(initial_url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[CDC Search] Failed to load search page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    token_input = soup.find('input', {'name': '__RequestVerificationToken'})
    if not token_input or not token_input.get('value'):
        print("[CDC Search] CSRF token not found.")
        return []
    
    csrf_token = token_input['value']
    print(f"[CDC Search] Got CSRF token: {csrf_token[:20]}...")

    # Step 2: Submit search
    search_url = "https://www.cdc.gov.tw/Search/AdvanceSearch"  # ✅ 移除空格
    payload = {
        '__RequestVerificationToken': csrf_token,
        'Keyword': keyword,
        'TotalWord': '',
        'SDate': '',
        'EDate': '',
        'Propaganda': ''
    }

    try:
        search_response = session.post(search_url, data=payload, headers=headers, timeout=15)
        search_response.raise_for_status()
    except requests.RequestException as e:
        print(f"[CDC Search] Search request failed: {e}")
        return []

    search_soup = BeautifulSoup(search_response.text, 'html.parser')
    result_items = search_soup.find_all('div', class_='cbp-item identity')[:k_value]
    print(f"[CDC Search] Found {len(result_items)} results for '{keyword}'.")

    results = []
    for item in result_items:
        title_tag = item.find('h2', class_='search_results_title')
        link_tag = item.find('a')
        desc_tag = item.find('p', class_='search_results_text')
        year_tag = item.find('p', class_='icon-year')
        date_tag = item.find('p', class_='icon-date')

        title = title_tag.get_text(strip=True) if title_tag else 'N/A'
        link = urllib.parse.urljoin("https://www.cdc.gov.tw", link_tag['href']) if link_tag and link_tag.get('href') else 'N/A'  # ✅ 修正 base URL
        summary = desc_tag.get_text(strip=True) if desc_tag else 'N/A'
        
        # 安全組合日期
        year = year_tag.get_text(strip=True) if year_tag else ''
        day = date_tag.get_text(strip=True) if date_tag else ''
        date_str = f"{year}-{day}" if year or day else 'N/A'
        # 清理多餘空白或重複分隔符
        date_str = re.sub(r'-+', '-', date_str).strip('-')

        results.append({
            'title': title,
            'link': link,
            'summary': summary,
            'date': date_str
        })

    return results


def get_article_content_with_trafilatura(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"[trafilatura] Unable to fetch content: {e}"

    extracted = trafilatura.extract(
        response.text,
        include_comments=False,
        include_tables=True,
        favor_precision=True
    )
    if extracted and len(extracted.strip()) > 50:
        return extracted.strip()
    return None


def get_article_content_fallback(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"[fallback] Unable to fetch content: {e}"

    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove noisy elements
    for tag in soup(['footer', 'nav', 'script', 'style']):
        tag.decompose()

    # Strategy 1: Main content container
    container = soup.find('div', id='ContentFirstLink')
    if container:
        text = container.get_text(separator='\n', strip=True)
        if len(text) > 50:
            return clean_invalid_content(text)

    # Strategy 2: Heading + siblings
    heading = soup.find(['h1', 'h2', 'h3'], string=lambda t: t and len(t.strip()) > 5)
    if heading:
        parts = [heading.get_text(strip=True)]
        current = heading
        for _ in range(50):  # limit loop
            current = current.find_next_sibling()
            if not current:
                break
            if current.name in ['p', 'ul', 'ol', 'div'] and len(current.get_text(strip=True)) > 10:
                parts.append(current.get_text(strip=True))
            if len(' '.join(parts)) > 3000:
                break
        if len(parts) > 1:
            return '\n'.join(parts)

    return "[Fallback] No valid content found."


def clean_invalid_content(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) > 10 and not stripped.startswith(('©', '版權所有', '更新日期', '瀏覽人次')):
            lines.append(stripped)
    return '\n'.join(lines)


def scrape_disease_description(disease_name: str) -> str:
    """
    Main entry point for CDC disease info scraping.
    Returns combined content from top search results.
    """
    print(f"[CDC Scraper] Searching for disease: {disease_name}")
    results = search_cdc_keywords(disease_name, k_value=2)  # 取前 2 筆更穩健
    
    if not results:
        return "（CDC 無相關搜尋結果）"

    all_content = []
    for i, res in enumerate(results):
        print(f"  → Fetching result {i+1}: {res['title']}")
        content = get_article_content(res['link'])
        if content and not content.startswith(("[Fallback]", "[trafilatura]")):
            all_content.append(f"【來源 {i+1}：{res['title']}】\n{content}\n\n")

    if not all_content:
        return "（CDC 搜尋成功但內容提取失敗）"
    
    return "\n".join(all_content).strip()


def get_article_content(article_url: str) -> str:
    """
    Unified content extraction: try trafilatura first, then fallback.
    Always returns a string.
    """
    print(f"    [Fetching: {article_url}]")
    content = get_article_content_with_trafilatura(article_url)
    if content:
        return content
    else:
        return get_article_content_fallback(article_url)


# --- Usage Example (for testing only) ---
if __name__ == "__main__":
    user_input = input("Please enter search keyword: ").strip()
    if user_input:
        results = search_cdc_keywords(user_input, k_value=2)
        for r in results:
            print(f"\nTitle: {r['title']}\nLink: {r['link']}\nDate: {r['date']}\nSummary: {r['summary'][:100]}...")
            content = get_article_content(r['link'])
            print(f"Content preview: {content[:200]}...")