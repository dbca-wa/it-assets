from babel.dates import format_timedelta
from collections import OrderedDict
from datetime import datetime
from django.core.files import File
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
import itertools
from rest_framework import viewsets
from rest_framework.response import Response

from itassets.utils import CSVDjangoResource
from .models import ITSystem, ITSystemHardware, ChangeRequest, StandardChange
from .serializers import ChangeRequestSerializer, StandardChangeSerializer


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
            'authentication': data.get_authentication_display() if data.authentication else '',
            'access': data.get_access_display() if data.access else '',
            'cost_centre__division__manager__name': cost_centre__division__manager__name,
            'cost_centre__division__manager__email': cost_centre__division__manager__email,
            'cost_centre__division__manager__title': cost_centre__division__manager__title,
            'cost_centre__division__name': cost_centre__division__name,
            'cost_centre__name': cost_centre__name,
            'cost_centre__code': cost_centre__code,
            'owner__name': data.owner.name if data.owner else '',
            'owner__email': data.owner.email if data.owner else '',
            'owner__title': data.owner.title if data.owner else '',
            'technology_custodian__name': data.technology_custodian.name if data.technology_custodian else '',
            'technology_custodian__email': data.technology_custodian.email if data.technology_custodian else '',
            'technology_custodian__title': data.technology_custodian.title if data.technology_custodian else '',
            'information_custodian__name': data.information_custodian.name if data.information_custodian else '',
            'information_custodian__email': data.information_custodian.email if data.information_custodian else '',
            'information_custodian__title': data.information_custodian.title if data.information_custodian else '',
            'link': data.link,
            'status_url': data.status_url or '',
            'system_reqs': data.system_reqs,
            'system_type': data.get_system_type_display() if data.system_type else '',
            'bh_support': {
                'name': data.bh_support.name,
                'email': data.bh_support.email,
                'telephone': data.bh_support.telephone} if data.bh_support else {},
            'ah_support': {
                'name': data.ah_support.name,
                'email': data.ah_support.email,
                'telephone': data.ah_support.telephone} if data.ah_support else {},
            'availability': data.get_availability_display() if data.availability else '',
            'status': data.get_status_display() if data.status else '',
            'hardwares': [{
                'computer': i.computer.hostname,
                'role': i.get_role_display(),
                'computer__location': i.computer.location.name if i.computer.location else '',
                'operating_system': i.computer.os_name if i.computer.os_name else '',
                'description': i.description,
                'patch_group': i.patch_group
            } for i in data.hardwares.filter(decommissioned=False)],
            'dependencies': [{
                'dependency__system_id': i.dependency.system_id,
                'dependency__name': i.dependency.name,
                'criticality': i.get_criticality_display(),
                'technology_custodian__name': i.dependency.technology_custodian.name if i.dependency.technology_custodian else '',
                'technology_custodian__email': i.dependency.technology_custodian.email if i.dependency.technology_custodian else '',
            } for i in data.itsystemdependency_set.all()],
            'dependants': [{
                'dependant__system_id': i.itsystem.system_id,
                'dependant__name': i.itsystem.name,
                'criticality': i.get_criticality_display(),
                'technology_custodian__name': i.itsystem.technology_custodian.name if i.itsystem.technology_custodian else '',
                'technology_custodian__email': i.itsystem.technology_custodian.email if i.itsystem.technology_custodian else '',
            } for i in data.dependency.all()],
            'usergroups': [{'name': i.name, 'count': i.user_count} for i in data.user_groups.all()],
            'backups': data.get_backups_display() if data.backups else '',
            'seasonality': data.get_seasonality_display() if data.seasonality else '',
            'user_notification': data.user_notification,
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
            'technology_custodian', 'information_custodian', 'bh_support', 'ah_support', 'user_groups',
            'itsystemdependency_set', 'itsystemdependency_set__dependency',
            'itsystemdependency_set__dependency__technology_custodian', 'dependency__itsystem',
            'dependency__itsystem__technology_custodian'
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


