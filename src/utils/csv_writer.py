import csv
import os
from datetime import datetime

FIELDS = [
    "検索キーワード",
    "案件URL",
    "案件タイトル",
    "特徴タグ",
    "単価",
    "使用技術",
    "職務内容",
    "必須スキル",
    "歓迎スキル",
    "職種",
    "契約形態",
    "勤務地",
    "エージェント名",
    "稼働日数",
]


def write_to_csv(jobs: list[dict], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"jobs_{timestamp}.csv")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(jobs)

    return filepath
