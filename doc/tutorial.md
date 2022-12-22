### 使用Flask-Migrate
1. 安裝Flask-Migrate
    ```shell
    pip install Flask-Migrate
    ```
2. 初始化migrations資料夾
    ```shell
    flask --app repository/models.py db init
    ```
3. 根據db.Model的結構產生對應的SQL語法
   - 會在`migrations/versions/`底下創建一個.py檔案(如下圖的7dca07870a72_.py)
   - 也會在DB創建alembic_version表，用來記錄當前的version版本(7dca07870a72)
    ```shell
    flask --app repository/models.py db migrate -m "init"
    ```
4. 更新到DB
    - 觸發7dca07870a72_.py內的upgrade()，新增該table
    - alembic_version表也會把該version記錄起來
    ```shell
    flask --app repository/models.py db upgrade
    ```
5. 後悔了(降版)
    - 觸發7dca07870a72_.py內的downgrade()，刪除該table
    ```shell
    flask --app repository/models.py db downgrade
    ```
   
### 特殊情境
- migrations/version底下已經有對應的版本了
  ```shell
  flask --app repository/models.py db upgrade
  ```
- 一直migrate出不來可以用以下的方式試試看
  ```shell
  flask --app repository/models.py db stamp head
  flask --app repository/models.py db migrate
  flask --app repository/models.py db upgrade
  ```

### 參考
- [flask設定sql的參數](https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/)
- [官方flask-migrate教學](https://flask-migrate.readthedocs.io/en/latest/)
- https://hackmd.io/@shaoeChen/r1luGOkVf?type=view#tags-flask-flask_ext-python
- https://medium.com/seaniap/python-web-flask-%E5%AF%A6%E4%BD%9C-flask-migrate%E6%9B%B4%E6%96%B0%E8%B3%87%E6%96%99%E5%BA%AB-a5ebc930422a