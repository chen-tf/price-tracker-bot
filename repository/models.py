import uuid

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from app import app

db = SQLAlchemy(app)
migrate = Migrate(app, db, compare_type=True)


class GoodInfo(db.Model):
    __tablename__ = 'good_info'

    STOCK_STATE_OUT_OF_STOCK = 0
    STOCK_STATE_IN_STOCK = 1
    STOCK_STATE_NOT_EXIST = 2
    STATE_DISABLE = 0
    STATE_ENABLE = 1

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=True)
    price = db.Column(db.BigInteger)
    create_time = db.Column(db.DateTime, server_default=func.now())
    update_time = db.Column(db.DateTime, onupdate=func.now())
    checksum = db.Column(db.String(16), nullable=True)
    stock_state = db.Column(db.Integer, default=1, comment='0: out of stock\n1: in stock')
    state = db.Column(db.Integer, default=1)

    def __init__(self, good_id: str, price: int, name: str, stock_state: int = 1) -> None:
        self.id = good_id
        self.price = price
        self.name = name
        self.stock_state = stock_state

    def __repr__(self):
        return f"GoodInfo<{self.id=}, {self.name=}, {self.price=}, {self.stock_state=}>"


class User(db.Model):
    __tablename__ = 'user'
    # __table_args__ = (
    #     db.Index(
    #         'user_state_enable_ix',
    #         "id", "chat_id",
    #         postgresql_where=db.Column("state")),
    # )

    id = db.Column(db.String, primary_key=True)
    chat_id = db.Column(db.String)
    create_time = db.Column(db.DateTime, server_default=func.now())
    update_time = db.Column(db.DateTime, onupdate=func.now())
    state = db.Column(db.Integer, default=1)
    line_notify_token = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"User<{self.id=}, {self.chat_id=}>"


class UserSubGood(db.Model):
    __tablename__ = 'user_sub_good'
    __table_args__ = (
        db.Index('user_sub_good_good_id_idx', "good_id", "price"),
        db.Index('user_sub_good_un', "user_id", "good_id", unique=True)
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String, db.ForeignKey('user.id'))
    good_id = db.Column(db.String, db.ForeignKey('good_info.id'))
    price = db.Column(db.BigInteger)
    create_time = db.Column(db.DateTime, server_default=func.now())
    update_time = db.Column(db.DateTime, onupdate=func.now())
    is_notified = db.Column(db.Boolean, default=False)
    state = db.Column(db.Integer, default=1, comment='0: disable\n1: enable')

    def __repr__(self):
        return f"UserSubGood<{self.id=}, {self.price=}>"
