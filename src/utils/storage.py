"""ストレージ抽象クラスとローカルファイルシステム実装。

新たなストレージバックエンド（S3 など）を追加する場合は BaseStorage を継承して
各メソッドを実装し、create_storage() に分岐を追加する。
"""

import csv
import logging
import os
from abc import ABC, abstractmethod


class BaseStorage(ABC):
    """ストレージ操作の抽象基底クラス。

    CSV の読み書きとログハンドラ生成を抽象化し、
    ローカル・クラウド等の実装を切り替え可能にする。
    """

    @property
    @abstractmethod
    def uri(self) -> str:
        """ストレージの場所を示す文字列（ロギング用）。"""

    @abstractmethod
    def read_csv(self, filename: str) -> list[dict]:
        """指定ファイルを読み込む。ファイルが存在しない場合は空リストを返す。"""

    @abstractmethod
    def write_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """指定ファイルを上書き作成する。書き込み先パス/URI を返す。"""

    @abstractmethod
    def append_csv(self, filename: str, rows: list[dict], fieldnames: list[str]) -> str:
        """指定ファイルに追記する（なければ作成）。書き込み先パス/URI を返す。"""

    @abstractmethod
    def create_log_handler(self, filename: str) -> logging.Handler:
        """ログ書き込み用ハンドラを返す。"""

    @abstractmethod
    def full_path(self, filename: str) -> str:
        """ファイルのフルパス/URI を返す。"""


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
        """FileHandler を生成する。S3 実装では異なるハンドラを返す。"""
        os.makedirs(self._path, exist_ok=True)
        return logging.FileHandler(os.path.join(self._path, filename), encoding="utf-8")

    def full_path(self, filename: str) -> str:
        return os.path.join(self._path, filename)


def create_storage(cfg) -> BaseStorage:
    """StorageTarget から対応する BaseStorage 実装を生成するファクトリ関数。

    新しいストレージ種別を追加する場合はここに elif ブロックを追加する。
    """
    if cfg.type == "local":
        return LocalStorage(cfg.path)
    raise ValueError(f"unsupported storage type: {cfg.type!r}")
