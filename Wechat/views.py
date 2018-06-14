import os
import datetime
import logging
from django.views import View
from django.http import HttpResponse, HttpResponseBadRequest
from addons.jw import Login
from addons.jw import JW
from addons.utils import rds, store_ocr_data
from .models import WxComment
import addons.errors as errors
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.events import SubscribeEvent
from wechatpy.exceptions import (
    InvalidSignatureException,
    InvalidAppIdException,
)

logger = logging.getLogger("django.jza.wechat")


TOKEN = os.getenv("WECHAT_TOKEN")
APPID = os.getenv("WECHAT_APPID")
APPSECRET = os.getenv("WECHAT_APPSECRET")
AES_KEY = os.getenv("WECHAT_AES_KEY")

OPERATION_TIPS_TEXT = \
"""这里是菜单的标题：
---
1:登录查询
2:快速查询
3:查询资料
---
0:显示该菜单
q:删除登录状态
---
m:留言&建议
w:官网链接"""

INTERNAL_TEL_TEXT = {
    "content": "",
    "source": ""
}

SUBSCRIBE_TEXT = \
"""谢谢你的关注！

订阅号吉珠小助手lite是jza.one吉珠小助手的微信服务端。
先浏览一遍菜单，然后按需输入操作代号体验吧！\n
"""

LOGGED_TIPS_TEXT = \
"""---登录查询---
请输入操作代号：
---
1:本学期成绩
2:其他学期成绩
3:在校学习成绩
---
4:本学期课表
5:其他学期课表
---
0:显示该菜单
q:删除登录状态"""

FAST_TIPS_TEXT = \
"""---快速查询---
请按下列格式输入:
---
本学期成绩
    1&学号&密码
本学期课表
    2&学号&密码
---
0:显示该菜单
q:退出查询"""

CURRENT_MENU_TIP = "输入0获取当前模式的指令菜单。"

YEAR_AND_SEMESTER = {
    "xn": "2016-2017",
    "xq": "2"
}

REDIS_EXPIRE_TIME = 5*60


def redis_key(key):
    return "wechat-user:%s" % key


class MsgOperation(object):
    msg = None

    def _clear_status(self):
        redis_user = redis_key(self.msg.source)
        rds.delete(redis_user)
        response = "已清除用户信息，退出查询过程。\n" + CURRENT_MENU_TIP
        return response

    def _get_score(self, uid, post_content=None):
        try:
            jw = JW(uid)
            data = jw.get_score(post_content)
            if post_content:
                _s = "%s 第%s学期 成绩：\n\n" % (post_content["xn"], post_content["xq"])
            else:
                _s = "在校学习成绩：\n\n"
            for score in data:
                _s += "%s      %s\n" % (score["kcmc"], score["cj"])
            _s += "\n%s" % CURRENT_MENU_TIP
            return _s
        except errors.PageError as e:
            rds.delete(redis_key(self.msg.source))
            return "错误：%s\n%s" % (e.value, CURRENT_MENU_TIP)
        except IndexError:
            return "请求错误。"

    def _get_timetable(self, uid, post_content=None):
        jw = JW(uid)
        try:
            cycle_number = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪", ""]
            data = jw.get_timetable(post_content)
            course_of_day = jw.get_timetable_daily(data)
            _s = "%s 第%s学期 课表：\n" % (post_content["xn"], post_content["xq"])

            for index in range(len(course_of_day)):
                if course_of_day[index]:
                    _s += "\n%s%s:\n%s %s" % (cycle_number[index*2], cycle_number[index*2+1],
                                              course_of_day[index]["name"], course_of_day[index]["location"])
                else:
                    _s += "\n%s%s:\n无" % (cycle_number[index*2], cycle_number[index*2+1])

            return _s
        except errors.PageError as e:
            return e.value

    def login_mode(self, init=True):
        redis_user = redis_key(self.msg.source)
        content = self.msg.content
        if init:
            key = rds.hget(redis_user, "status")
            if key not in ("xh", "pw"):
                rds.hset(redis_user, "status", "xh")
                return "请输入学号(输入q退出查询):"
            if key == "xh":
                rds.hset(redis_user, "xh", content)
                rds.hset(redis_user, "status", "pw")
                return "请输入密码(输入q退出查询):"
            if key == "pw":
                data = {
                    "username": rds.hget(redis_user, "xh"),
                    "password": content
                }
                captcha_ocr_try = 1
                zf = Login()
                while True:
                    try:
                        uid = zf.pre_login(no_code=True)
                        uid = zf.login(uid, data)
                        store_ocr_data(captcha_ocr_try)
                        rds.hset(redis_user, "uid", uid)
                        rds.hset(redis_user, "status", "logged")
                        rds.expire(redis_user, REDIS_EXPIRE_TIME)
                        return "登录成功！\n5分钟无操作会自动删除登录状态。\n\n"+LOGGED_TIPS_TEXT
                    except errors.CheckcodeError:
                        captcha_ocr_try += 1
                    except errors.PageError as e:
                        response = self._clear_status()
                        return "%s\n%s" % (e.value, response)
        else:
            uid = rds.hget(redis_user, "uid")
            _s = rds.hget(redis_user, "status")
            if _s == "logged":
                if content == "1":
                    response = self._get_score(uid, YEAR_AND_SEMESTER)
                    if response == "":
                        response = "无法查询到 %s第%s学期 的成绩，内容为空。" % (YEAR_AND_SEMESTER["xn"], YEAR_AND_SEMESTER["xq"])
                    rds.expire(redis_key(self.msg.source), REDIS_EXPIRE_TIME)
                    return response
                if content == "2":
                    rds.hset(redis_user, "status", "year")
                    return "请按右边格式输入(eg:2016-2017学年请输入2016 或者 输入q退出查询):"
                if content == "3":
                    response = self._get_score(uid)
                    return response
                if content == "4":
                    response = self._get_timetable(uid, YEAR_AND_SEMESTER)
                    return response
            else:
                if _s == "year":
                    rds.hset(redis_user, "year", content)
                    rds.hset(redis_user, "status", "semester")
                    return "请输入学期(1:春季学期, 2:秋季学期, q:退出查询):"
                if _s == "semester":
                    year = rds.hget(redis_user, "year")
                    data = {
                        "xn": "%s-%s" % (year, int(year) + 1),
                        "xq": content
                    }
                    response = self._get_score(uid, data)
                    rds.expire(redis_user, REDIS_EXPIRE_TIME)
                    return response

    def fast_mode(self, init=True):
        redis_user = redis_key(self.msg.source)
        content = self.msg.content
        if init:
            rds.hset(redis_user, "status", "fast")
            rds.expire(redis_user, REDIS_EXPIRE_TIME)
            return FAST_TIPS_TEXT
        else:
            try:
                _t = content.split("&")
                cmd, xh, pw = _t[0], _t[1], _t[2]
            except IndexError:
                response = "指令无效！\n"+FAST_TIPS_TEXT
                return response

            data = {
                "username": xh,
                "password": pw
            }
            captcha_ocr_try = 1
            zf = Login()
            while True:
                try:
                    uid = zf.pre_login(no_code=True)
                    uid = zf.login(uid, data)
                    store_ocr_data(captcha_ocr_try)
                    if cmd == "1":
                        response = self._get_score(uid, YEAR_AND_SEMESTER)
                        rds.expire(redis_user, REDIS_EXPIRE_TIME)
                        return response
                except errors.CheckcodeError:
                    captcha_ocr_try += 1
                except errors.PageError as e:
                    response = self._clear_status()
                    return "%s\n%s" % (e.value, response)

    def comment(self, init=True):
        redis_user = redis_key(self.msg.source)
        if init:
            rds.hset(redis_user, "status", "comment")
            rds.expire(redis_user, REDIS_EXPIRE_TIME)
            response = "留言格式：\n##内容\n------\n单独输入 ### 可持续留言，并以 # 号输入结束该模式。\n谢谢支持！"
            return response
        else:
            content = self.msg.content
            is_continued = rds.hget(redis_user, "status").startswith("continued")
            if content == "#":
                rds.delete(redis_user)
                response = "已退出留言。\n"+CURRENT_MENU_TIP
                return response
            if is_continued:
                self.comment_slice(content)
                rds.expire(redis_user, REDIS_EXPIRE_TIME)
                response = "留言成功。\n输入 # 号退出留言。5分钟无操作自动退出留言。"
                return response
            elif content == "###":
                rds.hset(redis_user, "status", "continued_comment")
                response = "已开启持续留言模式。无需前缀，任何输入均为留言。回复 # 结束留言。"
                return response
            elif content.startswith("##"):
                self.comment_slice(content[2:])
                rds.delete(redis_user)
                response = "留言成功。\n"+CURRENT_MENU_TIP
                return response
            else:
                response = "格式错误，请重新留言。\n输入q退出留言。"
                return response

    def comment_slice(self, content):
        comment = WxComment(user=self.msg.source, comment=content)
        comment.save()

    def get_tip_text(self):
        redis_user = redis_key(self.msg.source)
        content = self.msg.content
        _s = rds.hget(redis_user, "status")
        response = OPERATION_TIPS_TEXT

        if _s:
            if _s in ("logged", ):
                response = LOGGED_TIPS_TEXT
            elif _s in ("fast", ):
                response = FAST_TIPS_TEXT

        return response



class WechatInterface(View, MsgOperation):

    def get(self, request, *args, **kwargs):

        signature = request.GET.get("signature")
        timestamp = request.GET.get("timestamp")
        nonce = request.GET.get("nonce")

        try:
            check_signature(TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            pass

        echostr = request.GET.get("echostr", "")
        return HttpResponse(echostr, content_type="text/plain")

    def post(self, request, *args, **kwargs):
        signature = request.GET.get("signature")
        timestamp = request.GET.get("timestamp")
        nonce = request.GET.get("nonce")
        encrypt_type = request.GET.get("encrypt_type", "raw")
        msg_signature = request.GET.get("msg_signature")

        try:
            check_signature(TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            pass

        if encrypt_type == 'raw':
            # plaintext mode
            msg = parse_message(request.body)
            if msg.type == 'text':
                reply = create_reply(msg.content, msg)
            else:
                reply = create_reply('Sorry, can not handle this for now', msg)
            return reply.render()
        else:
            # encryption mode
            from wechatpy.crypto import WeChatCrypto

            crypto = WeChatCrypto(TOKEN, AES_KEY, APPID)
            try:
                msg = crypto.decrypt_message(
                    request.body,
                    msg_signature,
                    timestamp,
                    nonce
                )
            except (InvalidSignatureException, InvalidAppIdException):
                return HttpResponseBadRequest("Failed")
            else:

                msg = parse_message(msg)
                response = "小助手无法识别输入的内容。\n"+CURRENT_MENU_TIP

                if msg.type == "event":
                    if msg.event == SubscribeEvent.event:
                        response = SUBSCRIBE_TEXT+OPERATION_TIPS_TEXT
                elif msg.type == 'text':

                    options = {
                        "help": OPERATION_TIPS_TEXT,
                        "0": self.get_tip_text,
                        "q": self._clear_status,
                        "l": "还没想好",
                        "m": self.comment,
                        "w": "在微信里点开：\nhttp://bythesea.cn\n\n用外部浏览器访问：\nhttps://jza.one"
                    }

                    self.msg = msg
                    _r = options.get(msg.content, "")
                    if _r:
                        if callable(_r):
                            response = _r()
                        elif isinstance(_r, str):
                            response = _r
                    else:
                        _s = rds.hget(redis_key(msg.source), "status")
                        logger.info(_s)
                        if _s is None:
                            if msg.content in ("1", ):
                                response = self.login_mode(init=True)
                            elif msg.content in ("2", ):
                                response = self.fast_mode(init=True)
                        elif _s in ("logged", "year", "semester"):
                            response = self.login_mode(init=False)
                        elif _s == "fast":
                            response = self.fast_mode(init=False)
                        elif _s.endswith("comment"):
                            response = self.comment(init=False)
                        elif _s in ("xh", "pw"):
                            response = self.login_mode()

                reply = create_reply(response, msg)
                encrypted_response = crypto.encrypt_message(reply.render(), nonce, timestamp)
                return HttpResponse(encrypted_response, content_type="application/xml")





