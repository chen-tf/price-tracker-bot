from flask import Flask

import pt_config

app = Flask(__name__)

# 關閉追蹤各種改變的信號
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_DATABASE_URI'] = \
#     f"postgresql://{pt_config.DB_USER}:{pt_config.DB_PASSWORD}@{pt_config.DB_HOST}:5432/{pt_config.DB_NAME}"
app.config['SQLALCHEMY_DATABASE_URI'] = \
    f"postgresql://{pt_config.DB_USER}:{pt_config.DB_PASSWORD}@{pt_config.DB_HOST}:5432/test"

# 開啟可以看對應的sql語法
# app.config['SQLALCHEMY_ECHO'] = True
app.config['SQLALCHEMY_POOL_SIZE'] = 8
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 3
