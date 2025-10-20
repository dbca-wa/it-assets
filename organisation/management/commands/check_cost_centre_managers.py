import logging

from django.core.management.base import BaseCommand

from organisation.ascender import ascender_cc_manager_fetch
from organisation.models import CostCentre, DepartmentUser


class Command(BaseCommand):
    help = "Queries data from Ascender to update Cost Centre managers"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Querying Ascender database for cost centre manager information")
        records = ascender_cc_manager_fetch()

        for record in records:
            cc_ascender_code = record[1]
            employee_id = record[6]
            if (
                CostCentre.objects.filter(ascender_code=cc_ascender_code).exists()
                and DepartmentUser.objects.filter(employee_id=employee_id).exists()
            ):
                cc = CostCentre.objects.get(ascender_code=cc_ascender_code)
                manager = DepartmentUser.objects.get(employee_id=employee_id)
                if cc.manager != manager:
                    cc.manager = manager
                    cc.save()
                    logger.info(f"{cc} updated ({cc.manager})")

        logger.info("Completed")
