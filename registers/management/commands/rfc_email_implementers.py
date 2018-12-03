from django.core.management.base import BaseCommand
from registers.models import ChangeRequest, ChangeLog


class Command(BaseCommand):
    help = 'Emails implementers a request to record completion of any outstanding change requests.'

    def handle(self, *args, **options):
        # All incomplete changes of status "Ready":
        rfcs = ChangeRequest.objects.filter(status=3, completed__isnull=True)

        for rfc in rfcs:
            msg = 'Request for completion record-keeping emailed to {}.'.format(rfc.implementer.get_full_name())
            rfc.email_implementer()
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
