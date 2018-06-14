import time
import functools
import redis
import uuid
import requests
from .errors import *


def fn_timer(function):
    """
    calc the function running time
    :param function:
    :return:
    """
    @functools.wraps(function)
    def function_timer(*args, **kwargs):
        t0 = time.time()
        result = function(*args, **kwargs)
        t1 = time.time()
        print("Total time running %s: %s seconds" % (function.__name__, str(t1 - t0)))
        return result

    return function_timer


def not_error_page(html, uid=None):
    """
    check if the page is an error page with alert
    :param html:
    :param uid:
    :return:
    """
    import re
    s = r"alert\('(.*?)'\)"
    r = re.search(s, html)
    if r:
        if "验证码" in r.group(1):
            if uid:
                rds.delete(uid)
            raise CheckcodeError(r.group(1))
        else:
            raise PageError(r.group(1))
    return True


def no_error_content(html, xpath, uid=None):
    from lxml import etree
    page = etree.HTML(html)
    xp = page.xpath(xpath)
    if xp:
        alert_text = xp[0].text
        if "验证码" in alert_text:
            raise CheckcodeError(alert_text)
        raise PageError(alert_text)
    return True


def safe_get(*args, **kwargs):
    try:
        r = requests.get(*args, **kwargs)
        return r
    except requests.ConnectionError as e:
        raise PageError("无法正常连接")


def safe_post(*args, **kwargs):
    try:
        r = requests.post(*args, **kwargs)
        return r
    except requests.ConnectionError as e:
        raise PageError("无法正常连接")


def safe_re(s, html):
    import re
    try:
        result = re.findall(s, html)
        return result
    except NameError:
        raise PageError("无法链接到正方教务系统")
    except IndexError:
        pass


def safe_xpath(html, rules):
    from lxml import etree

    page = etree.HTML(html)
    results = []

    for rule in rules:
        result = page.xpath(rule)
        if result:
            results.append(result[0].text)
        else:
            results.append("")

    return results


def get_unique_key(prefix=""):
    """
    create a unique key with uuid
    :param prefix:
    :return:
    """
    key = uuid.uuid4().hex
    if prefix:
        return "%s:%s" % (prefix, key)
    return key


def init_redis():
    """
    init redis
    :return:
    """
    redis_serve = redis.StrictRedis(host="localhost", port="6379", db=0, decode_responses=True)
    return redis_serve


def init_mongodb():
    """
    init mongodb
    :return:
    """
    import pymongo
    client = pymongo.MongoClient("localhost", 27017)
    db = client["assist"]
    return db

rds = init_redis()


def store_ocr_data(captcha_ocr_try):
    """
    store the ocr try times and success times
    :param captcha_ocr_try:
    :return:
    """
    total = rds.hget("captcha_ocr", "total")
    success = rds.hget("captcha_ocr", "success")
    ocr_rds_data = {
        "total": int(total)+captcha_ocr_try if total else 0+captcha_ocr_try,
        "success": int(success)+1 if success else 0 + 1
    }
    rds.hmset("captcha_ocr", ocr_rds_data)


def create_ics_file(data, begin_date):
    """
    create an ics type file
    :param data:
    :param begin_date:
    :return:
    """
    from ics import Calendar, Event
    c = Calendar()
    e = Event()

    for i in data:
        e.name = i["name"]
        e.begin = begin_date
        e.end = i["end"]
        c.events.append(e)

    return c


def calc_date(begin_date="2017-2-27", weeks="16"):
    """
    calc the future date weeks away
    :param begin_date:
    :param weeks:
    :return:
    """
    from datetime import datetime, timedelta
    begin_date = datetime.strptime(begin_date, "%Y-%m-%d")
    end_date = begin_date + timedelta(weeks=weeks)
    return end_date


def calc_weeks(begin_date="2017-2-26"):
    """
    calc the weeks from now to begin time
    :param begin_date:
    :return:
    """
    import math
    from datetime import datetime
    begin_date = datetime.strptime(begin_date, "%Y-%m-%d")
    now = datetime.now()
    days = (now-begin_date).days
    weeks = math.ceil(days/7)  # 向上取整
    return weeks


def pretty_table(title, table, serial_number=False):
    import copy
    from prettytable import PrettyTable
    pt = PrettyTable(title)
    _t = copy.deepcopy(table)
    for i in range(len(_t)):
        if serial_number:
            _t[i].insert(0, i)
        pt.add_row(_t[i])
    return pt
