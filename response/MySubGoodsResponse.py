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
        message = "收藏清單\n"
        for user_sub_good in self.user_sub_goods:
            stock_state_string = "可購買"
            if user_sub_good.state == GoodInfoStockState.OUT_OF_STOCK:
                stock_state_string = "缺貨中，請等待上架後通知"
            elif user_sub_good.state == GoodInfoStockState.NOT_EXIST:
                stock_state_string = "商品目前無展售或是網頁不存在"
            good_url = pt_momo.generate_momo_url_by_good_id(user_sub_good.good_id)
            if user_sub_good.price > user_sub_good.good_info.price:
                formatted_sub_price = f"<del>{user_sub_good.formatted_price()}</del>（現在售價：{user_sub_good.good_info.price}）"
            else:
                formatted_sub_price = f"{user_sub_good.formatted_price()}"
            row = f'''
            ====
            <b>商品名稱</b>：{user_sub_good.good_info.name}
            <b>追蹤價格</b>：{formatted_sub_price}
            <b>狀態</b>：{stock_state_string}
            <a href="{good_url}">點我前往</a>
            ====
            '''
            message += inspect.cleandoc(row)
        return message
