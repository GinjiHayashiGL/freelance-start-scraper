"""
詳細ページの全要素を debug/page_elements.csv に書き出すデバッグスクリプト。
実行: python src/debug/page_elements.py
環境変数 DEBUG_URL で対象URLを上書き可能。
"""
import csv
import os
import time

from selenium.webdriver.common.by import By

from scraper.driver import create_driver

TARGET_URL = os.getenv(
    "DEBUG_URL",
    "https://freelance-start.com/jobs/detail/1654622?from=search_result",
)
OUTPUT_PATH = "/app/output/debug/page_elements.csv"


def main() -> None:
    driver = create_driver()
    try:
        print(f"アクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)

        elements = driver.find_elements(By.XPATH, "//*[normalize-space(text())]")
        rows = [
            {"tag": el.tag_name, "class": el.get_attribute("class") or "", "text": el.text.strip()[:200]}
            for el in elements
            if el.text.strip()
        ]

        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["tag", "class", "text"])
            writer.writeheader()
            writer.writerows(rows)

        print(f"{len(rows)} 件の要素を出力しました: {OUTPUT_PATH}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
