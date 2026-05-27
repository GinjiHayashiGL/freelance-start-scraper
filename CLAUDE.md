# CLAUDE.md — コーディングエージェント向け技術ガイド

このファイルはコーディングエージェント（Claude Code 等）がこのリポジトリを正しく理解・修正するための技術ドキュメントです。
ユーザー向けの運用手順は `README.md` を参照してください。

---

## アーキテクチャ概要

freelance-start.com の案件情報を Selenium で収集する Python スクレイパー。
**URL 収集 → 詳細取得** の 2 フェーズ構成で差分管理を行う。

### ファイルマップ

```
src/
├── main.py                 # エントリポイント・フェーズ制御・CSV 保存ロジック
├── scraper/
│   ├── driver.py           # WebDriver 生成（ボット検知回避設定込み）
│   ├── list_page.py        # URL 収集：一覧ページのページネーション・リダイレクト処理
│   └── detail_page.py      # 詳細取得：JS 1 回で全フィールドを一括取得
└── utils/
    ├── config.py           # config.json → Config dataclass へのマッピング
    ├── fields.py           # CSV カラム定義（URL_FIELDS / DETAIL_FIELDS）
    ├── storage.py          # BaseStorage 抽象クラス + LocalStorage 実装
    ├── logger.py           # JST タイムスタンプ付きロガー（storage 経由でログ出力先を抽象化）
    └── timezone.py         # JST タイムゾーン定義
```

### 処理フロー

```
main.py
 ├─ [urls フェーズ]
 │    list_page.get_all_urls_for_keyword()   # キーワードごとに一覧ページを巡回
 │    → urls/latest.csv（累積）+ archive/YYYYMMDD.csv（差分）に保存
 │
 └─ [details フェーズ]
      detail_page.scrape_job_detail()        # 未取得 URL のみ詳細取得
      → details/latest.csv（累積）+ archive/YYYYMMDD.csv（差分）に保存
        失敗時 → details/failed/YYYYMMDD_HHMMSS.csv に記録
```

---

## ⚠️ 変更禁止：リダイレクト時の二重アクセス

`src/scraper/list_page.py` の `get_all_urls_for_keyword` は、
キーワード検索時に page=1 を **意図的に 2 回アクセスする**。
これは「最適化すべき重複リクエスト」ではなく、**サイト仕様に基づいた必要な処理**である。

### 理由

freelance-start.com では、検索キーワードがサイト内のスキル名と完全一致するとき、
`prefecture`（都道府県）パラメータを**無視した** `/jobs/skill-{id}` へ自動リダイレクトする。

```
1回目のアクセス（意図した URL）:
  GET /jobs?keyword=Python&page=1&prefecture=13
       ↓ サイトが自動リダイレクト
  現在のURL: /jobs/skill-42   ← prefecture=13 が消えている

_resolve_page_url_builder() が skill_id=42 を検出

2回目のアクセス（修正後の正しい URL）:
  GET /jobs?skill=42&page=1&prefecture=13
       ↓ prefecture=13 の絞り込みが正しく反映された結果が表示される
```

### 実装箇所

```python
# list_page.py: get_all_urls_for_keyword()
driver.get(initial_url)                         # 1回目：リダイレクト有無を確認するため
build_page_url = _resolve_page_url_builder(...)  # リダイレクト検出 → 2回目アクセス

# list_page.py: _resolve_page_url_builder()
skill_match = re.search(r"/jobs/skill-(\d+)", driver.current_url)
if skill_match:
    driver.get(corrected_url)   # 2回目：prefecture を含む正しい URL で再取得
```

**この二重アクセスを削除・統合しないこと。削除すると prefecture フィルタが無効になる。**

---

## 設計原則

### 1. ストレージ抽象化ルール

**すべてのファイル I/O は `BaseStorage` メソッド経由で行うこと。**
`open()` / `os.path` / `pathlib` を `main.py` 等で直接使うと S3 対応できなくなる。

| ✅ やること | ❌ やらないこと |
|---|---|
| `storage.read_csv(filename)` | `open(filepath)` |
| `storage.write_csv(filename, rows, fields)` | `with open(filepath, "w") as f:` |
| `storage.full_path(filename)` を表示用に使う | `os.path.join(base, filename)` を直接扱う |

`filename` はすべて **ストレージ相対パス**（例: `"failed/20240101_120000.csv"`）で扱う。
フルパス / URI への変換は `storage.full_path()` が担う。

### 2. 重複排除（seen セット）

URL 収集フェーズでは `seen_urls` セットを `get_all_urls_for_keyword` に `seen=` パラメータとして渡す。
この共有セットで 2 種類の重複を一括排除している。

| 重複の種類 | 排除タイミング |
|---|---|
| 既存 CSV との重複 | `seen_urls` を `urls/latest.csv` の全 URL で初期化 |
| 複数キーワード間の重複 | keyword 1 の結果が `seen_urls` に追加され、keyword 2 以降に引き継がれる |

```python
# main.py: _run_url_phase()
seen_urls = {row["案件URL"] for row in existing_rows}   # CSV から初期化

for keyword in cfg.keywords:
    urls = get_all_urls_for_keyword(..., seen=seen_urls) # セットを共有・更新
    for url in urls:
        new_rows.append({"検索キーワード": keyword, "案件URL": url})
```

