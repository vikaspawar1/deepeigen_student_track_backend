import json
from django.core.management.base import BaseCommand
from django.core.management import call_command
from io import StringIO

class Command(BaseCommand):
    help = 'Dump entire database excluding specific fields from EnrolledUser model and excluding certain models'

    def handle(self, *args, **kwargs):
        # Step 1: Dump the entire database
        out = StringIO()
        call_command('dumpdata', stdout=out)
        out.seek(0)
        data = json.loads(out.read())

        # Step 2: Filter out contenttypes, auth.Permission, and modify EnrolledUser
        filtered_data = []
        for item in data:
            if item['model'] == 'course.enrolleduser':
                if 'invoice' in item['fields']:
                    del item['fields']['invoice']
                if 'serial_no' in item['fields']:
                    del item['fields']['serial_no']
                filtered_data.append(item)
            elif item['model'] not in ['contenttypes.contenttype', 'auth.permission']:
                filtered_data.append(item)

        # Step 3: Write the modified data to a JSON file
        with open('custom_dump.json', 'w') as json_file:
            json.dump(filtered_data, json_file, indent=4)

        self.stdout.write(self.style.SUCCESS('Successfully dumped the database to custom_dump.json'))
