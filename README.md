# price-tracker-bot

## 目錄

- [price-tracker-bot](#price-tracker-bot)
  - [目錄](#目錄)
  - [簡介](#簡介)
  - [如何在本機端使用](#如何在本機端使用)
    - [下載專案](#下載專案)
    - [建立 Python 環境](#建立-python-環境)
    - [建立 PostgreSQL](#建立-postgresql)
    - [建立 Telegram bot](#建立-telegram-bot)
    - [在本機端運行](#在本機端運行)
  - [更新](#更新)
      - [2022.11.12](#20221112)
      - [2022.09.13](#20220913)
  - [功能](#功能)
  - [Demo Bot](#demo-bot)
  - [環境建置](#環境建置)
    - [database](#database)
    - [環境變數](#環境變數)
    - [Telegram bot](#telegram-bot)
    - [Bot 接收訊息方式](#bot-接收訊息方式)
    - [fly.io](#flyio)
    - [Supabase (Free Postgres Online)](#supabase-free-postgres-online)
    - [heroku (免費方案即將關閉，建議遷移至flyio)](#heroku-免費方案即將關閉建議遷移至flyio)
  - [deploy](#deploy)
    - [Heroku git deploy](#heroku-git-deploy)
  - [執行方式](#執行方式)
    - [Build simple local postgres env (optional)](#build-simple-local-postgres-env-optional)
  - [機器人指令](#機器人指令)
    - [Command menu](#command-menu)

## 簡介

price-tracker-bot is a telegram bot that can trace the price on [momoshop](https://www.momoshop.com.tw "momoshop").

## 如何在本機端使用

### 下載專案

- 從 Github clone 此專案

```bash
git clone https://github.com/chen-tf/price-tracker-bot.git 
```

### 建立 Python 環境

- 安裝 Python，推薦版本 3.9
  - [python.org](https://www.python.org/)
- 在專案資料夾內，安裝相關套件
  - `pip install -r requirements.txt`

### 建立 PostgreSQL

- 安裝 Docker
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- 安裝 PostgreSQL 環境
  - 在專案資料夾內，執行 `docker-compose up`，創建並啟動 PostgreSQL 環境

### 建立 Telegram bot

- 加入 [Telegram](https://web.telegram.org/)
- 在對話視窗內呼叫 [@BotFather](https://t.me/botfather)，依照提示建立一個機器人，取得建立的 Telegram bot 的 Token
  - [Creating a new bot](https://core.telegram.org/bots/features#creating-a-new-bot)
  - Token Sample：`110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`

### 在本機端運行

- 在專案資料夾內建立一個檔名為 `.env` 檔案，內容如下
- 將 BOT_TOKEN 內容變更為建立 Telegram bot 時取得的 Token

```text
BOT_TOKEN = "{replace_me}"
DB_HOST = "localhost"
DB_NAME = "postgres"
DB_PASSWORD = "postgres"
DB_USER = "postgres"
DB_PORT = 5432
LOGGING_LEVEL = "INFO"
TELEGRAM_BOT_MODE = "polling"
```

- 在專案資料夾內執行檔案

```bash
python pt_scheduler.py
```

## 更新

#### 2022.11.12

一個夜晚突然無聊，想到如果我在 telegram bot 上面做 LINE Notify 的綁定，是不是會很有趣呢

- 新增 LINE 通知服務綁定 (目前 telegram bot 只能先支援 polling 的使用方式，為了要同時使用 flask web)

outage

- root case：同時間超過一個以上相同 telegram bot 使用 polling mode。
- fix：分別 deploy (telegram bot, flask web)
- impact：約莫早上五點至早上九點的降價服務倒站，既有資料不受影響，新資料都沒有建立成功。
- 後續動作：主動發送 telegram message 說明現況，請用戶再嘗試操作。
- 反思：恩...對，就是上面那個設定造成的，當初只是想要省錢不要開第二台機器，所以把對外的 port 讓給 LINE Notify
  Webhook，telegram bot 使用的是 polling mode，在後面部署階段的時候因為上面root case所述，所以造成期間內的telegram bot回覆異常。

#### 2022.09.13

[平臺即服務Heroku將在今年終止免費服務](https://www.ithome.com.tw/news/152729)

- 新增 fly.io 平台部署教學
- 新增 Supabase Database 申請

---

## 功能

- LINE 通知服務
  ![LINE 通知服務](https://i.imgur.com/DF9lOUR.jpg)
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

加入 [telegram botfather](https://t.me/botfather "telegram botfather")並建立一個機器人，取得 **token**
，後續須設定環境變數 **BOT_TOKEN**

### Bot 接收訊息方式

設定環境變數 **TELEGRAM_BOT_MODE**

- polling
  測試使用上方便，不需要對外網址，效能上較webhook差
- webhook
  如果要在local 測試 webhook，可使用 [ngrok](https://ngrok.com/ "ngrok")

### fly.io

- [Run a Python App](https://fly.io/docs/languages-and-frameworks/python/)
- [Install Flyctl and Login](https://fly.io/docs/languages-and-frameworks/python/#install-flyctl-and-login)
- [Inside fly toml](https://fly.io/docs/languages-and-frameworks/python/#inside-fly-toml)
- Procfile 一樣使用 `web: python3 app.py`
- fly postgres
  目前因為一些原因建議可以使用 Supabase Postgres

This is indeed a timeout due to the fact that Fly.io put HAproxy in front of the PostgreSQL instance, and the HAproxy
has a 30m timeout. (This was confirmed via email support with Fly.io)

This means you will either want to a make sure your PostgreSQL adapter can deal with (or automatically) reconnects, or
fire some kind of idle timer that runs a query at least once every 30 min, to keep the connection alive.

環境變數可以設定至 fly.toml 中

### Supabase (Free Postgres Online)

- https://supabase.com/
- [相關教學](https://flaviocopes.com/postgresql-supabase-setup/)

### heroku (免費方案即將關閉，建議遷移至flyio)

- [heroku application](https://devcenter.heroku.com/articles/creating-apps)
- [Heroku Postgres](https://devcenter.heroku.com/articles/heroku-postgresql)
- [Heroku config](https://devcenter.heroku.com/articles/config-vars) 設定heoku上環境變數
- [建立Heroku Scheduler(Optional)](https://devcenter.heroku.com/articles/scheduler)

如果是使用免費方案，服務太久沒有收到request，就會被暫時關閉，如果要長時間維持服務，需要定時發送一些request保持服務運作。
Scheduler新增`curl --location --request GET 'https://{AppName}.herokuapp.com'`，把AppName替換成Heroku上建立的application
name

![預期中的Add-ons](https://i.imgur.com/s1Et0bz.png)

### Linter

使用 [isort](https://github.com/PyCQA/isort) (sort imports)

```bash
# cheat
echo "$(git diff --name-only --diff-filter=ACMR HEAD *.py)" | xargs isort

# usage - never use
isort **/*.py
```

使用 [black](https://github.com/psf/black) (formatter)

```bash
# cheat
echo "$(git diff --name-only --diff-filter=ACMR HEAD *.py)" | xargs black

# find py file which place would be reformatted 
echo "$(git diff --name-only --diff-filter=ACMR HEAD *.py)" | xargs black --diff

# use black for specific file
black foo.py

# usage - never use, it will reformat py file at all
black *.py
```

使用 [pylint](https://github.com/PyCQA/pylint) (lint)

```bash
# cheat
echo "$(git diff --name-only --diff-filter=ACMR HEAD *.py)" | xargs pylint -sn

# usage - never use, cause too many output
pylint *.py
```

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
