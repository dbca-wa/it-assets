from babel.dates import format_timedelta
from django.conf import settings
from django.conf.urls import url
from django.shortcuts import get_object_or_404
import itertools
import pytz
from datetime import datetime, timedelta
from restless.dj import DjangoResource
from restless.preparers import FieldsPreparer
from restless.resources import skip_prepare
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from django.core.files import File
from django.db.models import Q
from collections import OrderedDict

from itassets.utils import CSVDjangoResource
from organisation.models import DepartmentUser
from .models import ITSystem, ITSystemHardware, ITSystemEvent, ChangeRequest, StandardChange, ChangeApproval
from .serializers import ChangeRequestSerializer, StandardChangeSerializer, ChangeApprovalSerializer


class ITSystemResource(CSVDjangoResource):
    VALUES_ARGS = ()

    def prepare(self, data):
        """Prepare a custom API response for ITSystemResource objects.
        """
        # Owner > CC > Division > Manager
        cost_centre__division__manager__name = ''
        cost_centre__division__manager__email = ''
        cost_centre__division__manager__title = ''
        cost_centre__division__name = ''
        cost_centre__name = ''
        cost_centre__code = ''
        # Every damn field is nullable!
        if data.cost_centre:  # Use this field first.
            cost_centre__name = data.cost_centre.name
            cost_centre__code = data.cost_centre.code
            if data.cost_centre.division:
                cost_centre__division__name = data.cost_centre.division.name
                if data.cost_centre.division.manager:
                    cost_centre__division__manager__name = data.cost_centre.division.manager.name
                    cost_centre__division__manager__email = data.cost_centre.division.manager.email
                    cost_centre__division__manager__title = data.cost_centre.division.manager.title
        elif data.owner:  # Use this second.
            if data.owner.cost_centre:
                cost_centre__name = data.owner.cost_centre.name
                cost_centre__code = data.owner.cost_centre.code
                if data.owner.cost_centre.division:
                    cost_centre__division__name = data.owner.cost_centre.division.name
                    if data.owner.cost_centre.division.manager:
                        cost_centre__division__manager__name = data.owner.cost_centre.division.manager.name
                        cost_centre__division__manager__email = data.owner.cost_centre.division.manager.email
                        cost_centre__division__manager__title = data.owner.cost_centre.division.manager.title

        domain = self.request.build_absolute_uri().replace(self.request.get_full_path(), '')
        prepped = {
            'pk': data.pk,
            'name': data.name,
            'acronym': data.acronym,
            'system_id': data.system_id,
            'description': data.description,
            'documentation': data.documentation,
            'technical_documentation': data.technical_documentation,
            'authentication_display': data.authentication_display or '',
            'access_display': data.access_display or '',
            'preferred_contact__name': data.preferred_contact.name if data.preferred_contact else '',
            'preferred_contact__email': data.preferred_contact.email if data.preferred_contact else '',
            'preferred_contact__title': data.preferred_contact.title if data.preferred_contact else '',
            'cost_centre__division__manager__name': cost_centre__division__manager__name,
            'cost_centre__division__manager__email': cost_centre__division__manager__email,
            'cost_centre__division__manager__title': cost_centre__division__manager__title,
            'cost_centre__division__name': cost_centre__division__name,
            'cost_centre__name': cost_centre__name,
            'cost_centre__code': cost_centre__code,
            'owner__name': data.owner.name if data.owner else '',
            'owner__email': data.owner.email if data.owner else '',
            'owner__title': data.owner.title if data.owner else '',
            'custodian__name': data.custodian.name if data.custodian else '',
            'custodian__email': data.custodian.email if data.custodian else '',
            'custodian__title': data.custodian.title if data.custodian else '',
            'data_custodian__name': data.data_custodian.name if data.data_custodian else '',
            'data_custodian__email': data.data_custodian.email if data.data_custodian else '',
            'data_custodian__title': data.data_custodian.title if data.data_custodian else '',
            'link': data.link,
            'status_html': data.status_html or '',
            'schema': data.schema_url or '',
            'system_reqs': data.system_reqs,
            'system_type': data.system_type_display or '',
            'vulnerability_docs': data.vulnerability_docs,
            'workaround': data.workaround,
            'recovery_docs': data.recovery_docs,
            'bh_support': {
                'name': data.bh_support.name,
                'email': data.bh_support.email,
                'telephone': data.bh_support.telephone} if data.bh_support else {},
            'ah_support': {
                'name': data.ah_support.name,
                'email': data.ah_support.email,
                'telephone': data.ah_support.telephone} if data.ah_support else {},
            'availability': data.availability_display or '',
            'status_display': data.status_display or '',
            'criticality': data.criticality_display or '',
            'mtd': format_timedelta(data.mtd),
            'rto': format_timedelta(data.rto),
            'rpo': format_timedelta(data.rpo),
            'hardwares': [{
                'computer': i.computer.hostname,
                'role': i.get_role_display(),
                'computer__location': i.computer.location.name if i.computer.location else '',
                'operating_system': i.computer.os_name if i.computer.os_name else '',
                'description': i.description,
                'patch_group': i.patch_group
            } for i in data.hardwares.filter(decommissioned=False)],
            'processes': [{
                'process__name': i.process.name,
                'process__criticality': i.process.get_criticality_display() if i.process.criticality else '',
                'process__importance': i.get_importance_display(),
                # Flatten the function(s) associated with the process.
                'function__name': ', '.join(f.name for f in i.process.functions.all()),
                # One nest listed comprehension to rule them all.
                'function__service': ', '.join(sorted(set(
                    [str(s.number) for s in list(
                        itertools.chain.from_iterable(
                            [f.services.all() for f in i.process.functions.all()]
                        )
                    )]
                )))
            } for i in data.processitsystemrelationship_set.all().order_by('importance')],
            'dependencies': [{
                'dependency__system_id': i.dependency.system_id,
                'dependency__name': i.dependency.name,
                'criticality': i.get_criticality_display(),
                'custodian__name': i.dependency.custodian.name if i.dependency.custodian else '',
                'custodian__email': i.dependency.custodian.email if i.dependency.custodian else '',
            } for i in data.itsystemdependency_set.all()],
            'dependants': [{
                'dependant__system_id': i.itsystem.system_id,
                'dependant__name': i.itsystem.name,
                'criticality': i.get_criticality_display(),
                'custodian__name': i.itsystem.custodian.name if i.itsystem.custodian else '',
                'custodian__email': i.itsystem.custodian.email if i.itsystem.custodian else '',
            } for i in data.dependency.all()],
            'usergroups': [{'name': i.name, 'count': i.user_count} for i in data.user_groups.all()],
            'contingency_plan_url': domain + settings.MEDIA_URL + data.contingency_plan.name if data.contingency_plan else '',
            'contingency_plan_status': data.get_contingency_plan_status_display(),
            'contingency_plan_last_tested': data.contingency_plan_last_tested,
            'notes': data.notes,
            'backup_info': data.backup_info,
            'system_health': data.get_system_health_display(),
            'system_health_rag': data.system_health,
            'system_creation_date': data.system_creation_date,
            # I love list comprehensions 4 eva
            'risks': [next(i for i in data.RISK_CHOICES if i[0] == risk[0])[1] for risk in data.risks],
            'change_history': [],
            'related_incidents': [],
            'related_projects': [],
            'critical_period': data.critical_period,
            'alt_processing': data.alt_processing,
            'technical_recov': data.technical_recov,
            'post_recovery': data.post_recovery,
            'variation_iscp': data.variation_iscp,
            'user_notification': data.user_notification,
            'function': [next(i for i in data.FUNCTION_CHOICES if i[0] == f[0])[1] for f in data.function],
            'use': [next(i for i in data.USE_CHOICES if i[0] == u[0])[1] for u in data.use],
            'capability': [next(i for i in data.CAPABILITY_CHOICES if i[0] == c[0])[1] for c in data.capability],
            'unique_evidence': 'Unknown' if data.unique_evidence is None else data.unique_evidence,
            'point_of_truth': 'Unknown' if data.point_of_truth is None else data.point_of_truth,
            'legal_need_to_retain': 'Unknown' if data.legal_need_to_retain is None else data.legal_need_to_retain,
            'other_projects': data.other_projects,
            'sla': data.sla,
            'biller_code': data.biller_code,
            'platforms': [{'name': i.name, 'category': i.get_category_display()} for i in data.platforms.all()],
            'oim_internal': data.oim_internal_only,
        }
        return prepped

    def list_qs(self):
        # Only return production/production legacy apps by default.
        FILTERS = {"status__in": [0, 2]}
        if "all" in self.request.GET:
            FILTERS.pop("status__in")
        if "system_id" in self.request.GET:
            FILTERS.pop("status__in")
            FILTERS["system_id__icontains"] = self.request.GET["system_id"]
        if "name" in self.request.GET:
            FILTERS.pop("status__in")
            FILTERS["name"] = self.request.GET["name"]
        if "pk" in self.request.GET:
            FILTERS.pop("status__in")
            FILTERS["pk"] = self.request.GET["pk"]
        return ITSystem.objects.filter(**FILTERS).prefetch_related(
            'cost_centre', 'cost_centre__division', 'org_unit',
            'owner', 'owner__cost_centre', 'owner__cost_centre__division',
            'preferred_contact',
            'custodian', 'data_custodian', 'bh_support', 'ah_support', 'user_groups',
            'itsystemdependency_set', 'itsystemdependency_set__dependency',
            'itsystemdependency_set__dependency__custodian', 'dependency__itsystem',
            'dependency__itsystem__custodian'
        )

    def list(self):
        return list(self.list_qs())


