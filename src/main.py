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
_SAVE_INTERVAL = 10  # 詳細取得を N 件成功するたびに CSV へ途中保存


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
        + (f"  retry_file={args.retry_file}" if args.retry_file else "")
    )

    driver = create_driver()
    try:
        if args.retry_file:
            # リトライモード: 失敗ファイルから URL を読み込んで詳細取得のみ実行
            retry_rows = _load_retry_file(detail_storage, args.retry_file)
            phase_start = time.perf_counter()
            _run_detail_phase(driver, retry_rows, cfg, detail_storage)
            logger.info(f"[retry] phase elapsed={_fmt_elapsed(time.perf_counter() - phase_start)}")
        else:
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

    seen_urls セットを get_all_urls_for_keyword に渡すことで、
    既存CSVとの重複排除・複数キーワード間の重複排除を list_page 側に一本化している。
    """
    existing_rows = url_storage.read_csv(_LATEST)
    seen_urls = {row["案件URL"] for row in existing_rows}

    new_rows: list[dict] = []
    for keyword in cfg.keywords:
        urls = get_all_urls_for_keyword(
            driver, cfg.base_url, keyword, cfg.prefecture,
            cfg.max_pages, cfg.request_delay_sec,
            seen=seen_urls,  # 共有セットを渡す（関数内で新規URLが追加される）
        )
        for url in urls:
            new_rows.append({"検索キーワード": keyword, "案件URL": url})
        logger.info(f"[urls] keyword={keyword}  new={len(urls)}")

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

    _SAVE_INTERVAL 件成功するたびに途中保存するため、途中クラッシュ時の損失を最小化する。
    個別URLのスクレイピングに失敗した場合はスキップして継続し、
    失敗URLを output/details/failed/YYYYMMDD_HHMMSS.csv に保存する。
    失敗ファイルのパスはログに出力するため、--retry-file で再実行できる。
    """
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
    failed_rows: list[dict] = []
    last_saved = 0   # new_jobs のうち保存済みの末尾インデックス
    date_str = jst_now().strftime("%Y%m%d")

    for i, row in enumerate(targets, 1):
        url = row["案件URL"]
        logger.info(f"[{i}/{total}] {url}")
        try:
            job = scrape_job_detail(
                driver, url, row["検索キーワード"], cfg.request_delay_sec,
            )
            new_jobs.append(job)
        except Exception as exc:
            logger.warning(f"[{i}/{total}] skip {url}: {exc}")
            failed_rows.append({
                "検索キーワード": row["検索キーワード"],
                "案件URL": url,
                "エラー": str(exc),
            })

        # 定期保存: _SAVE_INTERVAL 件成功ごと、または最終件
        ready = len(new_jobs) - last_saved
        if (ready >= _SAVE_INTERVAL or i == total) and ready > 0:
            batch = new_jobs[last_saved:]
            all_jobs = existing_details + new_jobs
            detail_storage.write_csv(_LATEST, all_jobs, DETAIL_FIELDS)
            detail_storage.append_csv(f"archive/{date_str}.csv", batch, DETAIL_FIELDS)
            last_saved = len(new_jobs)
            logger.info(
                f"[details] checkpoint  batch={len(batch)}  total_new={len(new_jobs)}"
            )

    # 失敗URLをファイルに保存し、リトライコマンドをログ出力
    if failed_rows:
        ts = jst_now().strftime("%Y%m%d_%H%M%S")
        fail_filename = f"failed/{ts}.csv"
        detail_storage.write_csv(
            fail_filename,
            failed_rows,
            ["検索キーワード", "案件URL", "エラー"],
        )
        logger.warning(
            f"[details] {len(failed_rows)} URLs failed → {detail_storage.full_path(fail_filename)}\n"
            f"  リトライ: python src/main.py --retry-file {fail_filename}"
        )

    logger.info(
        f"[details] done  new={len(new_jobs)}  failed={len(failed_rows)}  "
        f"total={len(existing_details) + len(new_jobs)}"
    )


def _load_retry_file(storage: BaseStorage, filename: str) -> list[dict]:
    """--retry-file で渡された失敗URLファイルを読み込み、_run_detail_phase に渡せる形式で返す。

    filename は detail_storage 相対パス（例: failed/20240101_120000.csv）。
    storage.read_csv() 経由で読み込むため、LocalStorage / S3Storage を問わず動作する。

    失敗ファイルのカラムは 検索キーワード / 案件URL / エラー。
    _run_detail_phase が必要とする 検索キーワード / 案件URL を含むためそのまま渡せる。
    """
    rows = storage.read_csv(filename)
    if not rows:
        raise ValueError(
            f"retry file not found or empty: {storage.full_path(filename)}"
        )
    logger.info(f"[retry] load {storage.full_path(filename)} ({len(rows)} rows)")
    return rows


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
    parser.add_argument(
        "--retry-file",
        metavar="FILENAME",
        help=(
            "詳細取得に失敗したURLのリトライ対象ファイル。"
            "detail ストレージ相対パスで指定する（例: failed/20240101_120000.csv）。"
            "指定した場合は --phase を無視して詳細取得のみ実行する。"
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
