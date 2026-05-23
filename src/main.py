import posixpath
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

url_jobs = "https://freelance-start.com/jobs"

map_skills = {
    "python": 3,
    "sql": 23,
    "aws": 29,
    "gcp": 236,
}

def main():
    # クエリパラメータを組み立てる
    target_url = f"{url_jobs}?page=1&skill={map_skills['python']}"

    with sync_playwright() as p:
        # headless=True でバックグラウンド実行（挙動を見たい場合は False にしてください）
        browser = p.chromium.launch(headless=True)
        
        # 一般ユーザー（ブラウザ）に見せかける設定
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP"
        )
        page = context.new_page()
        
        print(f"Accessing: {target_url}")
        page.goto(target_url)
        
        # 💡 タイムアウト対策：ネットワークの完全停止を待たず、HTMLの読み込み完了時点で次に進む
        page.wait_for_load_state("domcontentloaded")
        
        # WAFを突破した状態の完全なHTMLを取得
        html = page.content()
        print(html)
        
        # BeautifulSoupでパース
        soup = BeautifulSoup(html, "html.parser")
        
        print("\n--- 取得結果 ---")
        print("Page Title:", soup.title.text if soup.title else "No Title")
        
        # 💡 ここから下に、Soupを使ったスクレイピングロジック（案件タイトルの抽出など）を書いていきます
        # 例: print(soup.find("h1").text) など
        
        browser.close()

if __name__ == "__main__":
    main()