class ITSystemHardwareResource(CSVDjangoResource):
    VALUES_ARGS = ()

    def prepare(self, data):
        # Exclude decommissioned systems from the list of systems returned.
        it_systems = data.itsystem_set.all().exclude(status=3)
        return {
            'hostname': data.computer.hostname,
            'role': data.get_role_display(),
            'it_systems': [i.name for i in it_systems],
        }

    def list(self):
        return ITSystemHardware.objects.all()


class ITSystemEventResource(DjangoResource):
    def __init__(self, *args, **kwargs):
        super(ITSystemEventResource, self).__init__(*args, **kwargs)
        self.http_methods.update({
            'current': {'GET': 'current'}
        })

    preparer = FieldsPreparer(fields={
        'id': 'id',
        'description': 'description',
        'planned': 'planned',
        'current': 'current',
    })

    def prepare(self, data):
        prepped = super(ITSystemEventResource, self).prepare(data)
        prepped['event_type'] = data.get_event_type_display()
        # Output times as the local timezone.
        tz = pytz.timezone(settings.TIME_ZONE)
        prepped['start'] = data.start.astimezone(tz)
        if data.end:
            prepped['end'] = data.end.astimezone(tz)
        else:
            prepped['end'] = None
        if data.duration:
            prepped['duration_sec'] = data.duration.seconds
        else:
            prepped['duration_sec'] = None
        if data.it_systems:
            prepped['it_systems'] = [i.name for i in data.it_systems.all()]
        else:
            prepped['it_systems'] = None
        if data.locations:
            prepped['locations'] = [i.name for i in data.locations.all()]
        else:
            prepped['locations'] = None
        return prepped

    @skip_prepare
    def current(self):
        # Slightly-expensive query: iterate over each 'current' event and call save().
        # This should automatically expire any events that need to be non-current.
        for i in ITSystemEvent.objects.filter(current=True):
            i.save()
        # Return prepared data.
        return {'objects': [self.prepare(data) for data in ITSystemEvent.objects.filter(current=True)]}

    def list(self):
        return ITSystemEvent.objects.all()

    def detail(self, pk):
        return ITSystemEvent.objects.get(pk=pk)

    @classmethod
    def urls(self, name_prefix=None):
        urlpatterns = super(ITSystemEventResource, self).urls(name_prefix=name_prefix)
        return [
            url(r'^current/$', self.as_view('current'), name=self.build_url_name('current', name_prefix)),
        ] + urlpatterns

