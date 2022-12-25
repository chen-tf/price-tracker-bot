import functools

from repository.models import GoodInfo, db
from repository.app import app


def auto_commit(func):
    @functools.wraps(func)
    def wrapper(*args):
        session = db.session
        try:
            result = func(*args, session=session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        return result

    return wrapper


@auto_commit
def create_good_info(good_id: str, price: int, name: str, stock_state: int = 1, **kwargs):
    session = kwargs["session"]
    good_info = GoodInfo(good_id, price, name, stock_state)
    session.add(good_info)


@auto_commit
def update_good_stock_state(good_id: str, stock_state: int, **kwargs):
    # 對應到 update_good_stock_state(good_id, state)

    # Use ORM can trigger update_time(onupdate=func.now()), so don't need to manually set update_time
    r = GoodInfo.query.filter_by(id=good_id).update({"stock_state": stock_state})

    # Execute SQL line don't trigger sqlalchemy update_time(onupdate=func.now()),
    # so you need to manually set update_time to the current time
    # r = db.engine.execute(
    #     text("update good_info set stock_state=:stock_state, update_time=:update_time where id=:good_id"),
    #     {"stock_state": stock_state, "update_time": datetime.now(timezone.utc), "good_id": good_id})
    return r


@auto_commit
def query_good_info(skip: int = 0, limit: int = 100, **kwargs):
    # 對應到 find_all_good(handler)
    results = GoodInfo.query \
        .with_entities(GoodInfo.id, GoodInfo.price, GoodInfo.name, GoodInfo.stock_state) \
        .offset(skip) \
        .limit(limit) \
        .all()

    good_infos = []
    for r in results:
        good_infos.append(GoodInfo(good_id=r[0], price=r[1], name=r[2], stock_state=r[3]))
    return good_infos


@auto_commit
def delete_good_info(good_id, **kwargs):
    r = GoodInfo.query.filter_by(id=good_id).delete()
    return r


if __name__ == '__main__':
    with app.app_context():
        good_id = "1236"
        good_info_data = {
            "good_id": good_id,
            "name": "test",
            "price": 4567,
            "stock_state": 12
        }

        # create_good_info(good_info_data)
        # create_good_info2("123", 456, "test", 12)
        print(query_good_info())

        update_good_stock_state(good_id, 21)
        print(query_good_info())

    # print(query_good_info())

    # print(delete_good_info(good_id))
    # print(query_good_info())
