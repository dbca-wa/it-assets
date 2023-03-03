from django.core.management.base import BaseCommand
import logging
from organisation.models import DepartmentUser
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = 'Checks the set of department user email values against Azure AD, and deletes '

    def handle(self, *args, **options):
        logger = logging.getLogger('organisation')
        logger.info('Checking currently-recorded emails for department users against Azure AD')
        aad_users = ms_graph_users()
        aad_emails = [i['mail'].lower() for i in aad_users]
        du_emails = [i.lower() for i in DepartmentUser.objects.filter(email__iendswith='@dbca.wa.gov.au', active=False).values_list('email', flat=True)]

        for email in du_emails:
            if email not in aad_emails:
                logger.info(f'{email} not found in Azure AD, deleting department user object')
                du = DepartmentUser.objects.get(email=email)
                du.delete()
