from django.core.management.base import BaseCommand, CommandError
from status.utils import run_all


class Command(BaseCommand):
    help = 'Runs a full scan of all plugins in the status application'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Running a full scan'))
        try:
            run_all()
            self.stdout.write(self.style.SUCCESS('Completed'))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Status full scan failed')
