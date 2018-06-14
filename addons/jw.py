import re
import json
import time
import base64
import pickle
import logging
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from .utils import safe_get, safe_post, get_unique_key, rds, not_error_page, safe_re, calc_weeks
from .processImage import process
from .errors import *
from .zf_config import get_url
from .parse_html import parse_standard_table

ZF_PREFIX = "zf-user"
TIME_OUT_SECONDS = 4


def prepare_request(base_url, only_headers):
    """
    some settings before requesting
    :param base_url:
    :param only_headers:
    :return:
    """
    headers = {
        "Referer": base_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64;\
                 x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
        "Connection": "keep-alive"
    }

    if only_headers:
        return headers

    login_url = base_url + "default2.aspx"
    checkcode_url = base_url + "CheckCode.aspx"

    return login_url, checkcode_url, headers


def get_viewstate(html):
    s = r'input type="hidden" name="__VIEWSTATE" value="(.*)"'
    result = safe_re(s, html)
    return result[0]


class Login:

    def __init__(self):
        self._info = {"gnmkdm": "N121605"}
        self._COOKIES_TIME_OUT = 1000*60*5

    def _get_check_code(self, url):
        r = safe_get(url, stream=True)
        cookies = r.cookies
        return {"cookies": cookies, "img": r.content}

    def pre_login(self, no_code):
        login_url, checkcode_url, headers = prepare_request(get_url("base"), only_headers=False)
        r = safe_get(login_url, headers=headers, timeout=TIME_OUT_SECONDS)

        viewstate = get_viewstate(r.text)
        uid = get_unique_key()
        req = self._get_check_code(checkcode_url)
        pickled_cookies = pickle.dumps(req["cookies"])

        data = {
            "cookies": base64.b64encode(pickled_cookies),
            "viewstate": viewstate
        }

        if no_code:
            f = BytesIO(req["img"])
            process.set_working_key("jw")
            checkcode = "".join(process.predict(f))
            data["checkcode"] = checkcode
        else:
            data["checkcode"] = req["img"]
        rds.hmset(uid, data)
        rds.pexpire(uid, self._COOKIES_TIME_OUT)

        return uid

    def _init_from_form(self, uid, post_content):
        self._info["xh"] = post_content["username"]
        self._info["pw"] = post_content["password"]
        self._info["uid"] = uid

    def _init_from_redis(self):
        self._info["viewstate"] = rds.hget(self._info["uid"], "viewstate")
        self._info["cookies"] = pickle.loads(base64.b64decode(rds.hget(self._info["uid"], "cookies")))
        self._info["checkcode"] = rds.hget(self._info["uid"], "checkcode")

    def login(self, uid, post_content):

        self._init_from_form(uid, post_content)
        self._init_from_redis()
        login_url, checkcode_url, headers = prepare_request(get_url("base"), only_headers=False)

        data = {
            "__VIEWSTATE": self._info["viewstate"],
            "txtUserName": self._info["xh"],
            "TextBox2": self._info["pw"],
            "txtSecretCode": self._info["checkcode"],
            "RadioButtonList1": "学生",
            "Button1": "",
            "lbLanguage": "",
            "hidPdrs": "",
            "hidsc": ""
        }
        r = safe_post(login_url, data=data, headers=headers, cookies=self._info["cookies"], timeout=TIME_OUT_SECONDS)

        not_error_page(r.text, uid)

        uid = get_unique_key(ZF_PREFIX)
        s = r'<span id="xhxm">(.*?)同学'
        xm = safe_re(s, r.text)[0]
        pickled_cookies = pickle.dumps(self._info["cookies"])
        data = {
            "xh": self._info["xh"],
            "xm": xm,
            "cookies": base64.b64encode(pickled_cookies)
        }
        rds.hmset(uid, data)
        rds.pexpire(uid, self._COOKIES_TIME_OUT)
        return uid