class ChangeRequestViewSet(viewsets.ModelViewSet):
    """Used to allow users to create change requests. These can be viewed
    updated or created.
    """
    permission_classes = []
    queryset = ChangeRequest.objects.all()
    serializer_class = ChangeRequestSerializer

    def list(self, request):
        #changed submission_date to created
        qa = ChangeRequest.objects.all().order_by('-created')


        search = request.GET.get('search[value]') if request.GET.get('search[value]') else None
        start = request.GET.get('start') if request.GET.get('start') else 0
        length = request.GET.get('length') if request.GET.get('length') else len(qa)
        datefrom = datetime.strptime(request.GET.get('filterfrom'), '%d/%m/%Y').date() if request.GET.get('filterfrom') else None
        dateto = datetime.strptime(request.GET.get('filterto'), '%d/%m/%Y').date() if request.GET.get('filterto') else None
        urgency = request.GET.get('urgency') if request.GET.get('urgency') else None
        status = request.GET.get('status') if request.GET.get('status') else None
        mychanges = request.GET.get('mychanges') if request.GET.get('mychanges') else None
        recordsTotal = len(qa)
        if(mychanges):
            if(request.user.is_authenticated):
                user = request.user.email
                qa = qa.filter(Q(requester__email=user) | Q(endorser__email=user) | Q(implementer__email=user))
        if(search):
            qa = qa.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(notes__icontains=search) | Q(broadcast__icontains=search) | Q(implementation__icontains=search) | Q(it_system__name__icontains=search) | Q(implementer__name__icontains=search) | Q(endorser__name__icontains=search) | Q(requester__name__icontains=search))
        if(datefrom):
            qa = qa.filter(change_start__gte=datefrom)
        if(dateto):
            qa = qa.filter(change_start__lte=dateto)
        if(urgency):
            if(int(urgency) != 99):
                qa = qa.filter(urgency=urgency)
        if(status):
            if(int(status) != 99):
                qa = qa.filter(status=status)

        recordsFiltered = int(len(qa))
        qa = qa[int(start):int(length) + int(start)]
        serializer = self.serializer_class(qa, many=True)
        return Response(OrderedDict([
            ('recordsTotal', recordsTotal),
            ('recordsFiltered', recordsFiltered),
            ('results', serializer.data)
        ]))

    def retrieve(self, request, pk=None):
        qs = ChangeRequest.objects.select_related('it_system').all()
        change = get_object_or_404(qs, pk=pk)
        serializer = ChangeRequestSerializer(change)
        return Response(serializer.data)

    def create(self, request):
        data = {
            'requester': request.data.get('requester'),
            'endorser': request.data.get('endorser'),
            'implementer': request.data.get('implementer'),
            'title': request.data.get('title'),
            'description': request.data.get('description'),
            'change_type': request.data.get('changeType'),
            'urgency': request.data.get('urgency'),
            #changed submission date to created
            'created': datetime.now(),


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
            data['change_start'] = datetime.strptime(request.data.get('changeStart'), "%d/%m/%Y %H:%M")
        dateEnd = request.data.get('changeEnd')
        if(dateEnd):
            data['change_end'] = datetime.strptime(request.data.get('changeEnd'), "%d/%m/%Y %H:%M")
        systemCode = request.data.get('itSystem')
        if systemCode == 'System not listed':
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
                        'endorser': change.endorser.id,
                        'date_approved': datetime.now(),
                        'notes': request.data.get('approvalnotes'),
                    }
                    if int(request.data.get('camefrom')) < 3:
                        data['type_of_approval'] = request.data.get('camefrom')
                    else:
                        data['type_of_approval'] = 2
                elif change.status == 2:
                    change.completed_date = datetime.now()
            else:
                change.requester_id = request.data.get('requester')
                change.endorser_id = request.data.get('endorser')
                change.implementer_id = request.data.get('implementer')
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
                if systemCode == 'System not listed':
                    change.it_systems = None
                else:
                    system = ITSystem.objects.get(system_id=systemCode)
                    change.it_systems_id = system.pk
            change.save()
            serializer = ChangeRequestSerializer(change)
            data = serializer.data
        return Response(data)


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
