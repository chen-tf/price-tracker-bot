import enum
import uuid

import sqlalchemy as db
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from repository.IntEnum import IntEnum
from repository.database import Base


class GoodInfoState(enum.IntEnum):
    DISABLE = 0
    ENABLE = 1


class GoodInfoStockState(enum.IntEnum):
    OUT_OF_STOCK = 0
    IN_STOCK = 1
    NOT_EXIST = 2


class GoodInfo(Base):
    __tablename__ = "good_info"

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=True)
    price = db.Column(db.BigInteger)
    create_time = db.Column(db.DateTime, server_default=func.now())
    update_time = db.Column(db.DateTime, onupdate=func.now())
    checksum = db.Column(db.String(16), nullable=True)
    stock_state = db.Column(IntEnum(GoodInfoStockState), default=GoodInfoStockState.IN_STOCK,
                            comment="0: out of stock\n1: in stock")
    state = db.Column(IntEnum(GoodInfoState), default=GoodInfoState.ENABLE)

    def __repr__(self):
        return f"GoodInfo<{self.id=}, {self.name=}, {self.price=}, {self.stock_state=}>"


class UserState(enum.IntEnum):
    DISABLE = 0
    ENABLE = 1


class User(Base):
    __tablename__ = "user"
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
    state = db.Column(IntEnum(UserState), default=UserState.ENABLE)
    line_notify_token = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"User<{self.id=}, {self.chat_id=}, {self.state=}>"


class UserSubGoodState(enum.IntEnum):
    DISABLE = 0
    ENABLE = 1


class UserSubGood(Base):
    __tablename__ = "user_sub_good"
    # __table_args__ = (
    #     db.Index('user_sub_good_good_id_idx', "good_id", "price"),
    #     db.Index('user_sub_good_un', "user_id", "good_id", unique=True)
    # )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.String, db.ForeignKey("user.id"))
    good_id = db.Column(db.String, db.ForeignKey("good_info.id"))
    price = db.Column(db.BigInteger)
    create_time = db.Column(db.DateTime, server_default=func.now())
    update_time = db.Column(db.DateTime, onupdate=func.now())
    is_notified = db.Column(db.Boolean, default=False)
    state = db.Column(IntEnum(UserSubGoodState), default=UserSubGoodState.ENABLE,
                      comment="0: disable\n1: enable")
    good_info = relationship('GoodInfo', backref='user_sub_goods', foreign_keys=[good_id], lazy="joined")

    def __repr__(self):
        return f"UserSubGood<{self.id=}, {self.price=}>"
