from django.core.management.base import BaseCommand
from organisation.ascender import ascender_db_import


class Command(BaseCommand):
    help = 'Caches data from Ascender on matching DepartmentUser objects'

    def handle(self, *args, **options):
        self.stdout.write('Querying Ascender database for employee information')
        ascender_db_import(verbose=options['verbosity'] > 0)
        self.stdout.write(self.style.SUCCESS('Completed'))
