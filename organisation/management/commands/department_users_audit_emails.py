import logging

from django.core.management.base import BaseCommand

from organisation.models import DepartmentUser
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = "Checks the set of inactive department user email values against Entra ID, and deletes any having an email not found in Azure"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Checking currently-recorded emails for department users against Azure AD")
        entra_users = ms_graph_users()
        entra_emails = [i["mail"].lower() for i in entra_users if i["mail"]]
        du_emails = [
            i.lower()
            for i in DepartmentUser.objects.filter(email__iendswith="@dbca.wa.gov.au", active=False).values_list("email", flat=True)
        ]

        for email in du_emails:
            if email not in entra_emails:
                logger.info(f"{email} not found in Entra ID, deleting department user object")
                du = DepartmentUser.objects.get(email=email)
                du.delete()
