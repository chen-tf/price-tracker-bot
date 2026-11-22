# price-tracker-bot

Telegram momo 降價與補貨通知：[@momo_price_tracker_bot](https://t.me/momo_price_tracker_bot)。

正式服務使用 **Cloudflare Workers Free + D1 Free + Cron**，不需要常駐主機、付費代理或 Supabase。舊使用者與追蹤清單已遷移保留。部署、免費額度、維運與資料復原請見 [Cloudflare 說明](cloudflare/README.md)。

## 正式功能

- `/price 商品網址`：即時查詢價格與庫存，不改變追蹤基準價。
- `/add 商品網址` 或直接貼網址：加入追蹤，每人最多 20 件。
- `/my`：查看私人清單、最後紀錄價格與加入時價格。
- `/clear`：選擇移除商品；`/clearall`：清空；`/cancel`：取消操作。
- 商品降價且低於個人基準價、缺貨轉有貨時以 Telegram 通知。

LINE Notify 已於 2025-03-31 終止；Fly 應用與部署流程已移除。原 Supabase 僅保留作復原來源。

## Cloudflare 開發

使用 Node.js 26 LTS 與 Python 3.15（離線備份轉換工具）。

```bash
cd cloudflare
npm ci
npm run db:local
npm run dev
```

將 `.dev.vars.example` 複製成 `.dev.vars` 並在本機填入測試 bot 的 secrets。不要使用正式 bot 做本機 polling，也不要提交 secrets、資料匯出、私人備份或測試報告。

## 選用 Python 程式

Python 程式保留作本機開發與 PostgreSQL repository 範例；正式 Cloudflare 服務不依賴它。使用 **Python 3.15.2** 與 Pipenv 2026.11.0；所有依賴版本固定於 `Pipfile.lock`。

```bash
python -m pip install pipenv==2026.11.0
pipenv sync --dev
```

以獨立測試 bot 與本機 PostgreSQL 設定 `.env`，環境變數如下：

| 變數 | 用途 |
| --- | --- |
| BOT_TOKEN | 本機測試 bot token |
| DB_HOST、DB_NAME、DB_USER、DB_PASSWORD、DB_PORT | 本機 PostgreSQL，port 預設 5432 |
| TELEGRAM_BOT_MODE | `polling`（預設）或 `webhook` |
| WEBHOOK_SECRET | webhook 模式必填，與 Telegram secret_token 一致 |
| PORT | Flask port，預設 8080 |
| LOGGING_LEVEL | logging level |

```bash
docker compose up -d
pipenv run python app.py
```

Docker Compose 只供本機新資料庫，使用 PostgreSQL 18；資料存放於 `postgres-data-18/`。舊 `postgres-data/` 保留，不能直接掛載成新 major 的資料目錄，需先備份並以 PostgreSQL 官方升級流程處理。

Python webhook 為 `POST /webhook`，驗證 `X-Telegram-Bot-Api-Secret-Token`；不再將 bot token 放進 URL。匯入模組不會註冊 webhook 或啟動背景執行緒；啟用 webhook 與對外 TLS 由操作者明確設定。本機 polling 會變更該 bot 的接收模式，務必使用獨立 bot。

Python 支援原有追蹤與公開 API 查價；新舊商品編號自動對應、`/price` 與可靠 outbox 屬正式 Cloudflare 實作。

## 品質與安全

PR CI 執行完整 Python（含隔離 PostgreSQL container）與 Cloudflare workerd／D1 回歸測試、格式檢查、Pylint errors 與 pip-audit；測試使用合成設定，不讀取開發者 `.env`。本機可針對變更選跑測試：

```bash
pipenv run pytest tests/test_momo_security.py tests/test_python_runtime.py
cd cloudflare
node --test --test-name-pattern='same-user|observations stay' test/worker.test.js
```

使用 Black 與 isort 統一格式，設定在 `pyproject.toml`。Dependabot 每週檢查 Python、npm 與 GitHub Actions；Actions 固定 commit SHA。GitHub 公開儲存庫使用免費 CodeQL、secret scanning 與 push protection。請勿將私人資料或憑證放入 issue、PR、CI log 或 artifact。

## 授權

[MIT](LICENSE)
