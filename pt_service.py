# coding: utf-8
import logging
import threading
import uuid

import requests
from bs4 import BeautifulSoup

import pt_bot
import pt_config
import pt_datasource
import pt_error
from lotify_client import get_lotify_client
from pt_entity import GoodInfo

good_url = pt_config.momo_good_url()
logger = logging.getLogger('Service')
momo_request_lock = threading.Lock()  # control the number of request
pool = pt_datasource.get_pool()
lotify_client = get_lotify_client()


def upsert_user(user_id, chat_id):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''INSERT INTO public."user"
            (id, chat_id, state)
            VALUES(%s, %s, 1)
            ON CONFLICT(id) DO UPDATE
            SET chat_id = EXCLUDED.chat_id, state = EXCLUDED.state;
            '''
            cursor.execute(sql, (user_id, chat_id))
    pool.putconn(conn)


def count_user_good_info_sum(user_id):
    conn = pool.getconn()
    total_size = 0
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('select count(1) from user_sub_good where user_id=%s and state = 1', (str(user_id),))
            total_size = cursor.fetchone()[0]
    pool.putconn(conn)
    return total_size


def add_user_good_info(user_good_info):
    conn = pool.getconn()
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
    pool.putconn(conn)


def add_good_info(good_info):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''INSERT INTO good_info (id, name, price, stock_state,state) VALUES(%s, %s, %s, %s, 1) 
            ON CONFLICT(id) DO UPDATE
            SET name = EXCLUDED.name, price = EXCLUDED.price, stock_state = EXCLUDED.stock_state;
            '''
            cursor.execute(sql, (
                good_info.good_id, good_info.name, good_info.price, good_info.stock_state))
    pool.putconn(conn)


def _get_good_info_from_momo(i_code=None, session=requests.Session()):
    logger.debug('_get_good_info_from_momo lock waiting')
    momo_request_lock.acquire(timeout=pt_config.MOMO_REQUEST_TIMEOUT + 10)
    try:
        logger.debug('_get_good_info_from_momo lock acquired')
        params = {'i_code': i_code}
        response = session.request("GET", good_url, params=params, headers={'user-agent': pt_config.USER_AGENT},
                                   timeout=pt_config.MOMO_REQUEST_TIMEOUT)
    except Exception as e:
        logger.debug('_get_good_info_from_momo lock released')
        logger.error("Get good_info and catch an exception.", exc_info=True)
        raise pt_error.UnknownRequestError
    finally:
        momo_request_lock.release()
        logger.debug('_get_good_info_from_momo lock released')
    return response.text


def _format_price(price):
    return int(str(price).strip().replace(',', ''))


def get_good_info(good_id=None, session=requests.Session()):
    logger.info("good_id %s", good_id)
    response = _get_good_info_from_momo(i_code=good_id, session=session)

    soup = BeautifulSoup(response, "lxml")
    try:
        if soup.find('meta', property='og:title') is None:
            raise pt_error.GoodNotExist
        good_name = soup.find('meta', property='og:title')["content"]
        logger.info("good_name %s", good_name)
        price = _format_price(soup.find('meta', property='product:price:amount')["content"])
        logger.info("price %s", price)
        stock_state = soup.find('meta', property='product:availability')["content"]
        if stock_state == 'in stock':
            stock_state = GoodInfo.STOCK_STATE_IN_STOCK
        else:
            stock_state = GoodInfo.STOCK_STATE_OUT_OF_STOCK
        logger.info("stock_state %s", stock_state)
    except pt_error.GoodNotExist as e:
        logger.warning('Good not exist. id:%s', good_id)
        raise e
    except Exception as e:
        logger.error("Parse good_info and catch an exception. good_id:%s", good_id, exc_info=True)
        raise pt_error.CrawlerParseError
    return GoodInfo(good_id=good_id, name=good_name, price=price, stock_state=stock_state)


def sync_price():
    logger.info('Price syncer started')
    for good_info in _find_all_good():
        try:
            good_id = good_info.good_id
            is_exist = _disable_redundant_good_info(good_info.good_id)
            if not is_exist:
                logger.debug('%s not exist', good_id)
                continue
            new_good_info = get_good_info(good_id=good_id)
            add_good_info(new_good_info)
            cheaper_records = []
            if new_good_info.price != good_info.price:
                _reset_higher_user_sub(good_id)
                cheaper_records = _find_user_sub_goods_price_higher(new_good_info.price, good_id)
            msg = '%s\n目前價格為%s, 低於當初紀錄價格%s\n\n%s'
            success_notified = []
            good_page_url = generate_momo_url_by_good_id(good_id)
            for cheaper_record in cheaper_records:
                chat_id = cheaper_record[3]
                original_price = cheaper_record[2]
                format_msg = msg % (new_good_info.name, new_good_info.price, original_price, good_page_url)
                pt_bot.send(format_msg, chat_id)
                line_notify_token = cheaper_record[4]
                if line_notify_token:
                    try:
                        lotify_client.send_message(line_notify_token, format_msg)
                    except Exception as e:
                        logger.error(e, exc_info=True)
                success_notified.append(cheaper_record[0])
            _mark_is_notified_by_id(success_notified)

            # Notify if good's stock change
            if new_good_info.stock_state == GoodInfo.STOCK_STATE_IN_STOCK and good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
                logger.info('%s is in stock!', new_good_info.name)
                follow_good_chat_ids = _find_user_by_good_id(good_id)
                msg = '%s\n目前已經可購買！！！\n\n%s'
                for follow_good_chat_id in follow_good_chat_ids:
                    pt_bot.send(msg % (new_good_info.name, good_page_url), str(follow_good_chat_id[0]))
        except pt_error.GoodNotExist as e:
            update_good_stock_state(good_id, GoodInfo.STOCK_STATE_NOT_EXIST)
        except Exception as e:
            logger.error(e, exc_info=True)
    logger.info('Price syncer finished')


