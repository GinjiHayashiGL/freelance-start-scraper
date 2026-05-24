import re
import time
import random
from collections.abc import Callable
from urllib.parse import urlparse, urlunparse

from selenium import webdriver
from selenium.webdriver.common.by import By


def get_all_urls_for_keyword(
    driver: webdriver.Remote,
    base_url: str,
    keyword: str,
    prefecture: str = "13",
    max_pages: int = 0,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> list[str]:
    """指定キーワードの案件詳細URLを収集する。

    max_pages:   取得上限ページ数。0 はページネーションから自動検出した全ページ取得。
    delay_range: リクエスト間の待機秒数 (min, max)。
    """
    urls: list[str] = []
    seen: set[str] = set()

    # ページ1にアクセスしてスキルURLへのリダイレクトを検出する。
    # リダイレクトがあれば skill パラメータ＋prefecture で再アクセスする。
    initial_url = f"{base_url}/jobs?keyword={keyword}&page=1&prefecture={prefecture}"
    print(f"  ページ 1 を取得中: {initial_url}")
    driver.get(initial_url)
    time.sleep(random.uniform(*delay_range))

    build_page_url = _resolve_page_url_builder(driver, base_url, keyword, prefecture, delay_range)

    detected_max = _detect_max_page(driver)
    total_pages = max_pages if max_pages > 0 else detected_max

    if detected_max == 0:
        print("  案件が見つかりませんでした（ページネーションなし・リンクなし）")
        return []

    print(f"  検出ページ数: {detected_max}、取得対象: {total_pages} ページ")

    for page in range(1, total_pages + 1):
        if page > 1:
            page_url = build_page_url(page)
            print(f"  ページ {page} を取得中: {page_url}")
            driver.get(page_url)
            time.sleep(random.uniform(*delay_range))

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

        new_urls = []
        for href in card_links:
            normalized = _normalize_url(href)
            if re.search(r"/jobs/detail/\d+", normalized) and normalized not in seen:
                seen.add(normalized)
                new_urls.append(normalized)

        urls.extend(new_urls)
        print(f"    → {len(new_urls)} 件取得（累計 {len(urls)} 件）")

    return urls


def _resolve_page_url_builder(
    driver: webdriver.Remote,
    base_url: str,
    keyword: str,
    prefecture: str,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> Callable[[int], str]:
    """現在のURLを確認してリダイレクト有無を判定し、ページURLビルダーを返す。

    /jobs/skill-{id} へのリダイレクトを検出した場合は skill パラメータ＋
    prefecture で再アクセスし、以降のページにも同じ形式を使う。
    リダイレクトがない場合は keyword パラメータ形式をそのまま使う。
    """
    skill_match = re.search(r"/jobs/skill-(\d+)", driver.current_url)
    if skill_match:
        skill_id = skill_match.group(1)
        print(f"  スキルURLへのリダイレクトを検出 (skill={skill_id})、prefecture付きで再アクセス")
        corrected_url = f"{base_url}/jobs?skill={skill_id}&page=1&prefecture={prefecture}"
        driver.get(corrected_url)
        time.sleep(random.uniform(*delay_range))
        return lambda page: f"{base_url}/jobs?skill={skill_id}&page={page}&prefecture={prefecture}"

    return lambda page: f"{base_url}/jobs?keyword={keyword}&page={page}&prefecture={prefecture}"


def _normalize_url(href: str) -> str:
    """クエリパラメータ・フラグメントを除いた正規URLを返す。"""
    parsed = urlparse(href)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _detect_max_page(driver: webdriver.Remote) -> int:
    """ul.pagination 内の数値リンクから最大ページ数を返す。

    ページネーション自体が存在しない場合は案件が1ページ以内か0件かを
    リンク有無で判断し、1 または 0 を返す。
    """
    pagination = driver.find_elements(By.CSS_SELECTOR, "ul.pagination li a")
    if pagination:
        numbers = [int(a.text) for a in pagination if a.text.strip().isdigit()]
        return max(numbers) if numbers else 1

    fallback = driver.find_elements(
        By.CSS_SELECTOR,
        "section#job-list div.row.my-4 a[href*='/jobs/detail/']",
    )
    return 1 if fallback else 0
