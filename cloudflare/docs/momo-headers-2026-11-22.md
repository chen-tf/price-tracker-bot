# momo HTTP 403 的 header 對照實驗

日期：2026-11-22。測試對象為公開商品 4811545 的價格 API，固定 POST URL、JSON body、Content-Type、執行環境與出口；每一個案例只更換表列 header，沒有使用會員 cookie 或 token。

`POST https://www.momoshop.com.tw/api/moecapp/getInstantGoodsStatus`

| 只調整的 header | Cloudflare Worker | GitHub Ubuntu runner |
| --- | ---: | ---: |
| 預設 | 403 | 403 |
| User-Agent: Chrome desktop | 403 | 200，有效價格 |
| User-Agent: node | 403 | 403 |
| User-Agent: curl/8.7.1 | 403 | 403 |
| User-Agent: Python-urllib/3.9 | 403 | 403 |
| User-Agent: price-tracker-bot/1.0 | 200，有效價格 | 200，有效價格 |
| version: 999999 | 403 | 403 |
| Accept: application/json, text/plain, */* | 403 | 403 |
| Accept-Language: zh-TW,zh;q=0.9,en-US;q=0.8 | 403 | 403 |
| Origin: https://www.momoshop.com.tw | 403 | 403 |
| Referer: https://www.momoshop.com.tw/product/4811545 | 403 | 403 |
| Sec-Fetch-Site / Mode / Dest | 403 | 403 |

GitHub 原始紀錄：[固定 runner 的對照測試](https://github.com/chen-tf/price-tracker-bot/actions/runs/44991707239)。可用 `scripts/header_matrix.mjs` 重新執行，僅讀公開商品資料。

在 Cloudflare 原生 fetch 改用可識別此專案的 `price-tracker-bot/1.0` 後，又連續三次成功取得商品名稱、價格 1111 與庫存 1。正式程式對價格與庫存 API 都加上此 User-Agent，不需要瀏覽器、會員 cookie、付費代理或 Supabase 中繼。

結論是 **User-Agent 在這次固定出口實驗中具有決定性影響**。不能推論 momo 的所有封鎖只依賴一個 header：例如同一 Chrome UA 在 Cloudflare 與 GitHub 的結果不同，表示出口／HTTP 或 TLS 特徵等仍可能參與風險判斷。未取得 momo 的 WAF 規則，因此不宣稱知道其全部內部判定邏輯。區域測試曾在 Supabase 東京、新加坡、美東均成功，沒有證據支持這次必須切換區域；那些臨時中繼不作為正式依賴。
