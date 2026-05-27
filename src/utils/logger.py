"""ロガーのセットアップ。JST タイムスタンプ付きコンソール＋ファイル出力。"""

import logging
import sys
from datetime import datetime

from utils.storage import BaseStorage
from utils.timezone import JST, jst_now


class _JSTFormatter(logging.Formatter):
    """logging.Formatter のサブクラス。タイムスタンプを JST（UTC+9）で出力する。"""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=JST)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


def setup_logger(log_storage: BaseStorage, level: int = logging.INFO) -> None:
    """ルートロガーを設定する。

    stdout ハンドラは常に追加する。ログファイルは log_storage.create_log_handler()
    が返すハンドラを使用するため、ストレージ実装を切り替えるだけで出力先を変更できる。
    将来的に S3 などへ切り替える場合は S3Storage.create_log_handler() で対応ハンドラを返す。
    """
    root = logging.getLogger()
    if root.handlers:
        return  # 多重初期化防止
    root.setLevel(level)
    fmt = _JSTFormatter("%(asctime)s [%(levelname)s] %(message)s")

    # stdout へ常に出力
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    root.addHandler(stdout_handler)

    # ストレージ実装が返すハンドラでファイル（or クラウド）へ出力
    log_filename = f"scraper_{jst_now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = log_storage.create_log_handler(log_filename)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    logging.getLogger(__name__).info(f"log -> {log_storage.full_path(log_filename)}")
