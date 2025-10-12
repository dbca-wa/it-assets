import logging

from django.core.management.base import BaseCommand

from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = "Checks DepartmentUser objects for cached data which may be invalid or outdated"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Checking DepartmentUser objects for outdated cached data")

        # Check for any DepartmentUser objects not having any links to Entra ID or onprem AD.
        for du in DepartmentUser.objects.filter(ad_guid__isnull=True, azure_guid__isnull=True):
            du.active = False
            du.proxy_addresses = None
            du.assigned_licences = []
            du.account_type = 14  # Unknown
            du.ad_data = {}
            du.ad_data_updated = None
            du.azure_ad_data = {}
            du.azure_ad_data_updated = None
            du.dir_sync_enabled = None
            du.last_signin = None
            du.last_password_change = None

            if du.employee_id is None:
                du.ascender_data = {}
                du.ascender_data_updated = None

            logger.info(f"Clearing cached data from {du}")
            du.save()
