## 簡介
price-tracker-bot is a telegram bot that can trace the price on [momoshop](https://www.momoshop.com.tw "momoshop").

---

## 功能

- 降價通知
![降價通知](https://i.imgur.com/CSLhRGW.png)
- 上架通知
![上架通知](https://i.imgur.com/jmfC9aH.png)
- 收藏商品
![收藏商品](https://i.imgur.com/Ns9uGiA.png)
- 清空已收藏商品
![清空已收藏商品](https://i.imgur.com/kVwJVri.png)
- 顯示目前已收藏商品
![顯示目前已收藏商品](https://i.imgur.com/l8dgUpj.png)

---
## Demo Bot
Telegram bot search [@momo_price_tracker_bot](https://t.me/momo_price_tracker_bot)

---


## 環境建置
### database
- PostgreSQL 10<br>

執行 sqls folder底下放置的SQL file，或者可以自行使用其他db migration 工具
### 環境變數


| 環境變數              | 說明                                                                |
| --------------------- | ------------------------------------------------------------------- |
| DB_HOST               | Database host                                                       |
| DB_NAME               | Database name                                                       |
| DB_USER               | Database user                                                       |
| DB_PASSWORD           | Database user's password                                            |
| BOT_TOKEN             | Telegram bot token                                                  |
| WEBHOOK_URL(Optional) | If you use Heroku url like this **https://{AppName}.herokuapp.com** |
| PERIOD_HOUR                      | Resync latest good's price time period                                                                  |
| TELEGRAM_BOT_MODE     | default: polling, [polling,webhook]                                 |

### Telegram bot
加入 [telegram botfather](https://t.me/botfather "telegram botfather")並建立一個機器人，取得 **token**，後續須設定環境變數 **BOT_TOKEN**

### Bot 接收訊息方式
設定環境變數 **TELEGRAM_BOT_MODE**
- polling
測試使用上方便，不需要對外網址，效能上較webhook差
- webhook
如果要在local 測試 webhook，可使用 [ngrok](https://ngrok.com/ "ngrok")

### heroku
- [heroku application](https://devcenter.heroku.com/articles/creating-apps)
- [Heroku Postgres](https://devcenter.heroku.com/articles/heroku-postgresql)
- [Heroku config](https://devcenter.heroku.com/articles/config-vars) 設定heoku上環境變數
- [建立Heroku Scheduler(Optional)](https://devcenter.heroku.com/articles/scheduler)

如果是使用免費方案，服務太久沒有收到request，就會被暫時關閉，如果要長時間維持服務，需要定時發送一些request保持服務運作。
Scheduler新增`curl --location --request GET 'https://{AppName}.herokuapp.com'`，把AppName替換成Heroku上建立的application name

![預期中的Add-ons](https://i.imgur.com/s1Et0bz.png)



---

## deploy

### Heroku git deploy
![](https://i.imgur.com/iqFrHLC.png)

---


## 執行方式
`python3 App.py`

### Build simple local postgres env (optional)

```
docker run -d -p 5432:5432 --name mypostgres --restart always -v postgresql-data:/var/lib/postgresql/data -e POSTGRES_PASSWORD=1234 -d postgres:10.17-alpine3.14
```

---

## 機器人指令
<br>對話輸入momo商品網址可直接加入追蹤
- /start 顯示目前所支援的指令
- /my 顯示目前所有追蹤物品清單，以及當下所記錄價格
- /clear 清除目前所有追蹤物品清單

### Command menu
You need to say these to @BotFather.
![](https://i.imgur.com/nskbZPo.png)

Bot can show command menu
![](https://i.imgur.com/aEHJECc.png)
