import re
import math
import random
import pickle
import base64
import requests
from io import BytesIO
from lxml import etree
from PIL import Image
from addons.utils import safe_re, safe_get, safe_post, rds, get_unique_key, no_error_content
from addons.errors import *
from addons.parse_html import parse_standard_table
from addons.processImage import process


class Lib:

    info = {}
    base_url = "http://opac.jluzh.com/"
    opac_url = base_url + "opac/"
    reader_url = base_url + "reader/"
    captcha_url = reader_url + "captcha.php?"
    login_url = reader_url + "redr_verify.php"
    checkout_book_url = reader_url + "book_lst.php"
    headers = {
        "Referer": "http://opac.jluzh.com/opac/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
                      "55.0.2883.87 Safari/537.36",
    }

    def search(self, keyword):
        _url = self.opac_url + "search_adv_result.php?sType0=any&q0=%s&with_ebook=&page=%s"
        url = _url % (keyword, 1)
        html = safe_get(url, headers=self.headers).content.decode("utf-8")
        page = etree.HTML(html)
        books_num = int(page.xpath(u"//div[@class='box_bgcolor']/font[last()]")[0].text)
        current_page = 1
        books = []
        url_code = []

        while True:
            books.extend(parse_standard_table(html, "result_content", pure=True))
            url_code.extend(safe_re('marc_no=(.*)"', html))

            current_page += 1
            if current_page > math.ceil(books_num/20):
                break

            url = _url % (keyword, current_page)
            html = safe_get(url, headers=self.headers).content.decode("utf-8")

        return books, url_code

    def get_book_detail(self, marc_no):
        url = self.opac_url + "item.php?marc_no=" + marc_no
        html = safe_get(url, headers=self.headers).content.decode("utf-8")
        remain_books = parse_standard_table(html, "item", pure=True)
        return remain_books

    def get_captcha(self):
        res = safe_get(self.captcha_url+str(random.random()), stream=True)
        cookies = res.cookies
        return {"cookies": cookies, "captcha": res.content}

    def pre_login(self, no_code):
        ret = self.get_captcha()
        captcha = ret["captcha"]

        if no_code:
            img = BytesIO(captcha)
            process.set_working_key("lib")
            captcha = "".join(process.predict(img))

        pickled_cookies = pickle.dumps(ret["cookies"])
        data = {
            "captcha": captcha,
            "cookies": base64.b64encode(pickled_cookies)
        }
        
        uid = get_unique_key(prefix="lib")
        rds.hmset(uid, data)
        return uid
    
    def init_from_redis(self, uid, only_cookies=False):
        self.cookies = pickle.loads(base64.b64decode(rds.hget(uid, "cookies")))
        if not only_cookies:
            self.info["captcha"] = rds.hget(uid, "captcha")

    def login(self, uid, data):
        self.init_from_redis(uid)
        data = {
            "number": data["number"],
            "passwd": data["password"],
            "captcha": self.info["captcha"],
            "select": "cert_no",
            "returnUrl": "",
        }

        res = safe_post(self.login_url, data=data, headers=self.headers, cookies=self.cookies)
        html = res.content.decode("utf-8")

        no_error_content(html, "//font[@color='red']", uid)

        rds.hdel(uid, "captcha")
        return uid

    def get_checkout_book(self, uid):
        self.init_from_redis(uid, only_cookies=True)
        res = safe_get(self.checkout_book_url, headers=self.headers, cookies=self.cookies)
        html = res.content.decode("utf-8")
        checkout_books = parse_standard_table(html, class_name="table_line", pure=True)
        return checkout_books

