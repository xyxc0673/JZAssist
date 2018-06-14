from django.db import models
from django import forms

# Create your models here.


class LoginForm(forms.Form):
    number = forms.IntegerField(
        label="", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "学号"})
    )
    password = forms.CharField(
        label="", widget=forms.TextInput(attrs={"class": "form-control", "type": "password", "placeholder": "密码"})
    )