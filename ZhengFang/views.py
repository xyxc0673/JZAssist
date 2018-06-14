import logging
from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from addons.jw import Login, JW
from addons.utils import rds, store_ocr_data, calc_weeks
from .forms import LoginForm
import addons.errors as errors

logger = logging.getLogger("django.jza.zhengfang")


def index(request):
    captcha_ocr = {
        "total": rds.hget("captcha_ocr", "total"),
        "success": rds.hget("captcha_ocr", "success")
    }
    return render(request, "index.html", {"captcha_ocr": captcha_ocr})


def wechat_index(request):
    return render(request, "weixin.html")


def about(request):
    return render(request, "about.html")


def calc(xh):
    start_year = int("20"+xh[2:4])

    import time
    last_year = time.localtime().tm_year
    current_mon = time.localtime().tm_mon
    if current_mon >= 6:
        last_year += 1

    years = []
    for i in range(0, last_year-start_year):
        years.append("%d-%d" % (start_year+i, start_year+i+1))

    return years


class NoCodeLogin(View):

    def get(self, request, *args, **kwargs):
        logger.info("test")
        form = LoginForm()
        return render(request, "login.html", {"form": form})

    def post(self, request, *args, **kwargs):
        form = LoginForm(request.POST)
        form.is_valid()
        captcha_ocr_try = 1
        zf = Login()
        while True:
            try:
                uid = zf.pre_login(True)
                uid = zf.login(uid, form.data)
                store_ocr_data(captcha_ocr_try)
                request.session["zf-uid"] = uid
                search = []
                if "score" in form.data:
                    search.append("score")
                if "timetable" in form.data:
                    search.append("timetable")
                request.session["search"] = search
                return HttpResponseRedirect("/assist")
            except errors.CheckcodeError:
                captcha_ocr_try += 1
            except errors.PageError as e:
                form = LoginForm()
                return render(request, "login.html", {"form": form, "error": e.value})
            except TimeoutError as e:
                return JsonResponse(data={"error": e})


class Search(View):

    def get(self, request, *args, **kwargs):
        uid = request.session.get("zf-uid")
        xh = rds.hget(uid, "xh")
        if not xh:
            return redirect("/assist/login")
        try:
            years = calc(xh)
            jw = JW(uid)
            option = request.session.get("search")
            info = {}

            if "timetable" in option:
                weeks = calc_weeks()
                odd_or_even = "odd" if weeks % 2 else "even"
                timetable = jw.get_timetable()
                timetable = jw.get_timetable_weekly(timetable, weeks)
                info["timetable"] = {
                    "name": "课表",
                    "weeks": weeks,
                    "odd_or_even": odd_or_even,
                    "data": timetable
                }

            if "score" in option:
                score = jw.get_score()
                info["score"] = {"name": "成绩", "data": score}

            return render(request, "info.html", {"info": info, "years": years})
        except errors.RequestError as e:
            return HttpResponse(e)

    def post(self, request, *args, **kwargs):
        uid = request.session.get("zf-uid")
        xh = rds.hget(uid, "xh")
        if xh is None:
            return HttpResponseRedirect("/assist/login")
        try:
            years = calc(xh)
            jw = JW(uid)
            data = {
                "xn": request.POST["xn"],
                "xq": request.POST["xq"],
            }
            info = {}

            if "score" in request.POST:
                score = jw.get_score(data)
                info["score"] = {"name": "成绩", "data": score}

            if "timetable" in request.POST:
                weeks = calc_weeks()
                timetable = jw.get_timetable(post_content=data)
                info["timetable"] = {
                    "name": "课表",
                    "weeks": weeks,
                    "week_type": "odd" if weeks % 2 else "even",
                    "data": timetable
                }
            print(info)
            return render(request, "info.html", {"info": info, "years": years})
        except errors.RequestError as e:
            return HttpResponse(e)
        except errors.PageError as e:
            return HttpResponse(e)



