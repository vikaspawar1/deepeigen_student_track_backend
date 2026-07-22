from django.urls import path
from .views import (
    ChatbotHomeView,
    ChatbotPublicMessageView,
    ChatbotRemindersView,
    ChatbotFAQsView,
    ChatbotMessageView,
    ChatbotHistoryView,
     ChatbotPublicHomeView
)

urlpatterns = [
    path('home/', ChatbotHomeView.as_view(), name='chatbot_home'),
    path('reminders/', ChatbotRemindersView.as_view(), name='chatbot_reminders'),
    path('faqs/', ChatbotFAQsView.as_view(), name='chatbot_faqs'),
    path('message/', ChatbotMessageView.as_view(), name='chatbot_message'),
    path('history/', ChatbotHistoryView.as_view(), name='chatbot_history'),

    path('public-home/', ChatbotPublicHomeView.as_view()),
    path('public-message/', ChatbotPublicMessageView.as_view()),
]
