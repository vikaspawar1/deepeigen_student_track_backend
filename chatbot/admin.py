from django.contrib import admin
from .models import ChatbotFAQ, ChatbotReminder, ChatbotConversation

@admin.register(ChatbotFAQ)
class ChatbotFAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'keywords')
    search_fields = ('question', 'keywords')

@admin.register(ChatbotReminder)
class ChatbotReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'reminder_type')
    search_fields = ('title', 'reminder_type')

@admin.register(ChatbotConversation)
class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'timestamp')
    search_fields = ('user__email', 'message', 'reply')
    list_filter = ('timestamp',)
    readonly_fields = ('timestamp',)
