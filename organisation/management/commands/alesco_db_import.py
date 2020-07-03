import traceback
from django.core.management.base import BaseCommand, CommandError
from organisation.alesco import synctask


class Command(BaseCommand):
    help = 'Synchronises user data from Alesco into the matching DepartmentUser objects'

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true', help='Also update DepartmentUser field values')

    def handle(self, *args, **options):
        try:
            synctask.alesco_db_import(update_dept_user=options['update'])
        except:
            traceback.print_exc()
            raise CommandError('Syncronisation from Alesco database failed')
