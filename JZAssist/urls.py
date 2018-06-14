"""JZAssist URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.conf.urls import url, include
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from rest_framework import routers, serializers, viewsets
from ZhengFang.views import index as zhengfang_index
from ZhengFang.views import NoCodeLogin as zhengfang_login
from ZhengFang.views import Search as zhengfang_info
from ZhengFang.views import wechat_index as wechat_index
from ZhengFang.views import about as about
from Library.views import Login as lib_login
from Library.views import Index as lib_index
from Api.views import ZFLogin as api_zf_login
from Api.views import LibLogin as api_lib_login
from Wechat.views import WechatInterface as wechat_interface

# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'is_staff')

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', zhengfang_index),
    url(r'^assist/login/$', zhengfang_login.as_view()),
    url(r'^assist/$', zhengfang_info.as_view()),
    url(r'^lib/login/$', lib_login.as_view()),
    url(r'^lib/', lib_index.as_view()),
    url(r'^weixin/$', wechat_index),
    url(r'^about/$', about),
    url(r'^wechat/$', csrf_exempt(wechat_interface.as_view())),
    url(r'^api/jw/login/$', api_zf_login.as_view()),
    url(r'^api/lib/login/$', api_lib_login),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]
