"""Selenium RemoteWebDriver の生成。ボット検知回避設定を含む。"""

import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ボット検知を避けるため、一般的なデスクトップブラウザの UA を偽装する
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def create_driver() -> webdriver.Remote:
    """ボット検知回避設定を施した Selenium RemoteWebDriver を生成して返す。

    接続先は環境変数 SELENIUM_HOST / SELENIUM_PORT で指定する（.env で管理）。
    """
    selenium_host = os.getenv("SELENIUM_HOST", "selenium")
    selenium_port = os.getenv("SELENIUM_PORT", "4444")

    options = Options()
    # ボット検知回避: UA 偽装・ウィンドウサイズ・自動化フラグ無効化
    options.add_argument(f"user-agent={_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # コンテナ環境で必要なオプション
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Remote(
        command_executor=f"http://{selenium_host}:{selenium_port}/wd/hub",
        options=options,
    )
    # navigator.webdriver を undefined に上書きしてヘッドレス検出を回避する。
    # CDP 経由でページ読込前に注入することで全ページに適用される。
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver
