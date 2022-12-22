from repository.models import GoodInfo, db
from repository.app import app


def create_good_info(data):
    # 對應到 add_good_info(good_info)
    good_info = GoodInfo(**data)
    db.session.add(good_info)
    db.session.commit()


def create_good_info2(good_id: str, price: int, name: str, stock_state: int = 1):
    # 對應到 add_good_info(good_info)
    good_info = GoodInfo(good_id, price, name, stock_state)
    db.session.add(good_info)
    db.session.commit()


def update_good_stock_state(good_id: str, stock_state: int):
    # 對應到 update_good_stock_state(good_id, state)
    r = GoodInfo.query.filter_by(id=good_id).update({"stock_state": stock_state})
    db.session.commit()
    return r


def query_good_info(skip: int = 0, limit: int = 100):
    # 對應到 find_all_good(handler)
    results = GoodInfo.query.with_entities(GoodInfo.id, GoodInfo.price, GoodInfo.name, GoodInfo.stock_state).offset(skip).limit(limit).all()
    db.session.commit()

    good_infos = []
    for r in results:
        good_infos.append(GoodInfo(good_id=r[0], price=r[1], name=r[2], stock_state=r[3]))
    return good_infos


def delete_good_info(good_id):
    r = GoodInfo.query.filter_by(id=good_id).delete()
    db.session.commit()
    return r


if __name__ == '__main__':
    with app.app_context():
        good_id = "1236"
        good_info_data = {
            "good_id": good_id,
            "name": "test",
            "price": 456,
            "stock_state": 12
        }

        # create_good_info(good_info_data)
        # create_good_info2("123", 456, "test", 12)
        print(query_good_info())

        # update_good_stock_state(good_id, 18)
        # print(query_good_info())

        # print(delete_good_info(good_id))
        # print(query_good_info())
