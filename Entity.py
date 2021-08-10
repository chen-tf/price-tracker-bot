class UserGoodInfo:
    user_id: str
    chat_id: str
    good_id: str
    original_price: int
    is_notified: bool

    def __init__(self, user_id: str, chat_id: str, good_id: str, original_price: int, is_notified: bool) -> None:
        self.user_id = user_id
        self.chat_id = chat_id
        self.good_id = good_id
        self.original_price = original_price
        self.is_notified = is_notified


class GoodInfo:
    good_id: str
    price: int
    name: str

    def __init__(self, good_id: str, price: int, name: str) -> None:
        self.good_id = good_id
        self.price = price
        self.name = name
