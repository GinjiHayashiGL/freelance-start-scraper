# freelance-start-scraper

[freelance-start.com](https://freelance-start.com) の案件情報を収集する Selenium ベースのスクレイパー。

## フォルダ構成

```text
freelance-start-scraper/
├── src/
│   ├── main.py               # エントリポイント（--phase で実行フェーズを選択）
│   ├── scraper/
│   │   ├── driver.py         # WebDriver 生成（ボット検知回避設定込み）
│   │   ├── list_page.py      # 案件一覧ページから詳細URLを収集
│   │   └── detail_page.py    # 案件詳細ページから情報を取得
│   ├── utils/
│   │   ├── config.py         # input/config.json の読み込み・データクラス定義
│   │   ├── fields.py         # CSV カラム定義（URL_FIELDS / DETAIL_FIELDS）
│   │   ├── logger.py         # JST タイムスタンプ付きロガー設定
│   │   ├── storage.py        # ストレージ抽象クラスとローカル実装
│   │   └── timezone.py       # JST タイムゾーン定義とユーティリティ
│   └── debug/                # 開発・調査用スクリプト
│       ├── page_elements.py  # 詳細ページの全要素をダンプ
│       ├── list_elements.py  # 一覧ページのリンク構造と要素をダンプ
│       └── duplicates.py     # URL 重複を確認
├── input/
│   └── config.json           # スクレイピング設定
├── output/                   # スクレイピング結果（.gitignore 対象）
│   ├── urls/
│   │   ├── latest.csv        # 全期間の累積 URL 一覧
│   │   └── archive/          # 日次差分 YYYYMMDD.csv
│   ├── details/
│   │   ├── latest.csv        # 全期間の累積 詳細一覧
│   │   └── archive/          # 日次差分 YYYYMMDD.csv
│   ├── logs/                 # 実行ログ（scraper_YYYYMMDD_HHMMSS.log）
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
  "max_details": 0,
  "request_delay_sec": { "min": 2.0, "max": 4.0 },
  "storage": {
    "urls":    { "type": "local", "path": "/app/output/urls" },
    "details": { "type": "local", "path": "/app/output/details" },
    "logs":    { "type": "local", "path": "/app/output/logs" }
  }
}
```

| フィールド | 説明 |
| --- | --- |
| `keywords` | 検索キーワードのリスト |
| `prefecture` | 都道府県コード（`13` = 東京） |
| `max_pages` | 1 キーワードあたりの取得上限ページ数（`0` = 全ページ） |
| `max_details` | 1 実行あたりの詳細取得上限件数（`0` = 未取得分すべて） |
| `request_delay_sec` | リクエスト間の待機秒数（min〜max のランダム） |
| `storage` | 出力先設定（`urls` / `details` / `logs` ごとに `type` と `path` を指定） |

### 2. 環境変数ファイルの作成

```bash
cp .env.example .env
```

`.env` には Selenium コンテナの接続情報のみ記載する。

### 3. コンテナの起動

```bash
docker compose up --build
```

### 4. スクレイパーの実行

`scraper` コンテナは起動後に自動でスクリプトを実行しない。以下のコマンドでコンテナに入って手動実行する。

```bash
docker exec -it scraper bash
```

| コマンド | 動作 |
| --- | --- |
| `python src/main.py` | URL 収集 → 詳細取得を連続実行（デフォルト） |
| `python src/main.py --phase urls` | URL 収集のみ |
| `python src/main.py --phase details` | 詳細取得のみ（urls/latest.csv が必要） |
| `python src/main.py --phase all` | URL 収集 → 詳細取得を連続実行 |

### 5. 出力ファイル

実行のたびに差分のみを追加する累積方式を採用している。

| ファイル | 内容 |
| --- | --- |
| `output/urls/latest.csv` | 全期間の累積 URL 一覧（重複排除済み） |
| `output/urls/archive/YYYYMMDD.csv` | その日に新たに発見した URL の差分 |
| `output/details/latest.csv` | 全期間の累積 詳細一覧 |
| `output/details/archive/YYYYMMDD.csv` | その日に新たに取得した詳細の差分 |
| `output/logs/scraper_YYYYMMDD_HHMMSS.log` | 実行ログ（JST） |

### 6. ブラウザ動作の確認（noVNC）

```text
http://localhost:7900/?autoconnect=1&resize=scale&password=secret
```

### 7. コンテナの停止

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

## ストレージ拡張について

`src/utils/storage.py` の `BaseStorage` を継承することで、S3 等の別ストレージへの切り替えが可能。

1. `BaseStorage` を継承したクラスを実装する
2. `create_storage()` に `elif cfg.type == "s3":` の分岐を追加する
3. `config.json` の `storage.*.type` を `"s3"` に変更する