def _find_all_good():
    conn = pool.getconn()
    goods = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select id,price,name,COALESCE(stock_state,1) from good_info
                where state = 1;
                '''
            cursor.execute(sql)
            all_results = cursor.fetchall()
    pool.putconn(conn)
    for result in all_results:
        goods.append(
            GoodInfo(good_id=result[0], price=result[1], name=result[2], stock_state=result[3]))
    return goods


def _disable_redundant_good_info(good_id):
    conn = pool.getconn()
    is_exist = False
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
    pool.putconn(conn)
    return is_exist


def _find_user_sub_goods_price_higher(new_price, good_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select usg.id,usg.user_id, usg.price, u.chat_id, u.line_notify_token from user_sub_good usg
            join "user" u on usg.user_id = u.id and u.state = 1
            where usg.good_id = %s and usg.price > %s and usg.is_notified = false;
            '''
            cursor.execute(sql, (good_id, new_price))
            all_results = cursor.fetchall()
    pool.putconn(conn)
    return all_results


def _find_user_by_good_id(good_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select u.chat_id from user_sub_good usg
            join "user" u on usg.user_id = u.id and u.state = 1
            where usg.good_id = %s;
            '''
            cursor.execute(sql, (good_id,))
            all_results = cursor.fetchall()
    pool.putconn(conn)
    return all_results


def _reset_higher_user_sub(good_id):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update user_sub_good set is_notified=false where good_id=%s;
                '''
            cursor.execute(sql, (good_id,))
    pool.putconn(conn)


def _mark_is_notified_by_id(ids):
    if len(ids) < 1:
        return
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update user_sub_good set is_notified=true where id in %s;
                '''
            cursor.execute(sql, (tuple(ids),))
    pool.putconn(conn)


def find_user_sub_goods(user_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select gi.name, usg.price, COALESCE(gi.stock_state,1),usg.good_id from user_sub_good usg
                join good_info gi on gi.id = usg.good_id where usg.user_id = %s and usg.state = 1;
                '''
            cursor.execute(sql, (user_id,))
            all_results = cursor.fetchall()
    pool.putconn(conn)
    return all_results


def clear(user_id, good_name):
    conn = pool.getconn()
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
    pool.putconn(conn)
    return list(str(result[1]) for result in all_results if str(result[0]) in user_good_ids)


def generate_momo_url_by_good_id(good_id):
    return (pt_config.MOMO_URL + pt_config.MOMO_GOOD_URI + "?i_code=%s") % str(good_id)


def update_good_stock_state(good_id, state):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update good_info set stock_state=%s where id=%s;
                '''
            cursor.execute(sql, (state, good_id))
    pool.putconn(conn)


def disable_not_active_user_sub_good():
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''select u.id,u.chat_id from user_sub_good usg join
            "user" u on usg.user_id = u.id where usg.state = 1 
            group by (u.id, u.chat_id);'''
            cursor.execute(sql)
            all_results = cursor.fetchall()
    pool.putconn(conn)

    if not all_results:
        return

    not_active_user_ids = tuple(str(result[1]) for result in all_results if pt_bot.is_blocked_by_user(str(result[0])))

    if not not_active_user_ids:
        return

    conn = pool.getconn()
    logger.info("Not active user counts : %s", not_active_user_ids)
    with conn:
        with conn.cursor() as cursor:
            update_user_sql = '''UPDATE "user"
            SET state = 0
            WHERE id in %s;'''
            update_user_sub_good_sql = '''UPDATE user_sub_good
            SET state = 0
            WHERE user_id in %s;'''
            cursor.execute(update_user_sub_good_sql, (not_active_user_ids,))
            cursor.execute(update_user_sql, (not_active_user_ids,))

    pool.putconn(conn)


def update_user_line_token(user_id, line_notify_token):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update "user" set line_notify_token=%s where id=%s;
                    '''
            cursor.execute(sql, (line_notify_token, user_id))
    pool.putconn(conn)
