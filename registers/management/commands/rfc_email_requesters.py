from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from pytz import timezone
from registers.models import ChangeRequest, ChangeLog


class Command(BaseCommand):
    help = 'Emails requesters to record completion of any outstanding change requests.'

    def handle(self, *args, **options):
        # All changes of status "Ready", where the planned_end datetime has passed and completed datetime is null:
        rfcs = ChangeRequest.objects.filter(
            status=3, planned_end__lte=datetime.now().astimezone(timezone(settings.TIME_ZONE)), completed__isnull=True)

        for rfc in rfcs:
            if rfc.requester:
                msg = 'Request for completion record-keeping emailed to {}.'.format(rfc.requester.get_full_name())
                rfc.email_requester()
                log = ChangeLog(change_request=rfc, log=msg)
                log.save()
