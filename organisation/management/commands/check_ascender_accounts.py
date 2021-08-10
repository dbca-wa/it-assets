from django.core.management.base import BaseCommand, CommandError
from organisation.ascender import ascender_db_import


class Command(BaseCommand):
    help = 'Caches data from Ascender on matching DepartmentUser objects'

    def handle(self, *args, **options):
        self.stdout.write('Querying Ascender database for employee information')
        try:
            ascender_db_import(verbose=options['verbosity'] > 0)
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Syncronisation from Ascender database failed')

        # TODO: update department user data from Ascender database.

        self.stdout.write(self.style.SUCCESS('Completed'))
