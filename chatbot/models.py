from django.db import models
from django.conf import settings

class ChatbotFAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    keywords = models.TextField(help_text="Comma-separated keywords (e.g. assignment, pending, submit)")

    def __str__(self):
        return self.question

class ChatbotReminder(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    reminder_type = models.CharField(max_length=100, help_text="e.g. inactive_days, pending_assignment, payment_due")

    def __str__(self):
        return self.title

class ChatbotConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chatbot_conversations')
    message = models.TextField()
    reply = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
