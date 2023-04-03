import inspect
from dataclasses import dataclass, field
from typing import List

import pt_momo
from repository.entity import GoodInfoStockState, UserSubGood


@dataclass
class UserSubGoodsResponse:
    user_sub_goods: List[UserSubGood] = field(default_factory=lambda: [])

    def to_message(self) -> str:
        if len(self.user_sub_goods) == 0:
            return "尚未追蹤商品"
        message = "追蹤清單\n"
        for user_sub_good in self.user_sub_goods:
            stock_state_string = "可購買"
            if user_sub_good.state == GoodInfoStockState.OUT_OF_STOCK:
                stock_state_string = "缺貨中，請等待上架後通知"
            elif user_sub_good.state == GoodInfoStockState.NOT_EXIST:
                stock_state_string = "商品目前無展售或是網頁不存在"
            good_url = pt_momo.generate_momo_url_by_good_id(user_sub_good.good_id)
            row = f'''
            ====
            商品名稱:{user_sub_good.good_info.name}
            追蹤價格:{user_sub_good.price}
            狀態:{stock_state_string}
            {good_url}
            ====
            '''
            message += inspect.cleandoc(row)
        return message
