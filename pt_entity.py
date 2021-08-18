class UserGoodInfo:
    user_id: str
    chat_id: str
    good_id: str
    original_price: int
    is_notified: bool
    STATE_DISABLE = 0
    STATE_ENABLE = 1

    def __init__(self, user_id: str, chat_id: str, good_id: str, original_price: int, is_notified: bool) -> None:
        self.user_id = user_id
        self.chat_id = chat_id
        self.good_id = good_id
        self.original_price = original_price
        self.is_notified = is_notified
        self.state = 1


class GoodInfo:
    STOCK_STATE_OUT_OF_STOCK = 0
    STOCK_STATE_IN_STOCK = 1
    STOCK_STATE_NOT_EXIST = 2
    STATE_DISABLE = 0
    STATE_ENABLE = 1

    good_id: str
    price: int
    name: str
    checksum: str
    stock_state: int
    state: int

    def __init__(self, good_id: str, price: int, name: str, checksum: str, stock_state: int) -> None:
        self.good_id = good_id
        self.price = price
        self.name = name
        self.checksum = checksum
        if stock_state is None:
            self.stock_state = 1
        else:
            self.stock_state = stock_state
        self.state = 1
