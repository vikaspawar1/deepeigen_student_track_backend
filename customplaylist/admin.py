from django.contrib import admin
from .models import CustomPlaylist, PlaylistLecture, Invoice

class PlaylistLectureInline(admin.TabularInline):
    model = PlaylistLecture
    extra = 1

class CustomPlaylistAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'total_price', 'is_purchased', 'status', 'created_at')
    list_filter = ('is_purchased', 'status', 'created_at')
    search_fields = ('title', 'user__email', 'user__first_name')
    inlines = [PlaylistLectureInline]

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('playlist_name', 'user', 'amount', 'purchase_type', 'date')
    list_filter = ('purchase_type', 'date')
    search_fields = ('playlist_name', 'user__email', 'user__first_name')

admin.site.register(CustomPlaylist, CustomPlaylistAdmin)
admin.site.register(Invoice, InvoiceAdmin)