詳細取得フェーズでは `details/latest.csv` の `案件URL` カラムをキーとして未取得 URL を絞り込む。
失敗してスキップされた URL は `latest.csv` に記録されないため、再実行時に自動的に再試行される。

### 3. 途中保存とエラーハンドリング

詳細取得フェーズは `_SAVE_INTERVAL = 10` 件成功するたびに `latest.csv` と `archive/` へ途中保存する。
クラッシュ時の損失は最大 `_SAVE_INTERVAL - 1` 件に抑えられる。

```python
# main.py: _run_detail_phase()
for i, row in enumerate(targets, 1):
    try:
        job = scrape_job_detail(...)
        new_jobs.append(job)
    except Exception as exc:
        logger.warning(f"skip {url}: {exc}")
        failed_rows.append({...})           # 失敗 URL を記録してスキップ

    # _SAVE_INTERVAL 件成功 or 最終件で途中保存
    ready = len(new_jobs) - last_saved
    if (ready >= _SAVE_INTERVAL or i == total) and ready > 0:
        batch = new_jobs[last_saved:]
        detail_storage.write_csv(_LATEST, existing_details + new_jobs, DETAIL_FIELDS)
        detail_storage.append_csv(f"archive/{date_str}.csv", batch, DETAIL_FIELDS)
        last_saved = len(new_jobs)
```

### 4. リトライフロー

```
通常実行: python src/main.py --phase details
  ↓ N 件失敗
  → detail_storage.write_csv("failed/YYYYMMDD_HHMMSS.csv", failed_rows, ...)
  → ログ: "リトライ: python src/main.py --retry-file failed/YYYYMMDD_HHMMSS.csv"

リトライ: python src/main.py --retry-file failed/YYYYMMDD_HHMMSS.csv
  ↓ _load_retry_file(detail_storage, "failed/YYYYMMDD_HHMMSS.csv")
  ↓   → detail_storage.read_csv(filename) で読み込み（storage 経由）
  ↓ _run_detail_phase() に渡す
  ↓ details/latest.csv の scraped_urls と照合して未取得のみ実行
```

- `--retry-file` のパスは `detail_storage` 相対パス
- `--retry-file` を指定した場合、`--phase` は無視される
- 途中クラッシュ後は `--phase details` 同じ引数での再実行でも未取得分から自動再開できる

---

## ストレージ拡張ガイド（S3 実装）

### S3Storage 実装チェックリスト

| メソッド | 実装方針 |
|---|---|
| `read_csv(filename)` | `s3.get_object()` → CSV パース → `list[dict]` を返す。**不在時は `[]`（例外なし）** |
| `write_csv(filename, rows, fields)` | CSV を `io.StringIO` で生成 → `s3.put_object()` → S3 URI を返す |
| `append_csv(filename, rows, fields)` | `read_csv()` → 行結合 → `write_csv()` の **Read-Modify-Write** で実装（S3 はネイティブ追記不可） |
| `create_log_handler(filename)` | `MemoryHandler` でバッファするか、ローカル一時ファイルを使いプロセス終了時にアップロード |
| `full_path(filename)` | `f"s3://{bucket}/{prefix}/{filename}"` を返す |
| `uri` プロパティ | `f"s3://{bucket}/{prefix}"` を返す |

### ファクトリへの追加

```python
# src/utils/storage.py: create_storage()
elif cfg.type == "s3":
    return S3Storage(cfg.path)  # cfg.path = "s3://bucket/prefix"
```

### config.json の設定例

```json
{
  "storage": {
    "urls":    { "type": "s3", "path": "s3://my-bucket/scraper/urls" },
    "details": { "type": "s3", "path": "s3://my-bucket/scraper/details" },
    "logs":    { "type": "s3", "path": "s3://my-bucket/scraper/logs" }
  }
}
```

---

## CSV フォーマット

| ファイル | カラム |
| --- | --- |
| `urls/latest.csv` | 検索キーワード, 案件URL |
| `urls/archive/YYYYMMDD.csv` | 同上（その日の差分） |
| `details/latest.csv` | `DETAIL_FIELDS`（`src/utils/fields.py` 参照） |
| `details/archive/YYYYMMDD.csv` | 同上（その日の差分） |
| `details/failed/YYYYMMDD_HHMMSS.csv` | 検索キーワード, 案件URL, エラー |

**エンコーディング：**
- 新規作成時：BOM 付き UTF-8（`utf-8-sig`）— Excel での文字化け防止
- 既存ファイルへの追記時：BOM なし UTF-8（`utf-8`）— BOM の二重書き込み防止

---

## 実行環境

| 項目 | 内容 |
|---|---|
| 実行場所 | Docker コンテナ内（`docker exec -it scraper bash`） |
| 設定ファイル | `/app/input/config.json`（ホストの `./input/config.json` をマウント） |
| 出力先 | `/app/output/` 以下（ホストの `./output/` をマウント） |
| Python | 3.13 |
| Selenium | Remote WebDriver（`selenium/standalone-chrome` コンテナに接続） |
