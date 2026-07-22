"""
compute_dels.py — Management command to execute daily DELS calculation batch job.

Usage:
  python manage.py compute_dels
"""
from django.core.management.base import BaseCommand
from student_analytics.utils import run_compute_dels_job


class Command(BaseCommand):
    help = "Computes daily DELS scores, creates daily snapshots, updates course scores, and ranks students."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting daily DELS calculation..."))
        run_compute_dels_job()
        self.stdout.write(self.style.SUCCESS("Successfully computed DELS scores and updated rankings for all active users."))
