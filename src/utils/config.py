"""スクレイピング設定の読み込み。input/config.json を Config オブジェクトに変換する。"""

import json
from dataclasses import dataclass

# コンテナ内の固定パス。docker-compose で ./input:/app/input をマウントして使う。
CONFIG_PATH = "/app/input/config.json"


@dataclass
class StorageTarget:
    """単一ストレージの種別とパスを保持するデータクラス。

    type: ストレージ種別 ("local" | 将来: "s3" など)
    path: ローカルパス or S3 URI (s3://bucket/prefix)
    """

    type: str
    path: str


@dataclass
class StorageConfig:
    """URLs・詳細・ログそれぞれのストレージ設定を束ねるデータクラス。"""

    urls: StorageTarget
    details: StorageTarget
    logs: StorageTarget


@dataclass
class Config:
    """config.json から読み込んだスクレイピング設定全体を保持するデータクラス。"""

    base_url: str
    keywords: list[str]
    prefecture: str
    max_pages: int    # 0 = 全ページ取得
    max_details: int  # 0 = 未取得分すべて
    request_delay_sec: tuple[float, float]
    storage: StorageConfig


def _parse_target(data: dict, default_path: str) -> StorageTarget:
    """dict から StorageTarget を生成する。キーが省略された場合はデフォルト値を使用する。"""
    return StorageTarget(
        type=data.get("type", "local"),
        path=data.get("path", default_path),
    )


def load_config() -> Config:
    """CONFIG_PATH から JSON を読み込み Config オブジェクトを返す。"""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)

    delay = data.get("request_delay_sec", {})
    storage_data = data.get("storage", {})
    return Config(
        base_url=data["base_url"],
        keywords=data["keywords"],
        prefecture=str(data["prefecture"]),
        max_pages=int(data.get("max_pages", 0)),
        max_details=int(data.get("max_details", 0)),
        request_delay_sec=(float(delay.get("min", 2.0)), float(delay.get("max", 4.0))),
        storage=StorageConfig(
            urls=_parse_target(storage_data.get("urls", {}), "/app/output/urls"),
            details=_parse_target(storage_data.get("details", {}), "/app/output/details"),
            logs=_parse_target(storage_data.get("logs", {}), "/app/output/logs"),
        ),
    )
