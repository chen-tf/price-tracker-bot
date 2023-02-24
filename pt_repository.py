import logging
import uuid
from concurrent.futures import ProcessPoolExecutor

import pt_config
import pt_datasource
import pt_error
from pt_entity import GoodInfo

logger = logging.getLogger("Repository")
pool = pt_datasource.get_pool()


def _execute(sql: str, parameters: tuple, handler: callable = None):
    conn = pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, parameters)
            if handler:
                return handler(cursor)
    finally:
        pool.putconn(conn)


def add_user_good_info(user_good_info):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'select * from "user" where id=%s for update;',
                    (str(user_good_info.user_id),),
                )
                cursor.execute(
                    "select count(1) from user_sub_good where user_id=%s and state = 1",
                    (str(user_good_info.user_id),),
                )
                total_size = cursor.fetchone()[0]
                if total_size >= pt_config.USER_SUB_GOOD_LIMITED:
                    raise pt_error.ExceedLimitedSizeError

                sql = """INSERT INTO public.user_sub_good
                (id, user_id, good_id, price, is_notified, state)
                VALUES(%s, %s, %s, %s, false, 1)
                ON CONFLICT(user_id, good_id) DO UPDATE
                SET price = EXCLUDED.price, is_notified = EXCLUDED.is_notified, state = EXCLUDED.state;
                """
                cursor.execute(
                    sql,
                    (
                        uuid.uuid4(),
                        user_good_info.user_id,
                        user_good_info.good_id,
                        user_good_info.original_price,
                    ),
                )
    finally:
        pool.putconn(conn)


def find_all_good(handler):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select id,price,name,COALESCE(stock_state,1) from good_info
                    where state = 1;
                    """
                cursor.execute(sql)
                for result in cursor:
                    good_info = GoodInfo(
                        good_id=result[0],
                        price=result[1],
                        name=result[2],
                        stock_state=result[3],
                    )
                    handler(good_info)
    finally:
        pool.putconn(conn)


def disable_redundant_good_info(good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select id from user_sub_good where good_id=%s and state = 1 LIMIT 1;
                        """
                cursor.execute(sql, (good_id,))
                is_exist = len(cursor.fetchall()) > 0
                if not is_exist:
                    sql = """update public.good_info set state = 0
                    WHERE id=%s;
                    """
                    cursor.execute(sql, (good_id,))
    finally:
        pool.putconn(conn)
    return is_exist


def find_user_sub_goods_price_higher(new_price, good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select usg.id,usg.user_id, usg.price, u.chat_id, u.line_notify_token from user_sub_good usg
                    join "user" u on usg.user_id = u.id and u.state = 1 and usg.state = 1
                    where usg.good_id = %s and usg.price > %s and usg.is_notified = false;
                    """
                cursor.execute(sql, (good_id, new_price))
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    return all_results


def find_user_by_good_id(good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select u.chat_id from user_sub_good usg
                join "user" u on usg.user_id = u.id and u.state = 1
                where usg.good_id = %s;
                """
                cursor.execute(sql, (good_id,))
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    return all_results


def reset_higher_user_sub(good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """update user_sub_good set is_notified=false where good_id=%s;
                    """
                cursor.execute(sql, (good_id,))
    finally:
        pool.putconn(conn)


def mark_is_notified_by_id(ids):
    if len(ids) < 1:
        return
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """update user_sub_good set is_notified=true where id in %s;
                    """
                cursor.execute(sql, (tuple(ids),))
    finally:
        pool.putconn(conn)


def find_user_sub_goods(user_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select gi.name, usg.price, COALESCE(gi.stock_state,1),usg.good_id from user_sub_good usg
                    join good_info gi on gi.id = usg.good_id where usg.user_id = %s and usg.state = 1;
                    """
                cursor.execute(sql, (user_id,))
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    return all_results


def update_good_stock_state(good_id, state):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """update good_info set stock_state=%s where id=%s;
                    """
                cursor.execute(sql, (state, good_id))
    finally:
        pool.putconn(conn)


def find_all_active_user(consumer):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = """select u.id,u.chat_id from user_sub_good usg join
                    "user" u on usg.user_id = u.id where usg.state = 1 
                    group by (u.id, u.chat_id);"""
                cursor.execute(sql)
                executor = ProcessPoolExecutor(max_workers=3)
                futures = []
                for record in cursor:
                    future = executor.submit(consumer, record)
                    futures.append(future)
                executor.shutdown(True)
                for future in futures:
                    print(future.result())
    finally:
        pool.putconn(conn)


def disable_user_and_user_sub_goods(inactive_user_id):
    if not inactive_user_id:
        return

    conn = pool.getconn()
    logger.info("Not active user counts : %s", inactive_user_id)
    try:
        with conn:
            with conn.cursor() as cursor:
                update_user_sql = """UPDATE "user"
                SET state = 0
                WHERE id = %s;"""
                update_user_sub_good_sql = """UPDATE user_sub_good
                SET state = 0
                WHERE user_id = %s;"""
                cursor.execute(update_user_sub_good_sql, (inactive_user_id,))
                cursor.execute(update_user_sql, (inactive_user_id,))
    finally:
        pool.putconn(conn)
