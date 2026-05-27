"""案件一覧ページから詳細URLを収集する。ページネーション・リダイレクト検出・URL正規化を含む。"""

import logging
import re
import time
import random
from collections.abc import Callable
from urllib.parse import urlparse, urlunparse

from selenium import webdriver

logger = logging.getLogger(__name__)


def get_all_urls_for_keyword(
    driver: webdriver.Remote,
    base_url: str,
    keyword: str,
    prefecture: str = "13",
    max_pages: int = 0,
    delay_range: tuple[float, float] = (2.0, 4.0),
    seen: set[str] | None = None,
) -> list[str]:
    """指定キーワードの案件詳細URLを収集する。

    seen: 既知URLのセット。渡した場合はそのセットを共有して重複排除し、
          発見した新規URLをセットに追加する（呼び出し元のセットが更新される）。
          複数キーワード間・既存CSVとの重複排除を呼び出し側と一本化するために使う。
    max_pages:   取得上限ページ数。0 はページネーションから自動検出した全ページ取得。
    delay_range: リクエスト間の待機秒数 (min, max)。
    """
    if seen is None:
        seen = set()

    urls: list[str] = []

    # ページ1にアクセスしてスキルURLへのリダイレクトを検出する。
    #
    # 【仕様】キーワードがサイトのスキル名と完全一致する場合、freelance-start.com は
    # prefecture パラメータを無視した /jobs/skill-{id} へ自動リダイレクトする。
    # そのため _resolve_page_url_builder 内で 2 回目のアクセスを行い、
    # prefecture を含む正しい URL を再構築する必要がある（意図的な二重アクセス）。
    initial_url = f"{base_url}/jobs?keyword={keyword}&page=1&prefecture={prefecture}"
    logger.info(f"[{keyword}] p=1 GET {initial_url}")
    driver.get(initial_url)
    time.sleep(random.uniform(*delay_range))

    build_page_url = _resolve_page_url_builder(driver, base_url, keyword, prefecture, delay_range)

    detected_max = _detect_max_page(driver)
    total_pages = max_pages if max_pages > 0 else detected_max

    if detected_max == 0:
        logger.info(f"[{keyword}] no jobs found")
        return []

    logger.info(f"[{keyword}] pages={detected_max} target={total_pages}")

    for page in range(1, total_pages + 1):
        if page > 1:
            page_url = build_page_url(page)
            logger.info(f"[{keyword}] p={page} GET {page_url}")
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
        logger.info(f"[{keyword}] p={page} new={len(new_urls)} total={len(urls)}")

    return urls


def _resolve_page_url_builder(
    driver: webdriver.Remote,
    base_url: str,
    keyword: str,
    prefecture: str,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> Callable[[int], str]:
    """現在のURLを確認してリダイレクト有無を判定し、ページURLビルダーを返す。

    【仕様】キーワードがスキル名と完全一致した場合、サイトは prefecture パラメータを
    無視した /jobs/skill-{id} へリダイレクトする。この関数では skill_id を取得したうえで
    prefecture を含む正しい URL を再構築し直す（2 回目のアクセス）。
    リダイレクトがない場合は keyword パラメータ形式をそのまま使う。
    """
    skill_match = re.search(r"/jobs/skill-(\d+)", driver.current_url)
    if skill_match:
        skill_id = skill_match.group(1)
        logger.info(f"[{keyword}] redirect skill={skill_id}")
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
    """ul.pagination 内の数値リンクから最大ページ数を返す（JS 1 回で取得）。

    Python の find_elements による複数往復を避け、JS 1 回の execute_script に統合。
    ページネーション自体が存在しない場合は案件が1ページ以内か0件かを
    リンク有無で判断し、1 または 0 を返す。
    """
    return driver.execute_script("""
        const links = document.querySelectorAll('ul.pagination li a');
        if (links.length) {
            const nums = Array.from(links)
                .map(a => parseInt(a.textContent.trim(), 10))
                .filter(n => !isNaN(n));
            return nums.length ? Math.max(...nums) : 1;
        }
        return document.querySelector(
            "section#job-list div.row.my-4 a[href*='/jobs/detail/']"
        ) ? 1 : 0;
    """)
