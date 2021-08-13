# coding: utf-8
import hashlib
import logging
import threading
import uuid

import requests
from bs4 import BeautifulSoup

import Bot
import DataSource
import PTConfig
import PTError
from Entity import GoodInfo

good_url = PTConfig.momo_good_url()
basic_headers = {
    'User-Agent': PTConfig.USER_AGENT
}
logger = logging.getLogger('Service')
momo_request_lock = threading.Lock()  # control the number of request
pool = DataSource.get_pool()


def upsert_user(user_id, chat_id):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''INSERT INTO public."user"
            (id, chat_id)
            VALUES(%s, %s)
            ON CONFLICT(id) DO UPDATE
            SET chat_id = EXCLUDED.chat_id;
            '''
            cursor.execute(sql, (user_id, chat_id))
    pool.putconn(conn, close=True)


def count_user_good_info_sum(user_id):
    conn = pool.getconn()
    total_size = 0
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('select count(1) from user_sub_good where user_id=%s', (str(user_id),))
            total_size = cursor.fetchone()[0]
    pool.putconn(conn, close=True)
    return total_size


def add_user_good_info(user_good_info):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            cursor.execute('select * from "user" where id=%s for update;', (str(user_good_info.user_id),))
            cursor.execute('select count(1) from user_sub_good where user_id=%s', (str(user_good_info.user_id),))
            total_size = cursor.fetchone()[0]
            if total_size >= PTConfig.USER_SUB_GOOD_LIMITED:
                raise PTError.ExceedLimitedSizeError
            else:
                sql = '''INSERT INTO public.user_sub_good
                (id, user_id, good_id, price, is_notified)
                VALUES(%s, %s, %s, %s, false)
                ON CONFLICT(user_id, good_id) DO UPDATE
                SET price = EXCLUDED.price, is_notified = EXCLUDED.is_notified;
                '''
                cursor.execute(sql, (uuid.uuid4(), user_good_info.user_id, user_good_info.good_id,
                                     user_good_info.original_price))
    pool.putconn(conn, close=True)


def add_good_info(good_info):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''INSERT INTO good_info (id, name, price, checksum,stock_state) VALUES(%s, %s, %s, %s, %s) 
            ON CONFLICT(id) DO UPDATE
            SET name = EXCLUDED.name, price = EXCLUDED.price, checksum = EXCLUDED.checksum
            , stock_state = EXCLUDED.stock_state;
            '''
            cursor.execute(sql, (
                good_info.good_id, good_info.name, good_info.price, good_info.checksum, good_info.stock_state))
    pool.putconn(conn, close=True)


def _get_good_info_from_momo(i_code=None, session=requests.Session()):
    momo_request_lock.acquire()
    logger.debug('_get_good_info_from_momo lock acquired')
    params = {'i_code': i_code}
    response = session.request("GET", good_url, params=params, headers=basic_headers)
    momo_request_lock.release()
    logger.debug('_get_good_info_from_momo lock released')
    return response.text


def _format_price(price):
    return int(str(price).strip().replace(',', ''))


def _get_checksum(content):
    md5_hash = hashlib.md5()
    md5_hash.update(content.encode('utf-8'))
    return md5_hash.hexdigest()


def get_good_info(good_id=None, session=requests.Session(), previous_good_info=None):
    logger.info("good_id %s", good_id)
    response = _get_good_info_from_momo(i_code=good_id, session=session)
    response_checksum = _get_checksum(response)

    # Save the parse time if the checksum value is equal.
    if previous_good_info is not None and response_checksum == previous_good_info.checksum:
        return previous_good_info

    soup = BeautifulSoup(response, "lxml")
    try:
        good_name = soup.select(PTConfig.MOMO_NAME_PATH)[0].text
        logger.info("good_name %s", good_name)
        price = _get_price_by_bs4(soup)
        logger.info("price %s", price)
        stock_state = GoodInfo.STOCK_STATE_IN_STOCK
        if soup.find('li', id='buyNowBtn') is None:
            stock_state = GoodInfo.STOCK_STATE_OUT_OF_STOCK
        logger.info("stock_state %s", stock_state)
    except Exception as e:
        logger.error("Parse good_info and catch an exception. good_id:%s", good_id, exc_info=True)
        raise PTError.CrawlerParseError
    return GoodInfo(good_id=good_id, name=good_name, price=price, checksum=response_checksum, stock_state=stock_state)


def _get_price_by_bs4(soup):
    try:
        return _format_price(soup.select(PTConfig.MOMO_SINGLE_PRICE_PATH)[0].text)
    except Exception as e:
        return _format_price(soup.select(PTConfig.MOMO_TWO_PRICE_PATH)[0].text)


