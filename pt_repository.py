import logging
import uuid

import pt_config
import pt_datasource
import pt_error
from pt_entity import GoodInfo

logger = logging.getLogger('Repository')
pool = pt_datasource.get_pool()


def update_user_line_token(user_id, line_notify_token):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''update "user" set line_notify_token=%s where id=%s;
                        '''
                cursor.execute(sql, (line_notify_token, user_id))
    finally:
        pool.putconn(conn)


def upsert_user(user_id, chat_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''INSERT INTO public."user"
                (id, chat_id, state)
                VALUES(%s, %s, 1)
                ON CONFLICT(id) DO UPDATE
                SET chat_id = EXCLUDED.chat_id, state = EXCLUDED.state;
                '''
                cursor.execute(sql, (user_id, chat_id))
    finally:
        pool.putconn(conn)


def count_user_good_info_sum(user_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('select count(1) from user_sub_good where user_id=%s and state = 1', (str(user_id),))
                total_size = cursor.fetchone()[0]
    finally:
        pool.putconn(conn)
    return total_size


def add_user_good_info(user_good_info):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('select * from "user" where id=%s for update;', (str(user_good_info.user_id),))
                cursor.execute('select count(1) from user_sub_good where user_id=%s and state = 1',
                               (str(user_good_info.user_id),))
                total_size = cursor.fetchone()[0]
                if total_size >= pt_config.USER_SUB_GOOD_LIMITED:
                    raise pt_error.ExceedLimitedSizeError
                else:
                    sql = '''INSERT INTO public.user_sub_good
                    (id, user_id, good_id, price, is_notified, state)
                    VALUES(%s, %s, %s, %s, false, 1)
                    ON CONFLICT(user_id, good_id) DO UPDATE
                    SET price = EXCLUDED.price, is_notified = EXCLUDED.is_notified, state = EXCLUDED.state;
                    '''
                    cursor.execute(sql, (uuid.uuid4(), user_good_info.user_id, user_good_info.good_id,
                                         user_good_info.original_price))
    finally:
        pool.putconn(conn)


def add_good_info(good_info):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''INSERT INTO good_info (id, name, price, stock_state,state) VALUES(%s, %s, %s, %s, 1) 
                ON CONFLICT(id) DO UPDATE
                SET name = EXCLUDED.name, price = EXCLUDED.price, stock_state = EXCLUDED.stock_state;
                '''
                cursor.execute(sql, (
                    good_info.good_id, good_info.name, good_info.price, good_info.stock_state))
    finally:
        pool.putconn(conn)


def find_all_good():
    conn = pool.getconn()
    goods = []
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''select id,price,name,COALESCE(stock_state,1) from good_info
                    where state = 1;
                    '''
                cursor.execute(sql)
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    for result in all_results:
        goods.append(
            GoodInfo(good_id=result[0], price=result[1], name=result[2], stock_state=result[3]))
    return goods


def disable_redundant_good_info(good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''select id from user_sub_good where good_id=%s and state = 1 LIMIT 1;
                        '''
                cursor.execute(sql, (good_id,))
                is_exist = len(cursor.fetchall()) > 0
                if not is_exist:
                    sql = '''update public.good_info set state = 0
                    WHERE id=%s;
                    '''
                    cursor.execute(sql, (good_id,))
    finally:
        pool.putconn(conn)
    return is_exist


def find_user_sub_goods_price_higher(new_price, good_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''select usg.id,usg.user_id, usg.price, u.chat_id, u.line_notify_token from user_sub_good usg
                    join "user" u on usg.user_id = u.id and u.state = 1
                    where usg.good_id = %s and usg.price > %s and usg.is_notified = false;
                    '''
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
                sql = '''select u.chat_id from user_sub_good usg
                join "user" u on usg.user_id = u.id and u.state = 1
                where usg.good_id = %s;
                '''
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
                sql = '''update user_sub_good set is_notified=false where good_id=%s;
                    '''
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
                sql = '''update user_sub_good set is_notified=true where id in %s;
                    '''
                cursor.execute(sql, (tuple(ids),))
    finally:
        pool.putconn(conn)


def find_user_sub_goods(user_id):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''select gi.name, usg.price, COALESCE(gi.stock_state,1),usg.good_id from user_sub_good usg
                    join good_info gi on gi.id = usg.good_id where usg.user_id = %s and usg.state = 1;
                    '''
                cursor.execute(sql, (user_id,))
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    return all_results


def clear(user_id, good_name):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                query_user_good_sql = '''select usg.id,gi."name" from user_sub_good usg 
                join good_info gi on usg.good_id = gi.id
                where usg.state = 1 and usg.user_id = %s;
                '''
                cursor.execute(query_user_good_sql, (user_id,))
                all_results = cursor.fetchall()
                if good_name is not None:
                    user_good_ids = tuple(
                        str(result[0]) for result in all_results if good_name in str(result[1]))
                else:
                    user_good_ids = tuple(str(result[0]) for result in all_results)
                if len(user_good_ids) == 0:
                    return []
                sql = '''UPDATE public.user_sub_good 
                set state = 0
                WHERE id in %s;
                '''
                cursor.execute(sql, (user_good_ids,))
    finally:
        pool.putconn(conn)
    return list(str(result[1]) for result in all_results if str(result[0]) in user_good_ids)


def update_good_stock_state(good_id, state):
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''update good_info set stock_state=%s where id=%s;
                    '''
                cursor.execute(sql, (state, good_id))
    finally:
        pool.putconn(conn)


def find_all_active_user():
    conn = pool.getconn()
    try:
        with conn:
            with conn.cursor() as cursor:
                sql = '''select u.id,u.chat_id from user_sub_good usg join
                    "user" u on usg.user_id = u.id where usg.state = 1 
                    group by (u.id, u.chat_id);'''
                cursor.execute(sql)
                all_results = cursor.fetchall()
    finally:
        pool.putconn(conn)
    return all_results


def disable_user_and_user_sub_goods(inactive_user_ids):
    if not inactive_user_ids:
        return

    conn = pool.getconn()
    logger.info("Not active user counts : %s", inactive_user_ids)
    try:
        with conn:
            with conn.cursor() as cursor:
                update_user_sql = '''UPDATE "user"
                SET state = 0
                WHERE id in %s;'''
                update_user_sub_good_sql = '''UPDATE user_sub_good
                SET state = 0
                WHERE user_id in %s;'''
                cursor.execute(update_user_sub_good_sql, (inactive_user_ids,))
                cursor.execute(update_user_sql, (inactive_user_ids,))
    finally:
        pool.putconn(conn)
