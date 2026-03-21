from playwright.sync_api import sync_playwright


def fetch_medium_article(url):
    """使用 Playwright无头模式获取 Medium 文章页面内容"""
    with sync_playwright() as p:
        # 启动浏览器（无头模式）
        browser = p.chromium.launch(headless=True)
        
        # 创建浏览器上下文
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # # 添加 cookies
        # cookies = [
        #     {"name": "g_state", "value": "{\"i_l\":0,\"i_ll\":1768707205376}", "domain": ".medium.com", "path": "/"},
        #     {"name": "nonce", "value": "x6to5uzy", "domain": ".medium.com", "path": "/"},
        #     {"name": "uid", "value": "852bc158312f", "domain": ".medium.com", "path": "/"},
        #     {"name": "sid", "value": "1:A1eoX2iWsTsBxsyjOnNzmB5M4fBIexkuBsuzUkjCyE/cdC53B/31UnMxw8C2uWcv", "domain": ".medium.com", "path": "/"},
        #     {"name": "_ga", "value": "GA1.1.124414990.1768707205", "domain": ".medium.com", "path": "/"},
        #     {"name": "xsrf", "value": "d97b050e487f", "domain": ".medium.com", "path": "/"},
        #     {"name": "_cfuvid", "value": "OXpPKaxgLD1xyT7CQnqDK6K9tkdAJyFu7mCaniijSHU-1773542209524-0.0.1.1-604800000", "domain": ".medium.com", "path": "/"},
        #     {"name": "cf_clearance", "value": "P9biODbSgZ8BC0117LNp5YFLzxYB89uHHYLQC_uzf28-1773542210-1.2.1.1-g7RiQuzk_qWFqEd5TW68siHQxxjs5JY1ulK.J3sm7o3_Ib9umHbMzwmXDjDEfCRlRe3gCJgODxv1.8bqnu5FrZT6yq5L4ECOthfN2njDpONaV7fnu77BuvdhbOlFN9yLmzsd3isX3FOuG36XmzeMATXpcY77Y6SDeYyDBIFzmNk4wYa2NE8P7T8HgDYvNyted6CYKqV5RcMsVuUHc28HRtqpAwL6V4ggEaz8F69mBbM", "domain": ".medium.com", "path": "/"},
        #     {"name": "_ga_7JY7T788PK", "value": "GS2.1.s1773542210$o14$g1$t1773542288$j53$l0$h0", "domain": ".medium.com", "path": "/"},
        #     {"name": "_dd_s", "value": "rum=0&expire=1773543209360", "domain": ".medium.com", "path": "/"}
        # ]
        # context.add_cookies(cookies)
        
        # 创建新页面
        page = context.new_page()
        
        try:
            # 访问页面并等待加载
            page.goto(url, wait_until="networkidle")
            
            # 等待页面完全加载
            page.wait_for_timeout(2000)
            
            # 获取页面内容
            content = page.content()
            
            return content
            
        except Exception as e:
            print(f"Error fetching page: {e}")
            return None
        finally:
            browser.close()


if __name__ == "__main__":
    url = "https://medium.com/@munchieblak/a-i-and-the-demonic-966c7ee904de"
    content = fetch_medium_article(url)
    
    if content:
        print(content)
        print("\n" + "="*50)
        print("Page fetched successfully!")