def sync_price():
    logger.info('Price syncer started')
    session = requests.Session()
    for good_info in _find_all_good():
        try:
            good_id = good_info.good_id
            is_exist = _remove_redundant_good_info(good_info.good_id)
            if not is_exist:
                logger.debug('%s not exist', good_id)
                continue
            new_good_info = get_good_info(good_id=good_id, session=session, previous_good_info=good_info)
            add_good_info(new_good_info)
            cheaper_records = {}
            if new_good_info.price != good_info.price:
                _reset_higher_user_sub(good_id)
                cheaper_records = _find_user_sub_goods_price_higher(new_good_info.price, good_id)
            msg = '%s\n目前價格為%s, 低於當初紀錄價格%s'
            success_notified = []
            for cheaper_record in cheaper_records:
                chat_id = cheaper_record[3]
                original_price = cheaper_record[2]
                Bot.send(msg % (new_good_info.name, new_good_info.price, original_price), chat_id)
                success_notified.append(cheaper_record[0])
            _mark_is_notified_by_id(success_notified)

            # Notify if good's stock change
            if new_good_info.stock_state == GoodInfo.STOCK_STATE_IN_STOCK and good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
                logger.info('%s is in stock!', new_good_info.name)
                follow_good_chat_ids = _find_user_by_good_id(good_id)
                msg = '%s\n目前已經可購買！！！'
                for follow_good_chat_id in follow_good_chat_ids:
                    Bot.send(msg % new_good_info.name, str(follow_good_chat_id[0]))
        except Exception as e:
            logger.error(e, exc_info=True)
    logger.info('Price syncer finished')


def _find_all_good():
    conn = pool.getconn()
    goods = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select id,price,name,checksum,COALESCE(stock_state,1) from good_info;
                '''
            cursor.execute(sql)
            all_results = cursor.fetchall()
    pool.putconn(conn, close=True)
    for result in all_results:
        goods.append(
            GoodInfo(good_id=result[0], price=result[1], name=result[2], checksum=result[3], stock_state=result[4]))
    return goods


def _remove_redundant_good_info(good_id):
    conn = pool.getconn()
    is_exist = False
    with conn:
        with conn.cursor() as cursor:
            sql = '''select id from user_sub_good where good_id=%s LIMIT 1;
                    '''
            cursor.execute(sql, (good_id,))
            is_exist = len(cursor.fetchall()) > 0
            if not is_exist:
                sql = '''DELETE FROM public.good_info
                WHERE id=%s;
                '''
                cursor.execute(sql, (good_id,))
    pool.putconn(conn, close=True)
    return is_exist


def _find_user_sub_goods_price_higher(new_price, good_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select usg.id,usg.user_id, usg.price, u.chat_id from user_sub_good usg
            join "user" u on  usg.user_id = u.id
            where usg.good_id = %s and usg.price > %s and usg.is_notified = false;
            '''
            cursor.execute(sql, (good_id, new_price))
            all_results = cursor.fetchall()
    pool.putconn(conn, close=True)
    return all_results


def _find_user_by_good_id(good_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select u.chat_id from user_sub_good usg
            join "user" u on  usg.user_id = u.id
            where usg.good_id = %s;
            '''
            cursor.execute(sql, (good_id,))
            all_results = cursor.fetchall()
    pool.putconn(conn, close=True)
    return all_results


def _reset_higher_user_sub(good_id):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update user_sub_good set is_notified=false where good_id=%s;
                '''
            cursor.execute(sql, (good_id,))
    pool.putconn(conn, close=True)


def _mark_is_notified_by_id(ids):
    if len(ids) < 1:
        return
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''update user_sub_good set is_notified=true where id in (%s);
                '''
            cursor.execute(sql, ids)
    pool.putconn(conn, close=True)


def find_user_sub_goods(user_id):
    conn = pool.getconn()
    all_results = []
    with conn:
        with conn.cursor() as cursor:
            sql = '''select gi.name, usg.price, COALESCE(gi.stock_state,1) from user_sub_good usg
                join good_info gi on gi.id = usg.good_id where usg.user_id = %s;
                '''
            cursor.execute(sql, (user_id,))
            all_results = cursor.fetchall()
    pool.putconn(conn, close=True)
    return all_results


def clear(user_id):
    conn = pool.getconn()
    with conn:
        with conn.cursor() as cursor:
            sql = '''DELETE FROM public.user_sub_good
            WHERE user_id=%s;
            '''
            cursor.execute(sql, (user_id,))
    pool.putconn(conn, close=True)
