#!/usr/bin/env python3
"""
使用 Playwright 在 Google 上搜索
包含反偵測技術，避免被 CAPTCHA 封鎖

運行:
python google_search_playwright.py "您的搜索查詢"
"""

import asyncio
from playwright.async_api import async_playwright
import random

try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False


# 備用 User-Agent 列表（當 fake-useragent 不可用時使用）
FALLBACK_USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',

    # Chrome on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',

    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',

    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',

    # Safari on macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15',
]


def get_random_user_agent():
    """
    動態生成隨機 User-Agent
    優先使用 fake-useragent，失敗則使用備用列表
    """
    if FAKE_UA_AVAILABLE:
        try:
            ua = UserAgent()
            # 優先使用 Chrome，因為最常見
            return ua.chrome
        except Exception:
            # 如果 fake-useragent 失敗，使用備用列表
            pass

    # 使用備用列表
    return random.choice(FALLBACK_USER_AGENTS)


async def simulate_human_mouse_movement(page, duration_seconds=2):
    """
    模擬人類隨機滑鼠移動

    Args:
        page: Playwright page 對象
        duration_seconds: 移動持續時間（秒）
    """
    viewport = page.viewport_size
    if not viewport:
        viewport = {'width': 1920, 'height': 1080}

    num_moves = random.randint(3, 6)
    for _ in range(num_moves):
        # 隨機目標位置
        target_x = random.randint(100, viewport['width'] - 100)
        target_y = random.randint(100, viewport['height'] - 100)

        # 分多步移動
        steps = random.randint(5, 10)
        current_x = random.randint(0, viewport['width'])
        current_y = random.randint(0, viewport['height'])

        for i in range(steps):
            progress = (i + 1) / steps
            x = current_x + (target_x - current_x) * progress
            y = current_y + (target_y - current_y) * progress
            # 添加抖動
            x += random.uniform(-3, 3)
            y += random.uniform(-3, 3)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.02, 0.05))

        await asyncio.sleep(duration_seconds / num_moves)


async def simulate_page_scroll(page, scroll_times=3):
    """
    模擬人類滾動頁面

    Args:
        page: Playwright page 對象
        scroll_times: 滾動次數
    """
    print("📜 模擬頁面滾動...")

    for i in range(scroll_times):
        # 隨機滾動距離（300-800 像素）
        scroll_amount = random.randint(300, 800)

        # 使用 JavaScript 平滑滾動
        await page.evaluate(f"""
            window.scrollBy({{
                top: {scroll_amount},
                behavior: 'smooth'
            }});
        """)

        # 滾動後停留一下（模擬閱讀）
        await asyncio.sleep(random.uniform(1, 2.5))

        # 偶爾向上滾動一點（模擬重新查看）
        if random.random() < 0.3:  # 30% 機率
            scroll_back = random.randint(50, 150)
            await page.evaluate(f"""
                window.scrollBy({{
                    top: -{scroll_back},
                    behavior: 'smooth'
                }});
            """)
            await asyncio.sleep(random.uniform(0.5, 1))

    print("✓ 滾動完成")


