from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile


# edit a user's profile on the user page
class UserProfileInline(admin.StackedInline):
    model = UserProfile


class MyUserAdmin(UserAdmin):
    inlines = [UserProfileInline]


admin.site.register(User, MyUserAdmin)
