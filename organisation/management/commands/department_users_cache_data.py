from django.core.management.base import BaseCommand, CommandError
from organisation.ascender import ascender_db_import
from organisation.utils import onprem_ad_data_import, azure_ad_data_import


class Command(BaseCommand):
    help = 'Caches data from Ascender, on-prem AD and Azure AD into the matching DepartmentUser objects'

    def handle(self, *args, **options):
        self.stdout.write('Querying Ascender database for employee information')
        try:
            ascender_db_import()
            self.stdout.write(self.style.SUCCESS('Completed'))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Syncronisation from Ascender database failed')

        self.stdout.write('Querying on-premise AD data for employee information')
        try:
            onprem_ad_data_import()
            self.stdout.write(self.style.SUCCESS('Completed'))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Syncronisation from on-premise AD data failed')

        self.stdout.write('Querying Azure AD data for employee information')
        try:
            azure_ad_data_import()
            self.stdout.write(self.style.SUCCESS('Completed'))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(ex))
            raise CommandError('Syncronisation from Azure AD data failed')
