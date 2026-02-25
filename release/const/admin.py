from django.contrib import admin

# Register your models here.
from const.models import Constance


@admin.register(Constance)
class ConstanceAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'description']
    search_fields = ('key',)
