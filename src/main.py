import csv
import os
from datetime import datetime

from scraper.driver import create_driver
from scraper.list_page import get_all_urls_for_keyword
from utils.config import load_config


def main() -> None:
    cfg = load_config()

    if cfg.max_pages > 0:
        print(f"取得上限: {cfg.max_pages} ページ / キーワード")
    else:
        print("取得上限: なし（全ページ取得）")

    driver = create_driver()
    try:
        all_rows: list[dict] = []
        seen_urls: set[str] = set()

        for keyword in cfg.keywords:
            print(f"\nキーワード「{keyword}」の案件を取得中...")
            urls = get_all_urls_for_keyword(
                driver,
                cfg.base_url,
                keyword,
                cfg.prefecture,
                cfg.max_pages,
                cfg.request_delay_sec,
            )
            added = 0
            for url in urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_rows.append({"検索キーワード": keyword, "案件URL": url})
                    added += 1
            print(f"  → {len(urls)} 件取得、うち新規 {added} 件")

        print(f"\n合計 {len(all_rows)} 件の案件URLを取得しました")
        filepath = _write_csv(all_rows, os.path.join(cfg.output_dir, "urls"))
        print(f"ファイルに出力しました: {filepath}")

    finally:
        driver.quit()


def _write_csv(data: list[dict], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"job_urls_{timestamp}.csv")
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["検索キーワード", "案件URL"])
        writer.writeheader()
        writer.writerows(data)
    return filepath


if __name__ == "__main__":
    main()
