from django.core.management.base import BaseCommand, CommandError
from organisation.ascender import ascender_db_import


class Command(BaseCommand):
    help = 'Synchronises user data from Ascender into the matching DepartmentUser objects'

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true', help='Also update DepartmentUser field values')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Querying Ascender database for employee information'))
        try:
            ascender_db_import()
            self.stdout.write(self.style.SUCCESS('Completed'))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Syncronisation from Ascender database failed')
