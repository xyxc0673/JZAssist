from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView
from rest_framework import permissions
from addons.jw import Login
from addons.jw import JW
from addons.libr import Lib
from addons.errors import *


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


class ZFLogin(APIView):

    def post(self, request, format=None):
        data = request.data
        zf = Login()
        while True:
            try:
                uid = zf.pre_login(no_code=True)
                uid = zf.login(uid, data)
                jw = JW(uid)
                timetable = jw.get_timetable()
                score = jw.get_score()
                return JSONResponse(data={"code": "0", "uid": uid, "data": {"timetable": timetable, "score": score}})
            except CheckcodeError:
                continue
            except PageError as e:
                return JSONResponse(data={"code": "1", "error": e.value})
            except TimeoutError as e:
                return JSONResponse(data={"error": e})

    def get(self, request, format=None):
        return Response({"error": "error"})

class Search(APIView):

    def post(self):
        pass


class LibLogin(APIView):

    def post(self, request, format=None):
        data = request.data
        lib = Lib()
        while True:
            try:
                uid = lib.pre_login(no_code=True)
                uid = lib.login(uid, data)
                books = lib.get_checkout_book(uid)
                return JSONResponse(data={"code": "0", "uid": uid, "data": {"books": books}})
            except CheckcodeError:
                continue
            except PageError as e:
                return JSONResponse(data={"code": "1", "error": e.value})
            except TimeoutError as e:
                return JSONResponse(data={"error": e})

class Feedback(APIView):
    def post(self, request, format=None):
        data = request.data
