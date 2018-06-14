from django.db import models
import django.utils.timezone as timezone
# Create your models here.


class WxTimetable(models.Model):
    user = models.TextField()
    time = models.TextField()
    table = models.TextField()


class WxComment(models.Model):
    user = models.TextField()
    comment = models.TextField()
    time = models.DateTimeField(default=timezone.now())