class GoogleSearchWithPlaywright:
    """使用 Playwright 的 Google 搜索（加強反偵測）"""

    def __init__(self, headless: bool = True, show_browser: bool = False):
        """
        Args:
            headless: 是否無頭模式
            show_browser: 是否顯示瀏覽器（用於調試）
        """
        self.headless = headless if not show_browser else False

    async def search(self, query: str, max_results: int = 10):
        """
        在 Google 搜索並提取結果

        Args:
            query: 搜索查詢
            max_results: 最多返回幾個結果

        Returns:
            搜索結果列表
        """
        async with async_playwright() as p:
            # 啟動瀏覽器 - 加入反偵測參數
            browser = await p.chromium.launch(
                headless=True,  # 強制使用無頭模式（避免 X server 錯誤）
                args=[
                    '--disable-blink-features=AutomationControlled',  # 隱藏自動化特徵
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                ]
            )

            # 隨機選擇 User-Agent
            user_agent = get_random_user_agent()
            print(f"🎭 使用 User-Agent: {user_agent[:80]}...")

            # 創建上下文 - 模擬真實用戶
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='zh-TW',  # 台灣繁體中文
                timezone_id='Asia/Taipei',
                extra_http_headers={
                    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                }
            )

            page = await context.new_page()

            # 注入反偵測腳本
            await page.add_init_script("""
                // 隱藏 webdriver 屬性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // 模擬 chrome 對象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };

                // 覆蓋 permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // 覆蓋 plugins 長度
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // 覆蓋 languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-TW', 'zh', 'en-US', 'en']
                });
            """)

            try:
                print(f"\n🔍 正在 Google 搜索: {query}")
                print("=" * 80)

                # 1. 先訪問 Google 首頁（更像真實用戶）
                print("📱 訪問 Google 首頁...")
                await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(random.uniform(1, 2))

                # 2. 處理 Cookie 同意彈窗
                try:
                    # 嘗試點擊接受 Cookie 按鈕
                    accept_button = await page.query_selector('button:has-text("全部接受"), button:has-text("Accept all"), button:has-text("I agree")')
                    if accept_button:
                        await accept_button.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                        print("✓ 已接受 Cookie")
                except:
                    pass

                # 3. 找到搜索框並輸入查詢（模擬人類打字）
                print(f"⌨️  輸入查詢: {query}")
                search_box = await page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=10000)

                # 模擬滑鼠移動到搜索框（更真實）
                box_position = await search_box.bounding_box()
                if box_position:
                    # 從隨機起始位置移動到搜索框中心
                    start_x = random.randint(100, 500)
                    start_y = random.randint(100, 300)
                    target_x = box_position['x'] + box_position['width'] / 2
                    target_y = box_position['y'] + box_position['height'] / 2

                    # 分多步移動滑鼠（模擬人類曲線移動）
                    steps = random.randint(5, 10)
                    for i in range(steps):
                        progress = (i + 1) / steps
                        # 添加一些隨機抖動
                        jitter_x = random.uniform(-5, 5)
                        jitter_y = random.uniform(-5, 5)
                        current_x = start_x + (target_x - start_x) * progress + jitter_x
                        current_y = start_y + (target_y - start_y) * progress + jitter_y
                        await page.mouse.move(current_x, current_y)
                        await asyncio.sleep(random.uniform(0.01, 0.03))

                    print("🖱️  滑鼠移動到搜索框")

                # 點擊搜索框
                await search_box.click()
                await asyncio.sleep(random.uniform(0.3, 0.7))

                # 模擬打字（每個字符有延遲）
                for char in query:
                    await search_box.type(char, delay=random.uniform(50, 150))

                await asyncio.sleep(random.uniform(0.5, 1))

                # 嘗試點擊搜尋按鈕（更像真人）
                try:
                    # 尋找搜尋按鈕
                    search_button = await page.query_selector('input[type="submit"][name="btnK"], button[type="submit"]')
                    if search_button:
                        # 滑鼠移動到按鈕
                        button_position = await search_button.bounding_box()
                        if button_position:
                            button_x = button_position['x'] + button_position['width'] / 2
                            button_y = button_position['y'] + button_position['height'] / 2

                            # 從搜索框移動到按鈕
                            steps = random.randint(3, 6)
                            current_pos = await page.evaluate('() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })')
                            start_x = box_position['x'] + box_position['width'] / 2 if box_position else current_pos.get('x', 0)
                            start_y = box_position['y'] + box_position['height'] / 2 if box_position else current_pos.get('y', 0)

                            for i in range(steps):
                                progress = (i + 1) / steps
                                current_x = start_x + (button_x - start_x) * progress
                                current_y = start_y + (button_y - start_y) * progress
                                await page.mouse.move(current_x, current_y)
                                await asyncio.sleep(random.uniform(0.01, 0.03))

                        print("🖱️  點擊搜尋按鈕")
                        await search_button.click()
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                    else:
                        # 找不到按鈕，使用 Enter 鍵
                        print("⌨️  按下 Enter 鍵")
                        await search_box.press('Enter')
                except Exception:
                    # 如果出錯，回退到 Enter 鍵
                    print("⌨️  按下 Enter 鍵")
                    await search_box.press('Enter')

                # 4. 等待搜索結果加載
                print("⏳ 等待搜索結果...")
                print(f"🔍 提交後 URL: {page.url}")

                # 先等待 URL 變化（更可靠的等待策略）
                try:
                    # 等待 URL 包含 /search?q= （表示已跳轉到搜索結果頁）
                    for i in range(30):  # 最多等待 15 秒（每次 0.5 秒）
                        current_url = page.url
                        if '/search' in current_url and 'q=' in current_url:
                            print(f"✓ 已跳轉到搜索結果頁: {current_url}")
                            break
                        await asyncio.sleep(0.5)
                        if i % 4 == 0:  # 每 2 秒打印一次
                            print(f"   等待中... 當前 URL: {current_url[:80]}")
                    else:
                        # 超時仍未跳轉
                        print(f"⚠️ 警告: URL 未變化，仍在: {page.url}")
                        print("嘗試直接訪問搜索結果頁...")

                        # 方案B: 直接構造搜索 URL 並訪問
                        import urllib.parse
                        encoded_query = urllib.parse.quote(query)
                        search_url = f"https://www.google.com/search?q={encoded_query}&hl=zh-TW"
                        print(f"🔗 訪問: {search_url}")
                        await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
                        await asyncio.sleep(random.uniform(2, 3))

                    # 等待搜索結果出現（使用更靈活的選擇器）
                    # 嘗試多個可能的選擇器
                    selectors_to_try = [
                        'div#search',           # 舊版 Google
                        'div#rso',              # 搜索結果容器
                        'a:has(h3)',            # 包含 h3 的鏈接（搜索結果）
                        'div[data-hveid]',      # Google 搜索結果的 data 屬性
                    ]

                    result_found = False
                    for selector in selectors_to_try:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            print(f"✓ 找到搜索結果元素: {selector}")
                            result_found = True
                            break
                        except:
                            continue

                    if not result_found:
                        print("⚠️ 未找到預期的搜索結果選擇器，但繼續嘗試提取...")

                    await asyncio.sleep(random.uniform(2, 3))
                    print("✓ 搜索結果已加載\n")

                    # 模擬人類行為：隨機滑鼠移動
                    await simulate_human_mouse_movement(page, duration_seconds=1.5)

                    # 模擬人類行為：滾動頁面瀏覽
                    scroll_times = random.randint(2, 4)
                    await simulate_page_scroll(page, scroll_times=scroll_times)

                except Exception as e:
                    # 檢查是否遇到 CAPTCHA
                    current_url = page.url
                    print(f"\n❌ 等待搜索結果時出錯")
                    print(f"   當前 URL: {current_url}")
                    print(f"   錯誤: {str(e)}")

                    # 截圖保存（調試用）
                    try:
                        screenshot_path = "/tmp/google_search_debug.png"
                        await page.screenshot(path=screenshot_path)
                        print(f"   📸 已保存截圖: {screenshot_path}")
                    except:
                        pass

                    # 打印頁面部分內容
                    try:
                        page_text = await page.evaluate('() => document.body.innerText')
                        print(f"\n📄 頁面內容預覽:")
                        print(page_text[:500])
                    except:
                        pass

                    if 'sorry' in current_url or 'captcha' in current_url.lower():
                        print("\n❌ Google 偵測到自動化訪問，顯示 CAPTCHA")
                        print("\n💡 建議:")
                        print("   1. 設置 show_browser=True 查看實際情況")
                        print("   2. 使用 DuckDuckGo (更友善)")
                        print("   3. 增加延遲時間")

                    return []

                # 5. 提取搜索結果
                results = []
                print("📊 提取搜索結果:")
                print("=" * 80)

                # 嘗試多種選擇器策略來適應新版 Google
                all_links = []

                # 策略1: 找所有包含 h3 的連結
                links_h3 = await page.query_selector_all('a:has(h3)')
                if links_h3:
                    print(f"   策略1: 找到 {len(links_h3)} 個 a:has(h3) 鏈接")
                    all_links = links_h3

                # 策略2: 如果策略1失敗，嘗試找 h3 標籤內的鏈接
                if not all_links:
                    h3_elements = await page.query_selector_all('h3')
                    if h3_elements:
                        print(f"   策略2: 找到 {len(h3_elements)} 個 h3 元素")
                        for h3 in h3_elements:
                            # 找 h3 的父元素中的鏈接
                            parent_link = await h3.evaluate_handle('element => element.closest("a")')
                            if parent_link:
                                all_links.append(parent_link)

                # 策略3: 直接搜索所有看起來像搜索結果的鏈接
                if not all_links:
                    print("   策略3: 查找所有可能的搜索結果鏈接...")
                    all_hrefs = await page.query_selector_all('a[href^="http"]')
                    print(f"   找到 {len(all_hrefs)} 個外部鏈接")
                    # 過濾掉 Google 內部鏈接
                    for link in all_hrefs:
                        href = await link.get_attribute('href')
                        if href and 'google.com' not in href:
                            all_links.append(link)
                    print(f"   過濾後剩餘 {len(all_links)} 個非 Google 鏈接")

                print(f"\n✓ 準備提取 {min(len(all_links), max_results)} 個結果")

                for link in all_links[:max_results * 2]:  # 多取一些，因為可能有過濾
                    try:
                        # 模擬滑鼠懸停在結果上（像真人查看結果）
                        try:
                            link_box = await link.bounding_box()
                            if link_box:
                                hover_x = link_box['x'] + link_box['width'] / 2
                                hover_y = link_box['y'] + 20  # 稍微偏上一點

                                # 移動滑鼠到結果上
                                await page.mouse.move(hover_x, hover_y)
                                await asyncio.sleep(random.uniform(0.3, 0.8))  # 停留一下
                        except:
                            pass

                        # 獲取 URL
                        url = await link.get_attribute('href')

                        # 過濾 Google 內部鏈接
                        if not url or not url.startswith('http') or 'google.com' in url:
                            continue

                        # 獲取標題
                        h3 = await link.query_selector('h3')
                        if not h3:
                            continue

                        title = await h3.text_content()

                        # 嘗試獲取描述（在父元素中查找）
                        description = ""
                        try:
                            # 找到包含這個連結的父容器
                            parent = await link.evaluate_handle('element => element.closest("div[data-sokoban-container], div.g")')
                            if parent:
                                # 在父容器中查找描述文本
                                desc_texts = await parent.query_selector_all('div[data-sncf], div.VwiC3b, span')
                                for desc in desc_texts:
                                    text = await desc.text_content()
                                    # 找最長的非標題文本
                                    if text and len(text) > len(description) and text != title:
                                        description = text
                        except:
                            pass

                        result = {
                            'rank': len(results) + 1,
                            'title': title.strip(),
                            'url': url,
                            'description': description.strip() if description else ""
                        }

                        results.append(result)

                        # 顯示結果
                        print(f"\n{len(results)}. 📄 {result['title']}")
                        print(f"   🔗 {result['url']}")
                        if result['description']:
                            print(f"   📝 {result['description'][:150]}...")

                    except Exception as e:
                        continue

                if not results:
                    print("\n⚠️  未能提取到結果")
                    print("可能原因:")
                    print("  - Google 改變了 HTML 結構")
                    print("  - 被 CAPTCHA 封鎖")
                    print("\n💡 嘗試查看頁面內容:")

                    # 顯示部分頁面文本以供調試
                    page_text = await page.evaluate('() => document.body.innerText')
                    print(page_text[:500])

                print(f"\n✓ 成功提取 {len(results)} 個結果")
                return results

            except Exception as e:
                print(f"\n❌ 搜索失敗: {str(e)}")
                print(f"   當前 URL: {page.url}")
                return []

            finally:
                await browser.close()

    async def search_and_visit_first(self, query: str):
        """
        搜索並訪問第一個結果

        Args:
            query: 搜索查詢

        Returns:
            第一個結果的內容
        """
        # 先執行搜索
        results = await self.search(query, max_results=1)

        if not results:
            return None

        first_result = results[0]

        print(f"\n📥 正在訪問: {first_result['title']}")
        print("=" * 80)

        # 訪問第一個結果
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # 強制使用無頭模式
            page = await browser.new_page()

            try:
                await page.goto(first_result['url'], wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)

                # 獲取內容
                title = await page.title()
                content = await page.evaluate('() => document.body.innerText')

                # print(f"✓ 頁面標題: {title}\n")
                # print("=" * 80)
                # print("📄 內容預覽:")
                # print("=" * 80)
                # print(content[:2000])
                # print("\n... (更多內容) ...\n")

                return {
                    **first_result,
                    'page_title': title,
                    'content': content
                }

            except Exception as e:
                print(f"❌ 訪問失敗: {e}")
                return first_result

            finally:
                await browser.close()


