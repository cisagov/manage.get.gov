from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):

    """Edit a user's profile on the user page."""

    model = UserProfile


class MyUserAdmin(UserAdmin):

    """Custom user admin class to use our inlines."""

    inlines = [UserProfileInline]


admin.site.register(User, MyUserAdmin)
