# freelance-start-scraper

[freelance-start.com](https://freelance-start.com) の案件情報を収集する Selenium ベースのスクレイパー。

## フォルダ構成

```text
freelance-start-scraper/
├── src/
│   ├── main.py               # エントリポイント
│   ├── scraper/
│   │   ├── driver.py         # WebDriver 生成（ボット検知回避設定込み）
│   │   ├── list_page.py      # 案件一覧ページから詳細URLを収集
│   │   └── detail_page.py    # 案件詳細ページから情報を取得
│   ├── utils/
│   │   ├── config.py         # input/config.json の読み込み
│   │   └── csv_writer.py     # 案件詳細の CSV 出力
│   └── debug/                # 開発・調査用スクリプト
│       ├── page_elements.py  # 詳細ページの全要素をダンプ
│       ├── list_elements.py  # 一覧ページのリンク構造と要素をダンプ
│       └── duplicates.py     # URL 重複を確認
├── input/
│   └── config.json           # スクレイピング設定
├── output/
│   ├── urls/                 # 案件 URL 一覧 CSV
│   ├── details/              # 案件詳細 CSV（将来実装）
│   └── debug/                # デバッグスクリプトの出力
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 技術スタック

| 項目 | 内容 |
| --- | --- |
| 言語 | Python 3.13 |
| スクレイピング | Selenium 4.x (Remote WebDriver) |
| 実行環境 | Docker / Docker Compose |
| ブラウザ | selenium/standalone-chrome |

## コンテナ構成

| コンテナ名 | イメージ | 役割 |
| --- | --- | --- |
| `scraper` | python:3.13-slim (Dockerfile) | スクレイピング処理 |
| `selenium` | selenium/standalone-chrome:latest | Chrome WebDriver サーバ |

## セットアップと実行

### 1. 設定ファイルの編集

`input/config.json` を編集してキーワードなどを設定する。

```json
{
  "base_url": "https://freelance-start.com",
  "keywords": ["データエンジニア", "Python"],
  "prefecture": "13",
  "max_pages": 0,
  "output_dir": "/app/output",
  "request_delay_sec": { "min": 2.0, "max": 4.0 }
}
```

| フィールド | 説明 |
| --- | --- |
| `keywords` | 検索キーワードのリスト |
| `prefecture` | 都道府県コード（`13` = 東京） |
| `max_pages` | 1 キーワードあたりの取得上限ページ数（`0` = 全ページ） |
| `request_delay_sec` | リクエスト間の待機秒数（min〜max のランダム） |

### 2. 環境変数ファイルの作成

```bash
cp .env.example .env
```

`.env` には Selenium コンテナの接続情報のみ記載する。

### 3. コンテナの起動

```bash
docker compose up --build
```

### 4. スクレイパーを手動実行

`scraper` コンテナは起動後に自動でスクリプトを実行しない。以下のコマンドでコンテナに入って手動実行する。

```bash
docker exec -it scraper bash
python src/main.py
```

結果は `output/urls/job_urls_YYYYMMDD_HHMMSS.csv` に出力される。

### 5. ブラウザ動作の確認（noVNC）

```text
http://localhost:7900/?autoconnect=1&resize=scale&password=secret
```

### 6. コンテナの停止

```bash
docker compose down
```

## 環境変数（.env）

| 変数名 | デフォルト値 | 説明 |
| --- | --- | --- |
| `SELENIUM_HOST` | `selenium` | Selenium コンテナのホスト名 |
| `SELENIUM_PORT` | `4444` | Selenium サーバのポート番号 |

スクレイピング設定（対象URL・キーワード等）は `input/config.json` で管理する。

## デバッグスクリプト

コンテナ内で以下のコマンドで実行できる。

| スクリプト | コマンド | 出力 |
| --- | --- | --- |
| 詳細ページ要素ダンプ | `python src/debug/page_elements.py` | `output/debug/page_elements.csv` |
| 一覧ページ要素ダンプ | `python src/debug/list_elements.py` | `output/debug/list_links.csv` / `list_elements.csv` |
| URL 重複確認 | `python src/debug/duplicates.py` | `output/debug/duplicates.csv` |

対象 URL は環境変数 `DEBUG_URL` で上書き可能。

## ボット検知回避

`src/scraper/driver.py` で以下の対策を実施している。

- 一般的なデスクトップ User-Agent を設定
- ウィンドウサイズを実ブラウザと同等（1920×1080）に設定
- `--disable-blink-features=AutomationControlled` で自動化フラグを無効化
- `navigator.webdriver` を `undefined` に上書き（CDP 経由）
