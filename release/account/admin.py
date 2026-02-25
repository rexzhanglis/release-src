from django.contrib import admin

# Register your models here.
from account.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'chinese_name', 'email', 'mobile', 'is_staff', 'is_active', 'last_login',
                    'last_updated_time']
    search_fields = ('username', 'mobile')
    exclude = ('password',)
    ordering = ('-last_login',)
    filter_horizontal = ('groups', 'user_permissions')
