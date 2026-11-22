# Cloudflare 免費方案服務

正式 bot：[@momo_price_tracker_bot](https://t.me/momo_price_tracker_bot)

## 架構與修復

Telegram → Cloudflare Workers → D1。Cloudflare Cron 每分鐘處理到期商品與通知，不依賴常駐 VM、Supabase、GitHub 定時排程、Browser Run 或付費代理。

原 Supabase 正式庫暫停、GitHub 查價 workflow 因不活躍停用；Fly 健康檢查只回固定 OK，無法判斷業務是否正常。momo 403 經固定出口逐項比較，確認 `User-Agent: price-tracker-bot/1.0` 可讓 Workers 原生 fetch 直接取得價格與庫存。詳見 [header 對照證據](docs/momo-headers-2026-11-22.md)。

## Telegram 功能

- `/start`、`/help`：指令說明。
- `/price 商品網址`：當下查詢 momo 名稱、售價與庫存，不變更追蹤或加入時價格。
- `/add 商品網址` 或直接貼網址：以當下價格加入追蹤；支援舊 i_code、新 /product/ID 與 momo.dm 分享轉址。
- `/my`：顯示原有追蹤清單、最後紀錄價格與加入時價格。
- `/clear`、`/clearall`、`/cancel`：刪除或取消操作。

每位使用者最多追蹤 20 件商品；私人清單與刪除限定本人。LINE Notify 已於 2025-03-31 終止，`/line` 說明改用 Telegram。

正常商品每四小時重新到期，每分鐘最多批次處理 10 件。排程優先處理指令與待送通知，查價與訊息投遞分開執行以控制免費 CPU 預算；積壓、錯誤或大量指令會延長實際間隔，負載超過能力時不自動升級方案。

同一商品換過 momo 編號時，讀取公開商品頁的結構化資料，驗證 offer URL 後取得新編號，再以新編號呼叫即時價格與庫存 API；對應存入 `source_id`，保留原追蹤主鍵與個人基準價。排程每批最多解析一次新舊編號，避免少數異常資料耗盡免費 subrequests。

價格改變且低於該使用者加入時價格便通知；缺貨轉有貨也通知。momo 明確回覆「查無商品」時保留原價格、清單與基準價，標示無法取得並改每日批次重試；確認下架的商品若仍回傳空名稱與 0 元，不逐件重查庫存，重新出現有效價格時才恢復正常查價。其他抓價錯誤也不會以 0 覆蓋舊價。

## 舊資料

2026-11-22 已免費恢復原 Supabase，使用同一個唯讀 snapshot 匯出三表，匯入 D1 並逐筆比對全部遷移欄位一致：

| 表 | 全部 | 啟用 |
| --- | ---: | ---: |
| user | 2698 | 1709 |
| good_info | 5020 | 1710 |
| user_sub_good | 5771 | 1859 |

保留原 ID、Telegram chat ID、商品、追蹤基準價、庫存、狀態與時間。已終止的 LINE token 與未使用 checksum 不匯入。歷史異常商品 ID 保留原主外鍵，只於抓價與連結轉成正常商品編號。

私人備份與核對報告在被 Git 忽略的 `backups/`，匯入 SQL 為 `import.sql`；不得提交或放入 CI artifact。`scripts/convert_backup.py` 檢查本機 CSV 的型別、唯一鍵、外鍵與筆數，通過後產生權限 0600 的 SQL，僅限全新資料庫，不可重複匯入正式 D1。

原 Supabase 保留作為復原來源，正式 bot 不再讀寫它；若原專案日後自動暫停，不會影響新服務。

補查效率與實際額度紀錄：[2026-11-22 實測](docs/refresh-efficiency-2026-11-22.md)。

## 免費額度與可靠性

- Cloudflare 帳號保持 **Workers Free**：每日 100,000 requests，10ms CPU／次、50 subrequests／次。超額會拒絕服務，不啟用付費方案。
- D1 Free：每日 5,000,000 rows read、100,000 rows written；每 DB 500MB。本次匯入約寫入 49,311 rows。
- 不綁定 Browser Run，不消耗其每日 10 分鐘額度。
- GitHub Actions 僅負責公開 repo 標準免費 runner 的 CI/CD 與手動診斷；正式查價不依賴 GitHub 排程，因此沒有 60 天不活躍停用問題。
- Cron 查價每批 10 件，以單次價格 API 搭配最多四個並行庫存請求，移除固定等待；相同來源商品共用庫存請求。已知下架商品只需批次價格請求。通知分鐘最多發三則，該分鐘不查價。
- 每批有效價格與通知使用兩句 SQL，在同一 D1 transaction 提交；下架與錯誤各一句。這減少 SQL 準備、讀取與往返，不代表計費 rows written 同比下降。手動補查會記錄實際 rows read／written。

Webhook 先持久化再 ACK，重送去重。價格與 outbox 通知同 D1 batch 原子提交，過期或重送資料不重複建立提醒。Telegram 429／暫時錯誤重試，403 停用已封鎖 bot 的使用者與追蹤。Telegram sendMessage 沒有冪等鍵，接收成功但本地成功紀錄遺失時，仍可能重複發送。

更新最多自動處理十次，未完成仍留待調查。已完成更新與已送通知保留七天，每小時清理一次。大量復原通知會分批消化，指令回覆優先。

`GET /health` 可查看最後查價成功時間、查無商品數、失敗商品、過期商品與積壓量，不回傳私人資料。HTTP 200 只代表 D1 可用，仍須檢查最後成功時間與失敗數。免費服務與 momo 公開介面可能調整，無法保證永不暫停。

## 開發、測試與部署

需要 Node.js 24、Python 3.9+：

```bash
cd cloudflare
npm ci
npm test
python3 -m unittest discover -s test -p 'test_*.py'
npm run db:local
npm run check
node scripts/refresh_prices.mjs --probe
```

測試包含真實 workerd／D1 的價格與通知提交、Webhook 驗證、私人清單、個別基準價、重送／過期資料、即時查價不改追蹤、缺貨／降價、通知重試與封鎖用戶停用。

`.dev.vars.example` 複製為 `.dev.vars` 後安全填入憑證，禁止輸出到命令列、Git 或 CI 紀錄。Worker secrets：`BOT_TOKEN`、`WEBHOOK_SECRET`；`SYNC_SECRET` 供選用的手動補跑同步，正式 Cron 不需要外部 token。

D1 已建立並綁定在 `wrangler.jsonc`。部署：

```bash
npm run db:remote
npm run deploy
```

首次上線需先核對匯入資料，部署後確認 health 與未授權端點回 401；Telegram webhook 設為 Worker `/webhook`、附 secret_token，保留 pending updates。

## CI/CD 與手動維運

`.github/workflows/cloudflare.yml` 在相關 PR／main push 測試、套用本機 migrations、dry-run；main 手動 dispatch 才部署。使用 `cloudflare-production` environment 的 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`。首次建立 D1、匯入資料與 webhook 切換不隨 push 自動執行。

`.github/workflows/cloudflare-refresh.yml` 只提供手動維運：預設 connectivity 讀公開測試商品；headers 執行 header 對照；refresh 只補到期商品，retry-errors 只重試實際錯誤，full-refresh 才全量補跑。透過 repository secrets `WORKER_URL`、`SYNC_SECRET` 同步，每 100 件共用價格請求、每 20 件提交 D1；正常補查不重跑尚未到期商品。不啟用舊排程。

Fly 舊應用 `price-tracker` 已刪除，確認 0 台機器且無 Volume。原 Fly 部署、查價及 Python checks 改為手動，避免 push 啟動舊環境或重設 webhook。舊 Supabase 與本機備份不刪除。回復舊環境前需處理 D1 上線後新增資料，不可直接覆蓋。

參考：[Workers limits](https://developers.cloudflare.com/workers/platform/limits/)、[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)、[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。
