from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Application, Conversation, Job, Message, Profile, Review, User

admin.site.site_header = "Home Help administration"
admin.site.site_title = "Home Help admin"
admin.site.index_title = "Manage household jobs and accounts"


@admin.register(User)
class MoyaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Home Help", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Home Help", {"fields": ("email", "role")}),)
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")


admin.site.register(Profile)
admin.site.register(Job)
admin.site.register(Application)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(Review)
