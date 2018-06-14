from django.shortcuts import render
from django.views import View
from django.http import HttpResponseRedirect
from .models import LoginForm
from addons.libr import Lib
from addons.errors import *
# Create your views here.


class Login(View):
    def get(self, request, *args, **kwargs):
        form = LoginForm()
        return render(request, "lib_login.html", {"form": form})

    def post(self, request, *args, **kwargs):
        form = LoginForm(request.POST)
        form.is_valid()
        lib = Lib()
        while True:
            try:
                uid = lib.pre_login(no_code=True)
                uid = lib.login(uid, form.data)
                request.session["lib-uid"] = uid
                return HttpResponseRedirect("/lib")
            except CheckcodeError:
                continue
            except PageError as e:
                return render(request, "lib_login.html", {"form": form, "error": e.value})


class Index(View):
    def get(self, request, *args, **kwargs):
        uid = request.session.get("lib-uid")
        if not uid:
            return HttpResponseRedirect("/lib/login")
        try:
            lib = Lib()
            remind_books = lib.get_checkout_book(uid)
            return render(request, "lib_index.html", {"remind_books": remind_books})
        except PageError as e:
            pass