# ============================================================================
# 命令行界面
# ============================================================================

async def main():
    """主函數"""
    import sys

    print("\n" + "=" * 80)
    print("🔍 Google 搜索工具 (Playwright)")
    print("=" * 80)

    # 檢查命令行參數
    if len(sys.argv) > 1:
        # 命令行模式：直接執行，不詢問
        query = ' '.join(sys.argv[1:])
        print(f"\n查詢: {query}")

        # 默認參數
        show_browser = False
        max_results = 10

        # 創建搜索器並執行
        searcher = GoogleSearchWithPlaywright(show_browser=show_browser)
        await searcher.search(query, max_results)

    else:
        # 互動模式：詢問用戶
        query = input("\n請輸入搜索查詢: ").strip()

        if not query:
            print("❌ 查詢不能為空")
            return

        # 詢問是否顯示瀏覽器
        show = input("\n是否顯示瀏覽器？(y/n，默認 n): ").strip().lower()
        show_browser = show == 'y'

        # 詢問搜索模式
        print("\n選擇模式:")
        print("  1. 只獲取搜索結果列表（快）")
        print("  2. 搜索並訪問第一個結果（慢）")

        mode = input("\n選擇 (1 或 2，默認 1): ").strip()

        # 創建搜索器
        searcher = GoogleSearchWithPlaywright(show_browser=show_browser)

        # 執行搜索
        if mode == '2':
            await searcher.search_and_visit_first(query)
        else:
            num = input("\n需要幾個結果？(默認 10): ").strip()
            max_results = int(num) if num.isdigit() else 10
            await searcher.search(query, max_results)


if __name__ == "__main__":
    asyncio.run(main())
