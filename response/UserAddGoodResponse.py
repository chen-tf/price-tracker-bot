import inspect
from dataclasses import dataclass
from typing import Type

import pt_config
import pt_error
from repository import UserSubGood
from repository.models import GoodInfoStockState

error_message: dict[Type[pt_error.Error], str] = {
    pt_error.GoodNotExist: "商品目前無展售或是網頁不存在",
    pt_error.CrawlerParseError: "商品頁面解析失敗",
    pt_error.EmptyPageError: "商品頁面解析失敗",
    pt_error.ExceedLimitedSizeError: f"追蹤物品已達{pt_config.USER_SUB_GOOD_LIMITED}件",
    pt_error.NotValidMomoURL: "無效momo商品連結"
}

default_error_message = "Something wrong...try again."


@dataclass
class UserAddGoodResponse(Exception):
    user_sub_good: UserSubGood
    error: Type[pt_error.Error]

    @staticmethod
    def success(user_sub_good: UserSubGood):
        return UserAddGoodResponse(user_sub_good=user_sub_good, error=None)

    @staticmethod
    def error(error: Type[pt_error.Error]):
        return UserAddGoodResponse(user_sub_good=None, error=error)

    def to_message(self) -> str:
        if self.error is not None:
            return error_message.get(self.error, default_error_message)

        if self.user_sub_good.good_info.stock_state == GoodInfoStockState.OUT_OF_STOCK:
            stock_state_string = "缺貨中，請等待上架後通知"
        else:
            stock_state_string = "可購買"
        message = f'''
        ====
        成功新增
        商品名稱:{self.user_sub_good.good_info.name}
        價格:{self.user_sub_good.good_info.price}
        狀態:{stock_state_string}
        ====
        '''
        return inspect.cleandoc(message)
