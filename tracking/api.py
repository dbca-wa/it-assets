from django.db.models import F
from restless.resources import skip_prepare
from restless.preparers import Preparer

from itassets.utils import CSVDjangoResource
from .models import EC2Instance, FreshdeskTicket


class EC2InstanceResource(CSVDjangoResource):
    VALUES_ARGS = ('pk', 'name', 'ec2id', 'launch_time', 'running', 'next_state')

    def is_authenticated(self):
        return True

    def list_qs(self):
        if 'ec2id' in self.request.GET:
            return EC2Instance.objects.filter(
                ec2id=self.request.GET['ec2id']).values(*self.VALUES_ARGS)
        else:
            return EC2Instance.objects.exclude(
                running=F('next_state')).values(*self.VALUES_ARGS)

    @skip_prepare
    def list(self):
        data = list(self.list_qs())
        return data

    @skip_prepare
    def create(self):
        if not isinstance(self.data, list):
            self.data = [self.data]
            deleted = None
        else:
            deleted = EC2Instance.objects.exclude(
                ec2id__in=[i['InstanceId'] for i in self.data]).delete()
        for instc in self.data:
            instance, created = EC2Instance.objects.get_or_create(ec2id=instc['InstanceId'])
            instance.name = [x['Value'] for x in instc['Tags'] if x['Key'] == 'Name'][0]
            instance.launch_time = instc['LaunchTime']
            instance.running = instc['State']['Name'] == 'running'
            instance.extra_data = instc
            instance.save()
        return {'saved': len(self.data), 'deleted': deleted}


class FDTicketPreparer(Preparer):
    """Custom FieldsPreparer class for FreskdeskTicketResource.
    """
    def prepare(self, data):
        result = {
            'ticket_id': data.ticket_id,
            'type': data.type,
            'subject': data.subject,
            'description': data.description_text,
            'status': data.get_status_display(),
            'source': data.get_source_display(),
            'priority': data.get_priority_display(),
            'support_category': data.custom_fields['support_category'],
            'support_subcategory': data.custom_fields['support_subcategory'],
            'requester__email': data.freshdesk_requester.email if data.freshdesk_requester else '',
            'created_at': data.created_at.isoformat() if data.created_at else '',
            'updated_at': data.updated_at.isoformat() if data.updated_at else '',
        }
        return result


class FreshdeskTicketResource(CSVDjangoResource):
    """API Resource for the FreshdeskTicket class.
    """

    preparer = FDTicketPreparer()

    def list(self):
        from registers.models import ITSystem
        qs = FreshdeskTicket.objects.all()
        # Filter by type (Incident, Change, etc.)
        if 'type' in self.request.GET:
            qs = qs.filter(type=self.request.GET['type'])
        # Filter by IT System (system ID),
        if 'it_system' in self.request.GET:
            it_system = ITSystem.objects.get(system_id=self.request.GET['it_system'])
            qs = qs.filter(it_system=it_system)
        # Return up to 100 tickets, unless the "all" parameter is included.
        # TODO: count, pagination, etc.
        if 'all' in self.request.GET:
            return qs.order_by('-ticket_id')
        else:
            return qs.order_by('-ticket_id')[0:100]

    def detail(self, pk):
        """Override to consider ticket ID as PK.
        """
        return FreshdeskTicket.objects.get(ticket_id=pk)
