from django.core.management.base import BaseCommand
from registers.models import ChangeRequest, ChangeLog


class Command(BaseCommand):
    help = 'Emails endorsers a request to endorse any outstanding change requests.'

    def handle(self, *args, **options):
        # All incomplete changes of status "Submitted for endorsement":
        rfcs = ChangeRequest.objects.filter(status=1, completed__isnull=True)

        for rfc in rfcs:
            if rfc.endorser:
                msg = 'Request for endorsement emailed to {}.'.format(rfc.endorser.name)
                rfc.email_endorser()
                log = ChangeLog(change_request=rfc, log=msg)
                log.save()
