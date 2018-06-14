import base64
import pickle
from io import BytesIO
from lxml import etree
from datetime import datetime, timedelta
from addons.utils import rds, safe_get, safe_post, safe_xpath, get_unique_key, no_error_content
from addons.parse_html import parse_standard_table
from addons.processImage import process

class Card:
    info = {}
    base_url = "https://icard.jluzh.com/"
    index_url = base_url + "index.action"
    captcha_url = base_url + "check.action"
    login_url = base_url + "login.action"
    balance_url = base_url + "queryBalance.action"
    consume_url = base_url + "queryConsume.action"

    headers = {
        "Referer": base_url,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
                      "55.0.2883.87 Safari/537.36",
    }

    def _get_login_params(self):
        xp = "/html/body/form/input[%s]/@name"
        res = safe_get(self.index_url, headers=self.headers)
        html = res.content
        page = etree.HTML(html)
        param1 = page.xpath(xp % 1)[0]
        param2 = page.xpath(xp % 2)[0]
        return {"param1": param1, "param2": param2, "cookies": res.cookies}

    def get_captcha(self, cookies):
        res = safe_get(self.captcha_url, cookies=cookies)
        cookies = res.cookies
        return {"captcha": res.content, "cookies": cookies}

    def pre_login(self, no_code=True):
        login_params = self._get_login_params()
        ret = self.get_captcha(cookies=login_params["cookies"])
        captcha = ret["captcha"]

        if no_code:
            img = BytesIO(captcha)
            process.set_working_key("card")
            captcha = "".join(process.predict(img))

        pickled_cookies = pickle.dumps(login_params["cookies"])
        data = {
            "captcha": captcha,
            "cookies": base64.b64encode(pickled_cookies),
            "param1": login_params["param1"],
            "param2": login_params["param2"],
        }

        uid = get_unique_key(prefix="card")
        rds.hmset(uid, data)
        return uid

    def init_from_redis(self, uid, only_cookies=False):
        self.cookies = pickle.loads(base64.b64decode(rds.hget(uid, "cookies")))
        self.info["param1"] = rds.hget(uid, "param1")
        self.info["param2"] = rds.hget(uid, "param2")
        if not only_cookies:
            self.info["captcha"] = rds.hget(uid, "captcha")

    def login(self, post_data):
        uid = self.pre_login(no_code=True)
        self.init_from_redis(uid)

        post_data = {
            self.info["param1"]: post_data["xh"],
            self.info["param2"]: post_data["pw"],
            "checkName": self.info["captcha"],
            "loginType": "1",
            "input": "登陆"
        }

        res = safe_post(self.login_url, data=post_data, headers=self.headers, cookies=self.cookies)
        html = res.content

        no_error_content(html=html, xpath="//span[@class='red']")

        rds.hdel(uid, "captcha")
        rds.hdel(uid, "param1")
        rds.hdel(uid, "param2")
        return uid

    def get_balance(self, uid):
        html = safe_get(self.balance_url, headers=self.headers, cookies=self.cookies).content
        results = safe_xpath(html, ["//font[@color='#FF0000']"])

        return results[0]

    def cal_date(self):
        now = datetime.now()
        date1 = now.strftime("%Y%m%d")
        days_ago = now - timedelta(days=7)
        date2 = days_ago.strftime("%Y%m%d")
        return [date1, date2]

    def get_consume(self):
        dates = self.cal_date()
        data = {
            "opertype": "query",
            "startDate": dates[1],
            "endDate": dates[0],
            "input": "查询"
        }

        index = 1
        consume = []
        last_count = 0

        while True:
            if index == 1:
                html = safe_post(self.consume_url, data=data, headers=self.headers, cookies=self.cookies)
                index += 1
            else:
                html = safe_get(self.consume_url+"?opertype=page&page=%s" % index, headers=self.headers, cookies=self.cookies)
                index += 1

            html = html.content.decode("utf-8")
            consume.extend(parse_standard_table(html, pure=True))

            count = len(consume)
            if count < 10 or (last_count != 10 and last_count == count):
                break
            else:
                last_count = count

        return consume