class ChangeRequestViewSet(viewsets.ModelViewSet):
    """Used to allow users to create change requests. These can be viewed
    updated or created.
    """
    permission_classes = []
    queryset = ChangeRequest.objects.all()
    serializer_class = ChangeRequestSerializer

    def list(self, request):
        qa = ChangeRequest.objects.all().order_by('-submission_date')
        search = request.GET.get('search[value]') if request.GET.get('search[value]') else None
        start = request.GET.get('start') if request.GET.get('start') else 0
        length = request.GET.get('length') if request.GET.get('length') else len(qa)
        datefrom = datetime.strptime(request.GET.get('filterfrom'),'%d/%m/%Y').date() if request.GET.get('filterfrom') else None
        dateto = datetime.strptime(request.GET.get('filterto'),'%d/%m/%Y').date() if request.GET.get('filterto') else None
        urgency = request.GET.get('urgency') if request.GET.get('urgency') else None
        status = request.GET.get('status') if request.GET.get('status') else None
        mychanges = request.GET.get('mychanges') if request.GET.get('mychanges') else None
        recordsTotal = len(qa)
        if(mychanges):
            if(request.user.is_authenticated):
                user = request.user.email
                qa = qa.filter(Q(requestor__email=user) | Q(approver__email=user) | Q(implementor__email=user))
        if(search):
            qa = qa.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(notes__icontains=search) | Q(broadcast__icontains=search) | Q(implementation__icontains=search) | Q(it_system__name__icontains=search) | Q(implementor__name__icontains=search) | Q(approver__name__icontains=search) | Q(requestor__name__icontains=search))
        if(datefrom):
            qa = qa.filter(change_start__gte=datefrom)
        if(dateto):
            qa = qa.filter(change_start__lte=dateto)
        if(urgency):
            if(int(urgency)!=99):
                qa = qa.filter(urgency=urgency)
        if(status):
            if(int(status)!=99):
                qa = qa.filter(status=status)

        recordsFiltered = int(len(qa))
        qa = qa[int(start):int(length)+int(start)]
        serializer = self.serializer_class(qa, many=True)
        return Response(OrderedDict([
                ('recordsTotal', recordsTotal),
                ('recordsFiltered',recordsFiltered),
                ('results',serializer.data)
            ]))

    def retrieve(self, request, pk=None):
        qs = ChangeRequest.objects.select_related('it_system').all()
        change = get_object_or_404(qs, pk=pk)
        serializer = ChangeRequestSerializer(change)
        return Response(serializer.data)
    
    def create(self, request):
        data = {
            'requestor': request.data.get('requestor'),
            'approver': request.data.get('approver'),
            'implementor': request.data.get('implementor'),
            'title': request.data.get('title'),
            'description': request.data.get('description'),
            'change_type': request.data.get('changeType'),
            'urgency': request.data.get('urgency'),
            'submission_date': datetime.now(),
            'alternate_system': request.data.get('altSystem'),
            'outage': request.data.get('outage'),
            'implementation': request.data.get('implementation'),
            'broadcast': request.data.get('broadcast'),
            'notes': request.data.get('notes'),
            'status': 0,
            'unexpected_issues': False,
            'caused_issues': False
        }
        dateStart = request.data.get('changeStart')
        if(dateStart):
            data['change_start']= datetime.strptime(request.data.get('changeStart'), "%d/%m/%Y %H:%M")
        dateEnd = request.data.get('changeEnd')
        if(dateEnd):
            data['change_end']= datetime.strptime(request.data.get('changeEnd'), "%d/%m/%Y %H:%M")
        systemCode = request.data.get('itSystem')
        if systemCode=='System not listed':
            data['it_system'] = systemCode
        else:
            system = ITSystem.objects.get(system_id=systemCode)
            data['it_system'] = system.pk
        
        serializer = ChangeRequestSerializer(data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        res = ChangeRequestSerializer(instance)
        return Response(res.data)

    def update(self, request, pk=None):
        files = request.FILES.getlist('file')
        if files:
            try:
                change = ChangeRequest.objects.get(pk=pk)
            except:
                raise "Change Request not found."
            for file in files:
                f = file.open()
                change.implementation_docs.save(file.name, File(f))
                serializer = ChangeRequestSerializer(change)
                data = serializer.data
        else:
            try:
                change = ChangeRequest.objects.get(pk=pk)
            except:
                raise "Change Request not found."
            if 'status' in request.data and request.data.get('status'):
                change.status = request.data.get('status')
                if change.status == 1:
                    data = {
                        'change_request': change.pk,
                        'approver': change.approver.id,
                        'date_approved': datetime.now(),
                        'notes': request.data.get('approvalnotes'),
                    }
                    if int(request.data.get('camefrom')) < 3:
                        data['type_of_approval'] = request.data.get('camefrom')
                    else:
                        data['type_of_approval'] = 2
                    serial = ChangeApprovalSerializer(data=data, partial=True)
                    serial.is_valid(raise_exception=True)
                    instance = serial.save()
                    re = ChangeApprovalSerializer(instance)
                elif change.status == 2:
                    change.completed_date = datetime.now()
            else:
                change.requestor_id = request.data.get('requestor')
                change.approver_id = request.data.get('approver')
                change.implementor_id = request.data.get('implementor')
                change.title = request.data.get('title')
                change.description = request.data.get('description')
                change.change_type = request.data.get('changetype')
                change.urgency = request.data.get('urgency')
                change.alternate_system = request.data.get('altsystem')
                change.outage = request.data.get('outage')
                change.implementation = request.data.get('implementation')
                change.broadcast = request.data.get('broadcast')
                change.notes = request.data.get('notes')
                change.unexpected_issues = request.data.get('unexpectedissues')
                change.caused_issues = request.data.get('causedissues')

                dateStart = request.data.get('changestart')
                if(dateStart):
                    change.change_start = datetime.strptime(request.data.get('changestart'), "%d/%m/%Y %H:%M")
                dateEnd = request.data.get('changeend')
                if(dateEnd):
                    change.change_end = datetime.strptime(request.data.get('changeend'), "%d/%m/%Y %H:%M")
                systemCode = request.data.get('itsystem')
                if systemCode=='System not listed':
                    change.it_system = None
                else:
                    system = ITSystem.objects.get(system_id=systemCode)
                    change.it_system_id = system.pk
            change.save()
            serializer = ChangeRequestSerializer(change)
            data = serializer.data
        return Response(data)

    @detail_route()
    def approval_list(self, request, pk=None):
        change = self.get_object()
        approvals = ChangeApproval.objects.filter(change_request=change).order_by('-date_approved')
        serializer = ChangeApprovalSerializer(approvals, many=True)
        return Response(serializer.data)


class StandardChangeViewSet(viewsets.ViewSet):
    """Used to get standard changes
    """
    permission_classes = []
    queryset = StandardChange.objects.all()
    serializer_class = StandardChangeSerializer

    def list(self, request):
        qs = self.queryset
        serializer = self.serializer_class(qs, many=True)
        return Response(serializer.data)

