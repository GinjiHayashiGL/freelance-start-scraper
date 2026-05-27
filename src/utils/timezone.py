"""JST タイムゾーン定義と現在時刻取得ユーティリティ。

ファイル名・ログのタイムスタンプを日本時間で統一するために使用する。
"""

from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def jst_now() -> datetime:
    """JST での現在時刻を返す。"""
    return datetime.now(JST)
