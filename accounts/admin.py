from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http.request import HttpRequest
from .models import Account, UserProfile, company 
from django.contrib.auth.models import Group
from django.utils.html import format_html

# Register your models here.

class AccountAdmin(UserAdmin):
    def has_module_permission(self, request: HttpRequest):
        try:
            if not request.user.is_superadmin:
                return False
            else:
             return super().has_module_permission(request)
        except:
           return super().has_module_permission(request)
    list_display = ('email', 'first_name', 'last_name', 'username', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()
    

class UserProfileAdmin(admin.ModelAdmin):
    def has_module_permission(self, request: HttpRequest):
        try:
            if not request.user.is_superadmin:
                return False
            else:
             return super().has_module_permission(request)
        except:
           return super().has_module_permission(request)
   
    def thumbnail(self, object):
        return format_html('<img src="{}" width="30" style="border-radius:50%;">'.format(object.profile_picture.url))
    thumbnail.short_description = 'Profile Picture'
    list_display = ('thumbnail', 'user', 'city', 'state',)
    search_fields=("user__first_name",)

class CompanyAdmin(admin.ModelAdmin):
  def has_module_permission(self, request: HttpRequest):
        try:
            if not request.user.is_superadmin:
                return False
            else:
             return super().has_module_permission(request)
        except:
           return super().has_module_permission(request)

class GroupAdmin(admin.ModelAdmin):
   def has_change_permission(self, request, obj=None):
        if request.user.is_superadmin:
            return True  # Superuser has full access
        # Check your condition here for other users
        return False  # Restrict access if condition is not met
    
   def has_delete_permission(self, request, obj=None):
        if request.user.is_superadmin:
            return True  # Superuser has full access
        # Check your condition here for other users
        return False  # Restrict access if condition is not met
    
   def has_add_permission(self, request):
        if request.user.is_superadmin:
            return True  # Superuser has full access
        # Check your condition here for other users
        return False 
admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(company,CompanyAdmin)
admin.site.unregister(Group)
admin.site.register(Group,GroupAdmin)