class JW:

    _score_url = get_url("score")
    _timetable_url = get_url("timetable")
    _COOKIES_TIME_OUT = 1000*5*60

    def __init__(self, uid):
        self._headers = prepare_request(get_url("base"), only_headers=True)
        self.uid = uid
        self._cookies = None
        self._major_info = {}
        self._info = {
            "xh": rds.hget(uid, "xh"),
            "gnmkdm": "N121601",
        }

        self.init_from_redis()

    def init_from_redis(self):
        pickled_cookies = rds.hget(self.uid, "cookies")
        if pickled_cookies is None:
            raise PageError("请重新登录！")
        self._cookies = pickle.loads(base64.b64decode(pickled_cookies))
        self._info["xm"] = rds.hget(self.uid, "xm")

    def _get_html(self, url_slice, special_parameter=None, complete_url=None, only_html=True):
        url = url_slice
        if not complete_url:
            if special_parameter:
                url = url_slice % special_parameter
            else:
                url = url_slice % (self._info["xh"], self._info["xm"], self._info["gnmkdm"])
        r = safe_get(url=url, headers=self._headers, cookies=self._cookies)
        if only_html:
            return r.text
        else:
            return r.text, url

    def _parse_schedule_table(self, html, keys):
        keys = ["name", "time", "teacher", "location"]

        trs = html.find_all("tr")
        if len(trs) > 2:
            del trs[0:2]

        # trs = [trs[i] for i in range(len(trs)) if i % 2 == 0]
        classes = []

        for tr in trs:
            class_row = []

            tds = tr.find_all("td")
            for td in tds:
                class_in_td = []
                if td.string is None:
                    td_string = td.renderContents().decode()
                    _s = ["<br>", "</br>", "<br/>"]
                    for i in _s:
                        td_string = td_string.replace(i, " ")

                    class_values = td_string.split(" ")
                    class_values = [i for i in class_values if i != ""]
                    _n = len(class_values)//4

                    for _c in range(_n):
                        class_dict = {
                            "name": class_values[_c*4],
                            "teacher": class_values[_c*4+2],
                            "location": class_values[_c*4+3]
                        }
                        _rd = [r"(\d*)-(\d*)"]
                        detailed_time = []
                        for i in _rd:
                            _r = re.search(i, class_values[_c*4+1])
                            if _r:
                                detailed_time.append(_r.group(0))
                        if "单" in class_values[_c*4+1]:
                            class_dict["odd_or_even"] = "odd"
                        elif "双" in class_values[_c*4+1]:
                            class_dict["odd_or_even"] = "even"
                        else:
                            class_dict["odd_or_even"] = "false"
                        class_dict["course_during"] = detailed_time[0]
                        class_in_td.append(class_dict)
                elif td.text == "\xa0":
                    class_in_td.append({})
                if class_in_td:
                    class_row.append(class_in_td)

            classes.append(class_row)

        return classes

    def get_score(self, post_content=None):
        url = get_url("score")
        html, url = self._get_html(url, only_html=False)
        viewstate = get_viewstate(html)

        data = {
            "__VIEWSTATE": viewstate,
            "ddlXN": "",
            "ddlXQ": "",
            "Button1": "按学期查询"
        }

        if post_content:
            data["ddlXN"] = post_content["xn"]
            data["ddlXQ"] = post_content["xq"]

        html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
        keys = ["xn", "xq", "kcdm", "kcmc", "kcxz", "kcgs", "xf", "jd", "cj", "fxbj", "bkcj", "cxcj", "xymc", "bz",
                 "cxbj", "kcywmc"]
        table = parse_standard_table(html, "Datagrid1", keys=keys, pure=False)
        rds.pexpire(self.uid, self._COOKIES_TIME_OUT)

        return table

    def get_timetable(self, post_content=None):
        url = get_url("timetable")
        html, url = self._get_html(url, only_html=False)
        soup = BeautifulSoup(html, "html.parser")

        if post_content:
            selected_options = soup.find_all("option", attrs={"selected": "selected"})
            if selected_options[0].text != post_content["xn"] or selected_options[1].text != post_content["xq"]:
                viewstate = get_viewstate(html)
                data = {
                    "__VIEWSTATE": viewstate,
                    "xnd": post_content["xn"],
                    "xqd": post_content["xq"],
                }
                r = safe_post(url, data=data, headers=self._headers, cookies=self._cookies)
                html = r.text

        soup = BeautifulSoup(html, "html.parser")
        result = soup.find("table", attrs={"id": "Table1"})

        keys = ["name", "time", "teacher", "location"]
        table = self._parse_schedule_table(result, keys)
        rds.pexpire(self.uid, self._COOKIES_TIME_OUT)

        return table

    def selects_to_list(self, html, name):
        soup = BeautifulSoup(html, "html.parser")
        select = soup.find("select", attrs={"id": name})

        options = select.find_all("option")
        _t = []

        for option in options:
            _d = {"name": option.get_text(), "value": option["value"]}
            _t.append(_d)

        return _t

    # def test(self, url, data, first=True, remain_list=None):
    #
    #     if first:
    #         data = {
    #             "__EVENTTARGET": "xy",
    #             "__EVENTARGUMENT": "",
    #             "__VIEWSTATE": "",
    #             "xn": "2016-2017",
    #             "xq": "2",
    #             "nj": "2015",
    #             "xy": "",
    #             "zy": "",
    #             "kb": "",
    #         }
    #         remain_list = ["nj", "xy", "zy", "kb"]
    #         url, html = self._get_html(get_url("major_timetable"))
    #     else:
    #         html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
    #
    #     if len(remain_list) == 1:
    #         self._major_info["kb"] = self.selects_to_list(html, "kb")
    #         data["__VIEWSTATE"] = get_viewstate(html)
    #         data["__EVENTTARGET"] = "kb"
    #
    #         keys = ["name", "time", "teacher", "location"]
    #
    #         for item in self._major_info["kb"]:
    #             if item["value"] is "":
    #                 continue
    #             data["kb"] = item["value"]
    #             html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
    #             soup = BeautifulSoup(html, "html.parser")
    #             table_html = soup.find("table", attrs={"id": "Table6"})
    #             timetable = self._parse_schedule_table(table_html, keys)
    #             _t = {
    #                 "kb": item["name"],
    #                 "data": timetable,
    #             }
    #             self._belongs.update(_t)
    #             with open("major_timetables.txt", "w") as f:
    #                 f.write(str(self._belongs))
    #
    #
    #     else:
    #         viewstate = get_viewstate(html)
    #         current_mark = remain_list.pop(0)
    #         if current_mark == "nj":
    #             self._major_info["nj"] = [
    #                 {"name": "2014", "value": "2014"},
    #                 {"name": "2015", "value": "2015"},
    #                 {"name": "2016", "value": "2016"}
    #             ]
    #         else:
    #             self._major_info[current_mark] = self.selects_to_list(html, current_mark)
    #
    #         for item in self._major_info[current_mark]:
    #             print(item)
    #             if current_mark is "nj":
    #                 self._belongs = {}
    #                 remain_list = ["xy", "zy", "kb"]
    #             if current_mark is "xy":
    #                 remain_list = ["zy", "kb"]
    #             if current_mark == "zy" and item["value"] != "":
    #                 continue
    #
    #             data["__VIEWSTATE"] = viewstate
    #             data[current_mark] = item["value"]
    #             if current_mark != "zy":
    #                 self._belongs[current_mark] = item["name"]
    #                 print(self._belongs[current_mark])
    #             if current_mark == "zy":
    #                 print(data)
    #             self.test(url, data, first=False, remain_list=remain_list)

    def get_major_timetable(self):
        url = get_url("major_timetable")
        html = self._get_html(url)
        selects = {
            "nj": [
                {"name": "2014", "value": "2014"},
                {"name": "2015", "value": "2015"},
                {"name": "2016", "value": "2016"},
            ],
            "xy": self.selects_to_list(html, "xy")
        }
        data = {
            "__EVENTTARGET": "xy",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": get_viewstate(html),
            "xn": "2016-2017",
            "xq": "2",
            "nj": "2015",
            "xy": "",
            "zy": "",
            "kb": "",
        }
        keys = ["name", "time", "teacher", "location"]

        for grade in selects["nj"]:
            data["nj"] = grade["value"]
            for institute in selects["xy"]:
                data["xy"] = institute["value"]

                for i in range(2):
                    html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
                    data["__VIEWSTATE"] = get_viewstate(html)

                selects["kb"] = self.selects_to_list(html, "kb")

                for item in selects["kb"]:
                    if item["value"] == "":
                        continue

                    data["kb"] = item["value"]
                    html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
                    soup = BeautifulSoup(html, "html.parser")
                    table_html = soup.find(attrs={"id": "Table6"})
                    timetable = self._parse_schedule_table(table_html, keys)
                    _t = {
                        "grade": grade["name"],
                        "institute": institute["name"],
                        "class": item["name"],
                        "data": timetable,
                    }

    def get_timetable_weekly(self, data, weeks):
        odd_or_even = "odd" if weeks % 2 else "even"

        for i1 in range(len(data)):  # for class_row(tr) in timetable
            for i2 in range(len(data[i1])):  # for classes(td) in tr
                for i3 in range(len(data[i1][i2])):  # for class in classes
                    if data[i1][i2][i3]:
                        try:
                            # check if the current weeks is in course_during
                            course_during = data[i1][i2][i3]["course_during"].split("-")
                            if weeks < int(course_during[0]) or weeks > int(course_during[1]):
                                if i3 < 1 < len(data[i1][i2]):
                                    data[i1][i2][i3] = 0
                                else:
                                    data[i1][i2][i3] = {}
                                continue

                            # check if the current course's odd_or_even is fit to current one
                            if data[i1][i2][i3]["odd_or_even"] in ("false", odd_or_even):
                                data[i1][i2] = [data[i1][i2][i3]]
                                break
                            elif len(data[i1][i2]) == 1:
                                data[i1][i2] = [{}]

                        except ValueError as e:
                            print(e)

        return data

    def get_timetable_daily(self, data):
        weeks = calc_weeks()
        day_of_week = time.localtime(time.time()).tm_wday
        odd_or_even = "odd" if weeks % 2 else "even"
        timetable_weekly = self.get_timetable_weekly(data, weeks)
        course_of_day = []

        for i in range(len(timetable_weekly)):
            if i % 2 == 1:
                continue
            if len(timetable_weekly[i])-1 > day_of_week:
                course_list = timetable_weekly[i][day_of_week]
                if course_list == [{}]:
                    course_of_day.append({})
                    continue
                for course in course_list:
                    if course and course != 0:
                        if course["odd_or_even"] in ("false", odd_or_even):
                            course_of_day.append(course)

        return course_of_day

