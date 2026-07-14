from django.core.management.base import BaseCommand
from subscriptions.models import PlanCategoryAccess, SubscriptionPlan


class Command(BaseCommand):
    help = 'Seed PlanCategoryAccess with default plan-to-category mappings'

    def handle(self, *args, **kwargs):
        mappings = [
            # BASIC plan: access to II only
            ('BASIC', 'II'),
            # STANDARD plan: IA + II
            ('STANDARD', 'IA'),
            ('STANDARD', 'II'),
            # PREMIUM plan: all three categories
            ('PREMIUM', 'IA'),
            ('PREMIUM', 'IB'),
            ('PREMIUM', 'II'),
        ]

        created = 0
        skipped = 0
        for plan_type, category in mappings:
            obj, was_created = PlanCategoryAccess.objects.get_or_create(
                plan_type=plan_type,
                category=category
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {plan_type} -> {category}'))
            else:
                skipped += 1
                self.stdout.write(f'  Already exists: {plan_type} -> {category}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {created} new entries, {skipped} already existed.'
        ))

        # Also report existing PlanCategoryAccess rows
        self.stdout.write('\nCurrent PlanCategoryAccess table:')
        for row in PlanCategoryAccess.objects.all().order_by('plan_type', 'category'):
            self.stdout.write(f'  {row.plan_type} -> {row.category}')
