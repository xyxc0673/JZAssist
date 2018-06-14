from django import forms


class LoginForm(forms.Form):
    username = forms.IntegerField(label="", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "学号"}))
    password = forms.CharField(label="", widget=forms.TextInput(attrs={"class": "form-control", "type": "password", "placeholder": "密码"}))
