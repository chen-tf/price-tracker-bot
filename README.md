price-tracker-bot is a telegram bot that can trace the price on [momoshop](https://www.momoshop.com.tw "momoshop").

### 環境建置
#### database
使用Postgres，需要設定的環境變數如下
- DB_HOST
- DB_NAME
- DB_USER
- DB_PASSWORD
執行 sqls folder底下放置的SQL file，或者可以自行使用其他db migration 工具

#### telegram bot
加入 [telegram botfather](https://t.me/botfather "telegram botfather")並建立一個機器人，取得 **token**，後續須設定環境變數 BOT_TOKEN

#### bot 運作模式
設定環境變數 **TELEGRAM_BOT_MODE**
- polling
測試使用上方便，不需要對外網址，效能上較webhook差
- webhook
如果要在local 測試 webhook，可使用 [ngrok](https://ngrok.com/ "ngrok")

#### heroku
安裝heroku cli
1. `heroku login`


### 執行方式
`python3 App.py`

### 機器人指令
- /start 顯示目前所支援的指令
- /my 顯示目前所有追蹤物品清單，以及當下所記錄價格
- /clear 清除目前所有追蹤物品清單