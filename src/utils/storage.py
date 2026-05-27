"""ストレージ抽象クラスとローカルファイルシステム実装。

新たなストレージバックエンド（S3 など）を追加する場合は BaseStorage を継承して
各メソッドを実装し、create_storage() に分岐を追加する。

## S3 実装時の注意点

### append_csv
S3 はオブジェクトへのネイティブ追記をサポートしない。
以下の Read-Modify-Write パターンで実装すること。

    existing = self.read_csv(filename)       # S3 から既存データを取得
    combined = existing + rows               # 行を結合
    self.write_csv(filename, combined, ...)  # S3 へ上書きアップロード

### create_log_handler
S3 へリアルタイムに 1 行ずつログを書き込むことはできない。
以下のいずれかで実装する。

    案1: logging.handlers.MemoryHandler でバッファし、プロセス終了時に S3 アップロード
    案2: ローカル一時ファイルへ書き込み、プロセス終了時に S3 アップロード
    案3: AWS CloudWatch Logs 用のカスタムハンドラを使用

### full_path / uri
S3 の場合は `s3://bucket/prefix/filename` 形式の URI を返す。
main.py はこの値を表示用途にのみ使用するため、形式は自由。

### config.json
S3 を使用する場合は以下のように設定する。

    {
      "storage": {
        "urls":    { "type": "s3", "path": "s3://my-bucket/scraper/urls" },
        "details": { "type": "s3", "path": "s3://my-bucket/scraper/details" },
        "logs":    { "type": "s3", "path": "s3://my-bucket/scraper/logs" }
      }
    }
"""

import csv
import logging
import os
from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """ストレージ操作の抽象基底クラス。

    CSV の読み書きとログハンドラ生成を抽象化し、
    ローカル・クラウド等の実装を切り替え可能にする。

    すべてのファイル操作はこのクラスのメソッド経由で行うこと。
    main.py などで open() / os.path を直接使うと S3 対応できなくなる。
    """

    @property
    @abstractmethod
    def uri(self) -> str:
        """ストレージのベース URI（ロギング用）。
        ローカル実装では絶対パス、S3 実装では s3://bucket/prefix を返す。
        """

    @abstractmethod
    def read_csv(self, filename: str) -> list[dict]:
        """filename（ストレージ相対パス）の CSV を読み込む。
        ファイルが存在しない場合は空リストを返す（FileNotFoundError は送出しない）。
        """

    @abstractmethod
    def write_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """filename を上書き作成する。書き込み先のフルパス/URI を返す。
        親ディレクトリ（S3 の場合はプレフィックス）は自動的に作成する。
        """

    @abstractmethod
    def append_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """filename に rows を追記する（なければ新規作成）。書き込み先のフルパス/URI を返す。
        S3 実装では Read-Modify-Write（read_csv → 結合 → write_csv）で実現すること。
        """

    @abstractmethod
    def create_log_handler(self, filename: str) -> logging.Handler:
        """ログ書き込み用ハンドラを返す。
        S3 実装では MemoryHandler や一時ファイル経由で対応する（モジュール docstring 参照）。
        """

    @abstractmethod
    def full_path(self, filename: str) -> str:
        """filename のフルパス/URI を返す（表示・ログ用途）。
        ローカル実装では絶対パス、S3 実装では s3://bucket/prefix/filename を返す。
        """


class LocalStorage(BaseStorage):
    """ローカルファイルシステムへの BaseStorage 実装。

    path 配下にファイルを読み書きする。サブディレクトリ（archive/ など）は
    書き込み時に自動生成する。
    """

    def __init__(self, path: str):
        self._path = path

    @property
    def uri(self) -> str:
        return self._path

    def read_csv(self, filename: str) -> list[dict]:
        """ファイルが存在しない場合は空リストを返す（初回実行時の安全な読み込み）。"""
        filepath = os.path.join(self._path, filename)
        if not os.path.exists(filepath):
            return []
        with open(filepath, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def write_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """上書きで書き込む。latest.csv の更新に使用する。"""
        filepath = os.path.join(self._path, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return filepath

    def append_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """ファイルが存在すれば追記、なければ新規作成する。archive/ の日次ファイルに使用する。

        既存ファイルへの追記時は BOM を再書きしないよう utf-8 を使用する。
        """
        filepath = os.path.join(self._path, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file_exists = os.path.exists(filepath)
        encoding = "utf-8" if file_exists else "utf-8-sig"
        mode = "a" if file_exists else "w"
        with open(filepath, mode, newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows)
        return filepath

    def create_log_handler(self, filename: str) -> logging.Handler:
        """FileHandler を生成する。S3 実装では異なるハンドラを返す（モジュール docstring 参照）。"""
        os.makedirs(self._path, exist_ok=True)
        return logging.FileHandler(os.path.join(self._path, filename), encoding="utf-8")

    def full_path(self, filename: str) -> str:
        return os.path.join(self._path, filename)


def create_storage(cfg) -> BaseStorage:
    """StorageTarget から対応する BaseStorage 実装を生成するファクトリ関数。

    新しいストレージ種別を追加する場合はここに elif ブロックを追加する。

        elif cfg.type == "s3":
            return S3Storage(cfg.path)  # s3://bucket/prefix を受け取る想定
    """
    if cfg.type == "local":
        return LocalStorage(cfg.path)
    raise ValueError(f"unsupported storage type: {cfg.type!r}")
