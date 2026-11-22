# 免費方案服務復原

正式 bot：[@momo_price_tracker_bot](https://t.me/momo_price_tracker_bot)

## 架構與原因

Telegram → Cloudflare Workers → D1。Cloudflare Cron 每分鐘處理待辦與通知，並每四小時啟動一次公開 GitHub repository 的標準免費 Actions runner 查價。Runner 使用 Node.js 呼叫 momo 公開價格與庫存 API，透過具獨立 secret 的內部端點上傳；不需 momo 會員帳號或 cookie。

Workers 的直接 HTTP 出口被 momo 回覆 403。Browser Run 可以讀商品頁，但 Free 每日只有 10 分鐘，無法負擔原有商品量每四小時全量查價。因此批次查價使用公開 repo 免費 Actions，Browser Run 只處理新增商品，應用程式每日限制 9 分鐘並預留每次呼叫額度，額度不足時提示稍後重試。

保留 `/start`、`/add`、貼網址、`/my`、`/clear`、`/clearall`、`/cancel`；私人清單限定本人，最多追蹤 20 件商品。價格變更且低於加入時價格會通知；缺貨轉有貨也通知。抓價失敗保留原價格，下一輪重試。LINE Notify 已於 2025-03-31 終止，`/line` 說明改用 Telegram。

## 舊資料

2026-11-22 已免費恢復暫停的正式 Supabase，單一唯讀 snapshot 匯出三表，匯入新 D1 並逐筆比對全部遷移欄位一致：

| 資料表 | 全部 | 啟用 |
| --- | ---: | ---: |
| user | 2698 | 1709 |
| good_info | 5020 | 1710 |
| user_sub_good | 5771 | 1859 |

保留原 ID、Telegram chat ID、價格、追蹤基準價、庫存、狀態與時間。已終止的 LINE token 和未使用 checksum 不遷移。歷史異常商品 ID 的主外鍵也保留，查價時轉為正常商品編號。

備份、核對報告與匯入 SQL 存於被 Git 忽略的 `backups/`、`import.sql`；內含私人資料，不得提交或放入 CI artifact。`scripts/convert_backup.py` 僅處理本機 CSV，檢查外鍵與型別後產生權限 0600 的 SQL，僅適用全新資料庫；不要重複匯入正式 D1。

## 免費額度

- Cloudflare 必須維持 **Workers Free**，超額會拒絕服務；不升級、不購買代理服務。
- Workers：每日 100,000 requests，10ms CPU／次、50 subrequests／次。
- D1：每日 5,000,000 rows read、100,000 rows written；每 DB 500MB。本次匯入約寫入 49,311 rows。
- Browser Run：帳號每日 10 分鐘；本程式保守限制 9 分鐘，其他使用同帳號的應用程式會共用額度。
- GitHub Actions：repository 必須保持 public，使用標準 `ubuntu-latest` runner。改 private 或 larger runner 前須重新評估費用。
- Actions 沒有使用 `schedule`，由 Cloudflare dispatch，避免原定時工作因 repo 60 天沒有活動而停用。
- 免費服務與 momo 公開 API 都可能限流或調整，無法保證永不暫停。`/health` 的最後查價時間、失敗商品、積壓量及 dispatch error 用於檢查。

## 可靠性

Webhook 先寫 D1 再 ACK，重送不重複處理。批次價格與 outbox 通知原子提交，過期或重送上傳不重複建立通知；加入時價格維持各使用者原始基準。

指令回覆優先於價格通知。Telegram 429／暫時錯誤重試，403 停用已封鎖 bot 的使用者與追蹤。通知為至少一次發送：Telegram 已接收但成功紀錄未寫入時，仍可能重複。每分鐘最多處理一筆更新、六則訊息，積壓會逐步消化。更新最多自動處理十次，未完成資料留待調查。已送通知、已完成更新與 dispatch 工作保留七天。

`GET /health` 不含私人資料；`last_price_success` 過舊、`stale_products` 或 `failed_products` 大於零表示查價不完整，HTTP 200 僅代表資料庫可用。

## 本機驗證與部署

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

複製 `.dev.vars.example` 到 `.dev.vars`，透過安全輸入填入 secrets；不要印在命令、Git 或 CI 日誌。`npm run check` 只打包，`db:local` 只改本機 D1。

正式 D1 已建立，`wrangler.jsonc` 綁定 `price-tracker`。Worker secrets：

| Secret | 用途 |
| --- | --- |
| BOT_TOKEN | 正式 Telegram bot |
| WEBHOOK_SECRET | Telegram webhook header 驗證 |
| SYNC_SECRET | Runner 與 Worker 的獨立同步憑證 |
| GITHUB_TOKEN | 僅此 repo 的 Actions write，用於 dispatch |

GitHub repository secrets：`WORKER_URL`、`SYNC_SECRET`。

```bash
npm run db:remote
npm run deploy
```

部署後先確認 health、內部端點未授權回 401，執行 GitHub `Refresh prices on Cloudflare` 的 probe，再跑完整查價。確認資料可讀後設定 Telegram webhook `/webhook` 與 `secret_token`，保留 pending updates。使用原帳號驗證 `/start`、`/my`、新增與刪除。

## CI/CD 與回復

`.github/workflows/cloudflare.yml` 在相關 PR／main push 執行測試、本機 migrations、dry-run；main 手動 dispatch 才部署，使用 `cloudflare-production` environment 的 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_API_TOKEN`。首次建立 D1、匯入資料與 webhook 切換不隨 push 自動執行。

`.github/workflows/cloudflare-refresh.yml` 由 Cloudflare 每四小時 dispatch，也可手動執行；`probe=true` 僅測試公開商品，不讀寫使用者資料。禁止同時啟用舊排程。

原 Fly 部署與查價 workflows 已改為手動，以免 push 重設 webhook。原 Supabase 保留，回復前須先處理 D1 上線後新增資料，不能直接用舊備份覆蓋。舊 webhook 設定含 token，只保存在本機私人備份。舊 Fly 資源若仍運行需另外停止，不能只因新架構免費便假設舊帳單已歸零。

參考：[Workers limits](https://developers.cloudflare.com/workers/platform/limits/)、[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)、[Browser Run pricing](https://developers.cloudflare.com/browser-rendering/pricing/)、[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。
