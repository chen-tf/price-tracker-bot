# price-tracker-bot

[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/PyCQA/pylint)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

## 目錄

- [price-tracker-bot](#price-tracker-bot)
  - [目錄](#目錄)
  - [簡介](#簡介)
    - [Demo Bot](#demo-bot)  
  - [功能](#功能)
  - [如何在本機端使用](#如何在本機端使用)
    - [下載專案](#下載專案)
    - [建立 Python 環境](#建立-python-環境)
    - [建立 PostgreSQL](#建立-postgresql)
    - [建立 Telegram bot](#建立-telegram-bot)
    - [在本機端運行](#在本機端運行)
  - [環境建置](#環境建置)
    - [database](#database)
    - [環境變數](#環境變數)
    - [Telegram bot](#telegram-bot)
    - [Bot 接收訊息方式](#bot-接收訊息方式)
    - [fly.io](#flyio)
    - [Supabase (Free Postgres Online)](#supabase-free-postgres-online)
  - [執行方式](#執行方式)
    - [Build simple local postgres env (optional)](#build-simple-local-postgres-env-optional)
  - [機器人指令](#機器人指令)
    - [Command menu](#command-menu)
  - [如何貢獻](#如何貢獻)
  - [貢獻作者](#貢獻作者)
  - [授權條款](#授權條款)

## 簡介

price-tracker-bot is a telegram bot that can trace the price on [momoshop](https://www.momoshop.com.tw "momoshop").

### Demo Bot

Telegram bot search [@momo_price_tracker_bot](https://t.me/momo_price_tracker_bot)

## 功能

- LINE 通知服務<br>
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
python app.py
```

### 新建立的Telegram聊天頻道中已有的內建指令
```
/my 顯示追蹤清單
/clearall 清空全部追蹤清單
/clear 刪除指定追蹤商品
/add 後貼上momo商品連結可加入追蹤清單或是可以直接使用指令選單方便操作
```

---

## 環境建置

### Database

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
| WEBHOOK_URL(Optional) | For deploy your app to cloud provides |
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

### pre-commit  
  
確認 pre-commit 是否已安裝至專案環境底下  
  
```bash  
# check  
pre-commit -V  
  
# install with requirements.txt  
pip install -r requirements.txt  
  
# or directly install 
pip install pre-commit  
```  
  
將 pre-commit hook 安裝至專案裡的 .git/hooks 資料夾底下  
  
```bash  
# init hook, will create .git/hooks/pre-commit  
pre-commit install --install-hooks  
```  
  
執行 git commit  
  
```bash  
git commit -m 'feat: hello world'
```  

成功時畫面如下  
  
![succeful-pre-commit](https://i.imgur.com/1TNS07R.gif)  
  
失敗時，需要調整相對應的檔案，並重新將檔案加入 git 版控，再重新進行 commit  
  
![fail-pre-commit](https://i.imgur.com/Zo0RBxo.gif)

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

## 如何貢獻

歡迎所有貢獻、提交錯誤報告、協助錯誤修復、文檔改進、功能增強和提供你的想法。

你可以移至"Issue"選項並開始查看你認為有趣的問題。文檔下列出了許多問題，您可以從這裡開始。

或者，您有了自己的想法，或者正在程式碼中尋找某些東西並認為“這可以改進”……您可以為此做點什麼！

作為本項目的貢獻者和維護者，您應該遵守 price-tracker-bot 的行為準則。

## 貢獻作者
* chen-tf
* ken71301
* PayonAbyss
* s9891326
* henry-on-the-internet
* hokou
* w305jack

## 授權條款
[MIT](https://github.com/henry-on-the-internet/price-tracker-bot/blob/main/license) 
