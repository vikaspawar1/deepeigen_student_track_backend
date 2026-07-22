from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatbot.models import ChatbotConversation


class Command(BaseCommand):
    help = "Deletes chatbot conversations older than 12 hours for all users"

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(hours=12)
        deleted_count, _ = ChatbotConversation.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} old conversations."))




