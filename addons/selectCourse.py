import re
import os
import sys
import time
import json
import pickle
import requests
from bs4 import BeautifulSoup
from lxml import etree
from requests import TooManyRedirects
from addons.errors import *
from addons.jw import Login, JW, get_viewstate, safe_post, safe_get
from addons.utils import not_error_page, pretty_table, safe_re
from addons.zf_config import get_url
from addons.parse_html import parse_standard_table

INDEX_TXT = """
#   选课   #
1: 选修课
2: 院公选课
3: 体育课

#   评教   #
5: auto

Q: 开始选课

#   其他   #
w: 查看愿望清单
q: 退出
"""

INPUT_ERROR_TEXT = "\n输入信息有误"


class SelectCourse(JW):

    def get_course_category(self):
        special = "xnxq=%s&xh=%s"
        _t = ("2016-20171", self._info["xh"])
        url = get_url("course_category", special)
        html = self._get_html(url, _t)
        not_error_page(html, self.uid)
        selects = self.selects_to_list(html, "ListBox1")
        return selects

    def get_index_ec(self):
        url = get_url("selective_course")
        html = self._get_html(url)
        not_error_page(html)
        courses = parse_standard_table(html, "kcmcgrid", pure=True)
        url_code = re.findall(r'xkkh=(.*?)&', html)
        return url_code, courses

    def get_elective_course(self, category):
        while True:
            url = get_url("selective_course")
            html, url = self._get_html(url, only_html=False)
            if "三秒防刷" in html:
                print("\n检测到三秒防刷，程序将睡眠三秒钟。")
                time.sleep(3)
            else:
                break
        viewstate = get_viewstate(html)

        post_data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "zymc": "",
            "xx": "",
            "Button2": "选修课程"
        }

        html = safe_post(url=url, data=post_data, headers=self._headers, cookies=self._cookies).text

        post_data["zymc"] = (category + "|院公选课5").encode("gb2312")
        del post_data["Button2"]

        num = 0
        current_page = 1
        courses = []
        url_code = []
        page_num = []

        while True:
            try:
                post_data["__VIEWSTATE"] = get_viewstate(html)

                html = safe_post(url=url, data=post_data, headers=self._headers, cookies=self._cookies).text
                _t = parse_standard_table(html, "kcmcgrid", pure=True)
                courses.extend(_t)
                _t = re.findall(r'xkkh=(.*?)&', html)
                url_code.extend(_t)

                if num == 0:
                    num = int(re.search(r'共(\d*)条记录！', html).group(1))

                if (current_page % 10) == 1:
                    page_num = re.findall(r'kcmcgrid\$_ctl\d*\$_ctl\d*', html)
                    if (current_page // 10) == 1:
                        _n = 10 - (num // 10 - 9)
                        page_num = [page_num[i] for i in range(len(page_num)) if i > _n]

                if len(page_num) == 0:
                    break

                current_page += 1
                post_data["__EVENTTARGET"] = page_num.pop(0).replace("$", ":")
            except AttributeError:
                print("\n检测到三秒防刷，程序将睡眠三秒钟。")
                time.sleep(3)
        return url_code, courses

    def get_course_detail(self, url_code):
        special = "xkkh=%s&xh=%s"
        _t = (url_code, self._info["xh"])

        url = get_url("course_detail", special)
        html = self._get_html(url, _t)
        not_error_page(html, self.uid)
        classroom_selection = re.findall(r'value="(.*?)".*?xkkh', html)
        result = parse_standard_table(html, "xjs_table", pure=True)
        return result, classroom_selection

    def select_elective_course(self, url_code, selected_classroom):
        special = "xkkh=%s&xh=%s"
        _t = (url_code, self._info["xh"])

        url = get_url("course_detail", special)
        html, url = self._get_html(url, _t, only_html=False)
        viewstate = get_viewstate(html)

        data = {
            "__EVENTTARGET": "Button1",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "xkkh": selected_classroom,
            "RadioButtonList1": 0,
        }

        html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
        result = safe_re(r"alert\('(.*)'\)", html)
        return result

    def get_PEC_category(self, category=None):
        url = get_url("pe_class")
        html, url = self._get_html(url, only_html=False)
        if category:
            viewstate = get_viewstate(html)
            data = {
                "__EVENTTARGET": "ListBox1",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": viewstate,
                "DropDownList1": "项目".encode("gb2312"),
                "ListBox1": category
            }
            html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
            select_name = "ListBox2"
        else:
            select_name = "ListBox1"
        selects = self.selects_to_list(html, select_name)
        return selects

    def select_PE_class(self, code1, code2):
        url = get_url("pe_class")
        html, url = self._get_html(url, only_html=False)
        viewstate = get_viewstate(html)
        data = {
            "__EVENTTARGET": "ListBox1",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "DropDownList1": "项目".encode("gb2312"),
            "ListBox1": code1
        }
        html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
        _t = {
            "__VIEWSTATE": get_viewstate(html),
            "ListBox2": code2,
            "RadioButtonList1": "0",
            "button3": "选定课程"
        }
        data.update(_t)
        html = safe_post(url, data=data, headers=self._headers, cookies=self._cookies).text
        result = safe_re(r"alert\('(.*)'\)", html)
        return result

    def get_evaluate_course(self):
        url = get_url("evaluate_list", special="xh=%s")
        html = self._get_html(url, special_parameter=self._info["xh"])
        page = etree.HTML(html)
        course_list = page.xpath('//*[@id="headDiv"]/ul/li[4]/ul/li/a/@href')
        return course_list

    def evaluate_teacher(self, mark):
        course_list = self.get_evaluate_course()
        url = get_url("base")

        for index in range(len(course_list)):
            html = self._get_html(url+course_list[index], complete_url=True)
            viewstate = get_viewstate(html)
            page = etree.HTML(html)

            alert = page.xpath('//*[@id="Form1"]/script[2]')
            if alert:
                not_error_page(alert[0].text)

            current_course = page.xpath('//*[@id="pjkc"]/option[@selected="selected"]/@value')
            print("\nStart evaluating %s ..." % current_course[0])

            hidden_input = page.xpath('//*[@id="DataGrid1"]//input/@name')
            selects = page.xpath('//*[@id="DataGrid1"]//select/@name')

            data = {
                "__EVENTTARGET": "",
                "__EVENTARGUMENT": "",
                "__VIEWSTATE": viewstate,
                "pjkc": current_course[0],
                "pjxx": "",
                "txt1": "",
                "TextBox1": "0",
                "Button1": "保  存"
            }

            for i in range(len(hidden_input)):
                _data = {
                    hidden_input[i]: "",
                    selects[i]: mark.encode("gb2312")
                }
                data.update(_data)

            if index == len(course_list)-1:
                data.pop("Button1")
                data["Button2"] = " 提  交 "

            html = safe_post(url+course_list[index], data=data, headers=self._headers, cookies=self._cookies).text
            page = etree.HTML(html)
            alert = page.xpath('//*[@id="Form1"]/script[2]')
            if alert:
                raise PageError(alert.text)

            if index < len(course_list)-1:
                print("Finish and sleep for 2s")
                time.sleep(2)
            elif index == len(course_list)-1:
                print("Finish")
                return "\nEvaluation finish"

if __name__ == "__main__":
    wishlist = {"elective": [], "pe": []}
    with open("user.txt", "r") as f:
        post_content = {
            "username": f.readline().strip(),
            "password": f.readline().strip(),
        }
    zf = Login()

    while True:
        try:
            uid = zf.pre_login(no_code=True)
            uid = zf.login(uid, post_content)
            break
        except CheckcodeError as e:
            continue
        except PageError as e:
            print(e.value)
            break

    process = SelectCourse(uid)

    def query_index_ec():
        url_code, courses = process.get_index_ec()
        _code = [m[0] for m in courses]
        url_code = dict(zip(_code, url_code))
        keys = ["序号", "课程代码", "课程名称", "课程性质", "组或模块", "学分", "周学时", "考试时间", "课程介绍", "选否", "余量"]
        pt = pretty_table(keys, courses, serial_number=True)
        print("")
        print(pt)
        query_course_detail(url_code, courses, "选修课")

    def query_elective_course():
        category = process.get_course_category()

        print("")
        for i in range(len(category)):
            print("%s: %s" % (i, category[i]["name"]))

        while True:
            try:
                _i = int(input("\n请输入将要查询的院公选课的课程分类序号(可留空查询全部课程 或者 输入-1退出):"))

                if _i == -1:
                    break
                if _i == "":
                    _i = len(category) - 1

                url_code, courses = process.get_elective_course(category[_i]["value"])

                if len(courses) == 0:
                    print("\n该分类下没有可供选择的课程")
                else:
                    _code = [m[0] for m in courses]
                    url_code = dict(zip(_code, url_code))
                    keys = ["序号", "课程代码", "课程名称", "课程性质", "组或模块", "学分", "周学时", "考试时间", "课程介绍", "选否", "余量"]
                    pt = pretty_table(keys, courses, serial_number=True)
                    print("\n当前分类：" + category[_i]["name"])
                    print(pt)
                    query_course_detail(url_code, courses, "院公选课")
                    break

            except IndexError:
                print(INPUT_ERROR_TEXT)
            except ValueError:
                print(INPUT_ERROR_TEXT)


    def query_course_detail(url_code, courses, _type):
        while True:
            try:
                _i = int(input("\n请输入%s的序号(输入-1退出):" % _type))
                if _i == -1:
                    break
                _code = url_code[courses[_i][0]]
                course_detail, classroom_selection = process.get_course_detail(_code)
                course_name = courses[_i][1]

                keys = ["序号", "教师姓名", "教学班/开课学院", "周学时", "考核", "上课时间", "上课地点", "校区", "备注", "授课方式", "是否短学期",
                        "容量(人数)", "教材名称", "本专业已选人数", "所有已选人数", "选择情况"]
                pt = pretty_table(keys, course_detail, serial_number=True)
                print("\n当前课程：" + course_name)
                print(pt)

                select_elective_course(_code, classroom_selection, course_detail, course_name)
            except IndexError:
                print(INPUT_ERROR_TEXT)
            except ValueError:
                print(INPUT_ERROR_TEXT)

    def select_elective_course(url_code, classroom_selection, course_detail, course_name):
        while True:
            try:
                _i = int(input("\n请输入开课班级的序号(输入-1退出):"))
                if _i == -1:
                    break
                data = {
                    "name": course_name,
                    "teacher": course_detail[_i][0],
                    "time": course_detail[_i][4],
                    "location": course_detail[_i][5],
                    "url_code": url_code,
                    "selected_classroom": classroom_selection[_i],
                }
                wishlist["elective"].append(data)
                save_to_file("wishlist.txt", data=wishlist)
                print("\n%s | %s | %s | %s" % (data["name"], data["teacher"], data["time"], data["location"]))
                print("\n成功保存到wishlist.txt")
                break

            except IndexError:
                print(INPUT_ERROR_TEXT)
            except ValueError:
                print(INPUT_ERROR_TEXT)

    def query_pe_class():
        PEC_category = process.get_PEC_category()
        print("")
        for i in range(len(PEC_category)):
            print("%s: %s" % (i, PEC_category[i]["name"]))
        while True:
            try:
                _i = int(input("\n请输入体育课程的序号(输入-1退出):"))
                if _i == -1:
                    break
                else:
                    _class = process.get_PEC_category(PEC_category[_i]["value"])
                    print("")
                    for i in range(len(_class)):
                        print("%s: %s" % (i, _class[i]["name"]))
                    _t = int(input("\n请输入开课班级的序号(输入-1退出):"))
                    if _t == -1:
                        break
                    else:
                        class_info_list = _class[_t]["name"].split("∥")

                        data = {
                            "name": PEC_category[_i]["name"].split("∥")[1],
                            "teacher": class_info_list[2],
                            "time": class_info_list[4],
                            "location": class_info_list[5],
                            "code1": PEC_category[_i]["value"],
                            "code2": _class[_t]["value"],
                        }
                        wishlist["pe"].append(data)
                        save_to_file("wishlist.txt", wishlist)
                        print("\n%s | %s | %s | %s" % (data["name"], data["teacher"], data["time"], data["location"]))
                        print("\n成功保存到wishlist.txt")

            except IndexError:
                print(INPUT_ERROR_TEXT)

    def grab_course():
        if len(wishlist["elective"]) == 0:
            if len(wishlist["pe"]) == 0:
                print("\n无待选课程，退出选课")
            else:
                worklist = wishlist["pe"]
                current_mark = "pe"
                print("\n### 体育选课 ###")
        else:
            worklist = wishlist["elective"]
            current_mark = "elective"
            print("\n\n### 普通选课 ###")

        sleep_time = 10
        while len(worklist):
            for course in worklist:
                print("\n--- \033[34;0m%s | %s | %s | %s\033[0m" % (course["name"], course["teacher"],
                                                                    course["time"], course["location"]))
                if current_mark == "elective":
                    ret = process.select_elective_course(course["url_code"], course["selected_classroom"])
                    if "现在不是选课时间！" in ret:
                        print("\n--- \033[31;0m现在不是选课时间，退出普通选课。\033[0m")
                    elif "成功" in ret:
                        print("\n--- \033[32;0m选课成功\033[0m")
                        worklist.remove(course)
                else:
                    ret = process.select_PE_class(course["code1"], course["code2"])
                    if "只能选1门体育课！！" in ret:
                        print("\n--- \033[31;0m只能选1门体育课，退出体育选课。\033[0m\n")
                        break

            if current_mark == "elective":
                print("\n\nSleeping for 2s...")
                time.sleep(2)
                worklist = wishlist["pe"]
                print("\n\n### 体育选课 ###")
                current_mark = "pe"
                continue
            elif current_mark == "pe":
                break

    def view_wishlist():
        while True:

            keys = ["序号", "分类", "课程名称", "教师姓名", "上课时间", "上课地点"]
            _t = [["elective", i["name"], i["teacher"], i["time"], i["location"]] for i in wishlist["elective"]]
            _t.extend([["pe", i["name"], i["teacher"], i["time"], i["location"]] for i in wishlist["pe"]])
            pt = pretty_table(keys, _t, serial_number=True)
            print("\n{}".format(pt))
            try:
                _i = input("\n输入序号以删除对应的课程(输入all删除所有Elective课程 或 输入allpe删除所有PE课程 或 输入-1返回主菜单):")
                if _i == "-1":
                    break
                elif _i.startswith("all"):
                    if _i == "all":
                        wishlist["elective"].clear()
                    elif _i == "allpe":
                        wishlist["pe"].clear()
                    else:
                        print(INPUT_ERROR_TEXT)
                        continue
                    print("\n已清空相关愿望清单")
                    save_to_file("wishlist.txt", wishlist)
                else:
                    _i = int(_i)

                    mark = _t[_i][0]
                    if mark == "pe":
                        _i -= len(wishlist["elective"])

                    del wishlist[mark][int(_i)]
                    save_to_file("wishlist.txt", wishlist)
            except IndexError:
                print(INPUT_ERROR_TEXT)
            except KeyError:
                print(INPUT_ERROR_TEXT)
            except ValueError:
                print(INPUT_ERROR_TEXT)

    def evaluate_teacher():
        mark = "B（良好）"
        result = process.evaluate_teacher(mark=mark)
        print(result)

    def save_to_file(file, data):
        data = json.dumps(data)
        with open(file, "w+") as f:
            f.write(data)

    def read_from_file(file):
        with open(file, "r+") as f:
            data = f.read()
            data = json.loads(data)
        return data

    def remove_key(data):
        keys = data[0].keys()
        result = []

        for i in data:
            _t = []
            for x, y in i.items():
                _t.append(y)
            result.append(_t)

        return keys, result

    try:
        wishlist = read_from_file("wishlist.txt")
    except:
        pass

    options = {
        "1": query_index_ec,
        "2": query_elective_course,
        "3": query_pe_class,
        "5": evaluate_teacher,
        "Q": grab_course,
        "q": exit,
        "w": view_wishlist,
    }

    while True:
        try:
            print(INDEX_TXT)

            cmd = input("请输入操作代号:")
            options.get(cmd, lambda: print("\n指令错误"))()

        except TooManyRedirects:
            print("\n无法连接到教务系统。")
        except PageError as e:
            print("\n" + e.value)

        print("\n输入任意内容继续...")
        input()

