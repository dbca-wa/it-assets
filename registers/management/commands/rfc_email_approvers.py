from django.core.management.base import BaseCommand
from registers.models import ChangeRequest, ChangeLog


class Command(BaseCommand):
    help = 'Emails approvers a request to endorse any outstanding change requests.'

    def handle(self, *args, **options):
        # All incomplete changes of status "Submitted for endorsement":
        rfcs = ChangeRequest.objects.filter(status=1, completed__isnull=True)

        for rfc in rfcs:
            msg = 'Request for approval emailed to {}.'.format(rfc.approver.get_full_name())
            rfc.email_approver()
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
