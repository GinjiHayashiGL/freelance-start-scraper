"""スクレイパーのエントリポイント。URL収集・詳細取得の2フェーズをオーケストレートする。"""

import argparse
import logging
import time

from scraper.detail_page import scrape_job_detail
from scraper.driver import create_driver
from scraper.list_page import get_all_urls_for_keyword
from utils.config import load_config
from utils.fields import DETAIL_FIELDS, URL_FIELDS
from utils.logger import setup_logger
from utils.storage import BaseStorage, create_storage
from utils.timezone import jst_now

logger = logging.getLogger(__name__)

_LATEST = "latest.csv"


def main() -> None:
    """設定読み込み・ロガー初期化・WebDriver 生成を行い、指定フェーズを実行する。"""
    args = _parse_args()
    cfg = load_config()
    setup_logger(create_storage(cfg.storage.logs))

    url_storage = create_storage(cfg.storage.urls)
    detail_storage = create_storage(cfg.storage.details)

    total_start = time.perf_counter()
    logger.info(
        f"phase={args.phase}  "
        f"max_pages={cfg.max_pages or 'all'}  "
        f"max_details={cfg.max_details or 'all'}"
    )

    driver = create_driver()
    try:
        if args.phase in ("urls", "all"):
            phase_start = time.perf_counter()
            all_rows = _run_url_phase(driver, cfg, url_storage)
            logger.info(f"[urls] phase elapsed={_fmt_elapsed(time.perf_counter() - phase_start)}")
        else:
            all_rows = _load_latest_url_csv(url_storage)

        if args.phase in ("details", "all"):
            phase_start = time.perf_counter()
            _run_detail_phase(driver, all_rows, cfg, detail_storage)
            logger.info(f"[details] phase elapsed={_fmt_elapsed(time.perf_counter() - phase_start)}")
    finally:
        driver.quit()
        logger.info(f"elapsed {_fmt_elapsed(time.perf_counter() - total_start)}")


def _run_url_phase(driver, cfg, url_storage: BaseStorage) -> list[dict]:
    """全キーワードの案件URLを収集し、latest.csv と archive/ に保存して全行を返す。

    既存の latest.csv を読み込んで差分のみ追加することで重複を防ぐ。
    """
    # 既存の累積データを読み込み、差分収集の基準とする
    existing_rows = url_storage.read_csv(_LATEST)
    seen_urls = {row["案件URL"] for row in existing_rows}

    new_rows: list[dict] = []
    for keyword in cfg.keywords:
        urls = get_all_urls_for_keyword(
            driver, cfg.base_url, keyword, cfg.prefecture,
            cfg.max_pages, cfg.request_delay_sec,
        )
        keyword_new = 0
        for url in urls:
            if url not in seen_urls:
                seen_urls.add(url)
                new_rows.append({"検索キーワード": keyword, "案件URL": url})
                keyword_new += 1
        logger.info(f"[urls] keyword={keyword}  fetched={len(urls)}  new={keyword_new}")

    all_rows = existing_rows + new_rows
    if new_rows:
        date_str = jst_now().strftime("%Y%m%d")
        archive = url_storage.append_csv(f"archive/{date_str}.csv", new_rows, URL_FIELDS)
        url_storage.write_csv(_LATEST, all_rows, URL_FIELDS)
        logger.info(f"[urls] new={len(new_rows)} total={len(all_rows)} archive={archive}")
    else:
        logger.info(f"[urls] no new urls, total={len(all_rows)}")

    return all_rows


def _run_detail_phase(driver, all_rows: list[dict], cfg, detail_storage: BaseStorage) -> None:
    """未取得の案件URLのみを対象に詳細スクレイピングし、latest.csv と archive/ に保存する。

    all_rows は URL フェーズの全行、または latest.csv から読み込んだ行。
    """
    # 既取得の詳細データを読み込み、未取得URLのみを対象にする
    existing_details = detail_storage.read_csv(_LATEST)
    scraped_urls = {row["案件URL"] for row in existing_details}
    targets = [row for row in all_rows if row["案件URL"] not in scraped_urls]
    if cfg.max_details > 0:
        targets = targets[: cfg.max_details]

    total = len(targets)
    logger.info(f"[details] to_scrape={total}  already_done={len(scraped_urls)}")

    if not targets:
        logger.info("[details] no new jobs to scrape")
        return

    new_jobs: list[dict] = []
    for i, row in enumerate(targets, 1):
        logger.info(f"[{i}/{total}] {row['案件URL']}")
        job = scrape_job_detail(
            driver, row["案件URL"], row["検索キーワード"], cfg.request_delay_sec,
        )
        new_jobs.append(job)

    all_jobs = existing_details + new_jobs
    date_str = jst_now().strftime("%Y%m%d")
    archive = detail_storage.append_csv(f"archive/{date_str}.csv", new_jobs, DETAIL_FIELDS)
    detail_storage.write_csv(_LATEST, all_jobs, DETAIL_FIELDS)
    logger.info(f"[details] new={len(new_jobs)} total={len(all_jobs)} archive={archive}")


def _load_latest_url_csv(url_storage: BaseStorage) -> list[dict]:
    """urls/latest.csv を読み込んで返す。ファイルが存在しない場合は例外を送出する。"""
    rows = url_storage.read_csv(_LATEST)
    if not rows:
        raise FileNotFoundError(
            f"urls/latest.csv not found or empty: {url_storage.uri}"
        )
    logger.info(f"[urls] load {url_storage.full_path(_LATEST)} ({len(rows)} rows)")
    return rows


def _fmt_elapsed(seconds: float) -> str:
    """経過秒数を HH:MM:SS 形式の文字列に変換する。"""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析して返す。--phase で実行フェーズを選択する。"""
    parser = argparse.ArgumentParser(description="freelance-start.com スクレイパー")
    parser.add_argument(
        "--phase",
        choices=["urls", "details", "all"],
        default="all",
        help="実行フェーズ (urls: URL収集のみ / details: 詳細取得のみ / all: 両方)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
