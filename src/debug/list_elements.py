"""
一覧ページの section#job-list 配下のリンク構造と全要素を
debug/list_links.csv・debug/list_elements.csv に書き出すデバッグスクリプト。
実行: python src/debug/list_elements.py
環境変数 DEBUG_URL で対象URLを上書き可能。
"""
import csv
import os
import time

from selenium.webdriver.common.by import By

from scraper.driver import create_driver

TARGET_URL = os.getenv(
    "DEBUG_URL",
    "https://freelance-start.com/jobs?page=1&keyword=データエンジニア&prefecture=13",
)
LINKS_CSV = "/app/output/debug/list_links.csv"
ELEMENTS_CSV = "/app/output/debug/list_elements.csv"


def main() -> None:
    driver = create_driver()
    try:
        print(f"アクセス中: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)

        os.makedirs("/app/output/debug", exist_ok=True)
        _dump_links(driver)
        _dump_elements(driver)
    finally:
        driver.quit()


def _dump_links(driver) -> None:
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/detail/']")
    rows = []
    for a in links:
        ancestors: list[str] = driver.execute_script("""
            const out = [];
            let el = arguments[0].parentElement;
            for (let i = 0; i < 5 && el; i++) {
                const id = el.id ? '#' + el.id : '';
                const cls = el.className ? '.' + [...el.classList].join('.') : '';
                out.push(el.tagName.toLowerCase() + id + cls);
                el = el.parentElement;
            }
            return out;
        """, a)
        rows.append({
            "href": a.get_attribute("href") or "",
            "text": a.text.strip()[:80],
            **{f"parent{i + 1}": ancestors[i] if i < len(ancestors) else "" for i in range(5)},
        })

    with open(LINKS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["href", "text", "parent1", "parent2", "parent3", "parent4", "parent5"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} 件のリンクを出力しました: {LINKS_CSV}")


def _dump_elements(driver) -> None:
    sections = driver.find_elements(By.CSS_SELECTOR, "section#job-list")
    if not sections:
        print("section#job-list が見つかりませんでした")
        return

    elements = sections[0].find_elements(By.XPATH, ".//*[normalize-space(text())]")
    rows = [
        {
            "tag": el.tag_name,
            "class": el.get_attribute("class") or "",
            "id": el.get_attribute("id") or "",
            "text": el.text.strip()[:200],
        }
        for el in elements
        if el.text.strip()
    ]

    with open(ELEMENTS_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["tag", "class", "id", "text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} 件の要素を出力しました: {ELEMENTS_CSV}")


if __name__ == "__main__":
    main()
