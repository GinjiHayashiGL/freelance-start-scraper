"""
重複案件の確認用デバッグスクリプト。
重複除去を行わずに全URLを収集し、keyword・ページ番号・URLを記録する。
実行: python src/debug/duplicates.py

環境変数 (省略時はデフォルト値):
  KEYWORDS    カンマ区切りキーワード (例: "データエンジニア,AWS")
  PREFECTURE  都道府県コード (デフォルト: 13)
  MAX_PAGES   1キーワードあたりの上限ページ数 (デフォルト: 3)
"""
import csv
import os
import re
import time
import random
from collections import Counter
from urllib.parse import urlparse, urlunparse

from scraper.driver import create_driver

BASE_URL = os.getenv("BASE_URL", "https://freelance-start.com")
KEYWORDS_RAW = os.getenv("KEYWORDS", "データエンジニア,AWS")
PREFECTURE = os.getenv("PREFECTURE", "13")
MAX_PAGES = int(os.getenv("MAX_PAGES", "3"))
OUTPUT_PATH = "/app/output/debug/duplicates.csv"


def main() -> None:
    keywords = [k.strip() for k in KEYWORDS_RAW.split(",") if k.strip()]
    driver = create_driver()
    try:
        rows: list[dict] = []

        for keyword in keywords:
            print(f"\nキーワード「{keyword}」の収集開始 (最大 {MAX_PAGES} ページ)")
            driver.get(f"{BASE_URL}/jobs?keyword={keyword}&page=1&prefecture={PREFECTURE}")
            time.sleep(random.uniform(2, 4))

            build_page_url = _resolve_page_url_builder(driver, keyword)

            for page in range(1, MAX_PAGES + 1):
                if page > 1:
                    driver.get(build_page_url(page))
                    time.sleep(random.uniform(2, 4))

                print(f"  ページ {page}: {driver.current_url}")
                card_links: list[str] = driver.execute_script("""
                    const cards = document.querySelectorAll(
                        'section#job-list div.row.my-4 h3.card-head'
                    );
                    const results = [];
                    for (const h3 of cards) {
                        const a = h3.closest('a[href*="/jobs/detail/"]');
                        if (a) results.push(a.href);
                    }
                    return results;
                """)

                for href in card_links:
                    normalized = _normalize_url(href)
                    if re.search(r"/jobs/detail/\d+", normalized):
                        rows.append({"keyword": keyword, "page": page, "url": normalized})

                print(f"    → {len(card_links)} 件収集")

        _write_csv_with_duplicate_flag(rows)
        _print_summary(rows)
    finally:
        driver.quit()


def _resolve_page_url_builder(driver, keyword: str):
    skill_match = re.search(r"/jobs/skill-(\d+)", driver.current_url)
    if skill_match:
        skill_id = skill_match.group(1)
        print(f"  スキルURLへのリダイレクトを検出 (skill={skill_id})、prefecture付きで再アクセス")
        driver.get(f"{BASE_URL}/jobs?skill={skill_id}&page=1&prefecture={PREFECTURE}")
        time.sleep(random.uniform(2, 4))
        return lambda page: f"{BASE_URL}/jobs?skill={skill_id}&page={page}&prefecture={PREFECTURE}"
    return lambda page: f"{BASE_URL}/jobs?keyword={keyword}&page={page}&prefecture={PREFECTURE}"


def _normalize_url(href: str) -> str:
    parsed = urlparse(href)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _write_csv_with_duplicate_flag(rows: list[dict]) -> None:
    seen: set[str] = set()
    for row in rows:
        row["is_duplicate"] = 0 if row["url"] not in seen else 1
        seen.add(row["url"])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "page", "url", "is_duplicate"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSVに出力しました: {OUTPUT_PATH}")


def _print_summary(rows: list[dict]) -> None:
    total = len(rows)
    duplicates = sum(1 for r in rows if r["is_duplicate"])
    url_counter: Counter = Counter(r["url"] for r in rows)

    print(f"\n===== 集計結果 =====")
    print(f"  収集総数     : {total}")
    print(f"  ユニークURL  : {total - duplicates}")
    print(f"  重複件数     : {duplicates}")
    top = [(u, c) for u, c in url_counter.most_common(10) if c > 1]
    if top:
        print(f"\n  重複が多いURL (上位10件):")
        for url, count in top:
            print(f"    {count}回 {url}")


if __name__ == "__main__":
    main()
