from django.contrib import admin
from django.http.request import HttpRequest
from django.utils.html import format_html

# Register your models here.
from .models import Team

class TeamAdmin(admin.ModelAdmin):
    def profilephoto(self, object):
        return format_html('<img src="{}" width="50" style="border-radius:50%;">'.format(object.photo.url))
    
    def has_module_permission(self, request: HttpRequest) :
        try:
            if request.user.is_superadmin:
               return super().has_module_permission(request)
            else:
                return False
        except:
            return False
    
    def has_add_permission(self, request: HttpRequest):
        try:
            if not request.user.is_superadmin:
                return False
            else:
             return super().has_add_permission(request)
        except:
            return super().has_add_permission(request)

    list_display = ('id','profilephoto','first_name', 'last_name', 'role', 'job_role')
    list_display_links = ('profilephoto','first_name', 'last_name')
    search_fields = ('first_name', 'role', 'job_role')
    ordering = ('id',)

admin.site.register(Team, TeamAdmin)



# from django.contrib import admin
# from django.utils.html import format_html

# # Register your models here.
# from .models import Team

# class TeamAdmin(admin.ModelAdmin):
#     def profilephoto(self, object):
#         return format_html('<img src="{}" width="50" style="border-radius:50%;">'.format(object.photo.url))

#     list_display = ('id','profilephoto','first_name', 'last_name')
#     list_display_links = ('profilephoto','first_name', 'last_name')
#     search_fields = ('first_name', 'role')
#     ordering = ('id',)

# admin.site.register(Team, TeamAdmin)