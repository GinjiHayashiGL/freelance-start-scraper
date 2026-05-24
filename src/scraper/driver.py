import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def create_driver() -> webdriver.Remote:
    selenium_host = os.getenv("SELENIUM_HOST", "selenium")
    selenium_port = os.getenv("SELENIUM_PORT", "4444")

    options = Options()
    # ボット検知回避
    options.add_argument(f"user-agent={_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # コンテナ動作に必要なオプション
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Remote(
        command_executor=f"http://{selenium_host}:{selenium_port}/wd/hub",
        options=options,
    )
    # navigator.webdriver を undefined に上書き（CDP 経由でページ読込前に適用）
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver
