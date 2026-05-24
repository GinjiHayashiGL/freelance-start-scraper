import json
import os
from dataclasses import dataclass


CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/input/config.json")


@dataclass
class Config:
    base_url: str
    keywords: list[str]
    prefecture: str
    max_pages: int
    output_dir: str
    request_delay_sec: tuple[float, float]


def load_config() -> Config:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)

    delay = data.get("request_delay_sec", {})
    return Config(
        base_url=data["base_url"],
        keywords=data["keywords"],
        prefecture=str(data["prefecture"]),
        max_pages=int(data.get("max_pages", 0)),
        output_dir=data.get("output_dir", "/app/output"),
        request_delay_sec=(float(delay.get("min", 2.0)), float(delay.get("max", 4.0))),
    )
