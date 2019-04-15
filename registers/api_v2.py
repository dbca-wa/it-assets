from django.shortcuts import get_object_or_404
import itertools
from rest_framework import viewsets
from rest_framework.response import Response
from datetime import datetime
from collections import OrderedDict

from .models import ITSystem, ChangeRequest, StandardChange
from .serializers import ChangeRequestSerializer, StandardChangeSerializer


"""Changed the viewset to be readonly,and disable the create,update
 functionality, also made changes from requestor and implementor to
 requester and implementer"""

# class ChangeRequestViewSet(viewsets.ModelViewSet):
class ChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
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
        qs = ChangeRequest.objects.select_related('it_systems').all()
        change = get_object_or_404(qs, pk=pk)
        serializer = ChangeRequestSerializer(change)
        return Response(serializer.data)

    # def create(self, request):
    #     data = {
    #         'requester': request.data.get('requester'),
    #         'endorser': request.data.get('endorser'),
    #         'implementer': request.data.get('implementer'),
    #         'title': request.data.get('title'),
    #         'description': request.data.get('description'),
    #         'change_type': request.data.get('changeType'),
    #         'urgency': request.data.get('urgency'),
    #         #changed submission date to created
    #         'created': datetime.now(),
    #
    #
    #         'alternate_system': request.data.get('altSystem'),
    #         'outage': request.data.get('outage'),
    #         'implementation': request.data.get('implementation'),
    #         'broadcast': request.data.get('broadcast'),
    #         'notes': request.data.get('notes'),
    #         'status': 0,
    #         'unexpected_issues': False,
    #         'caused_issues': False
    #     }
    #     #changed changedStart and changedEnd to planned_start and planned_end
    #     dateStart = request.data.get('changedStart')
    #     if(dateStart):
    #         data['changedStart'] = datetime.strptime(request.data.get('changedStart'), "%d/%m/%Y %H:%M")
    #     dateEnd = request.data.get('changedEnd')
    #     if(dateEnd):
    #         data['changedEnd'] = datetime.strptime(request.data.get('changedEnd'), "%d/%m/%Y %H:%M")
    #     systemCode = request.data.get('itsystems')
    #     if systemCode == 'System not listed':
    #         data['it_systems'] = systemCode
    #     else:
    #         system = ITSystem.objects.get(system_id="systemCode")
    #         data['it_systems'] = system.pk
    #
    #     serializer = ChangeRequestSerializer(data=data, partial=True)
    #     serializer.is_valid(raise_exception=True)
    #     instance = serializer.save()
    #     res = ChangeRequestSerializer(instance)
    #     return Response(res.data)
    #
    # def update(self, request, pk=None):
    #     files = request.FILES.getlist('file')
    #     if files:
    #         try:
    #             change = ChangeRequest.objects.get(pk=pk)
    #         except:
    #             raise "Change Request not found."
    #         for file in files:
    #             f = file.open()
    #             change.implementation_docs.save(file.name, File(f))
    #             serializer = ChangeRequestSerializer(change)
    #             data = serializer.data
    #     else:
    #         try:
    #             change = ChangeRequest.objects.get(pk=pk)
    #         except:
    #             raise "Change Request not found."
    #         if 'status' in request.data and request.data.get('status'):
    #             change.status = request.data.get('status')
    #             if change.status == 1:
    #                 data = {
    #                     'change_request': change.pk,
    #                     'endorser': change.endorser.id,
    #                     'date_approved': datetime.now(),
    #                     'notes': request.data.get('approvalnotes'),
    #                 }
    #                 if int(request.data.get('camefrom')) < 3:
    #                     data['type_of_approval'] = request.data.get('camefrom')
    #                 else:
    #                     data['type_of_approval'] = 2
    #             elif change.status == 2:
    #                 change.completed_date = datetime.now()
    #         else:
    #             change.requester_id = request.data.get('requester')
    #             change.endorser_id = request.data.get('endorser')
    #             change.implementer_id = request.data.get('implementer')
    #             change.title = request.data.get('title')
    #             change.description = request.data.get('description')
    #             change.change_type = request.data.get('changetype')
    #             change.urgency = request.data.get('urgency')
    #             change.alternate_system = request.data.get('altsystem')
    #             change.outage = request.data.get('outage')
    #             change.implementation = request.data.get('implementation')
    #             change.broadcast = request.data.get('broadcast')
    #             change.notes = request.data.get('notes')
    #             change.unexpected_issues = request.data.get('unexpectedissues')
    #             change.caused_issues = request.data.get('causedissues')
    #
    #             dateStart = request.data.get('changestart')
    #             if(dateStart):
    #                 change.change_start = datetime.strptime(request.data.get('changestart'), "%d/%m/%Y %H:%M")
    #             dateEnd = request.data.get('changeend')
    #             if(dateEnd):
    #                 change.change_end = datetime.strptime(request.data.get('changeend'), "%d/%m/%Y %H:%M")
    #             systemCode = request.data.get('itsystem')
    #             if systemCode == 'System not listed':
    #                 change.it_systems = None
    #             else:
    #                 system = ITSystem.objects.get(system_id=systemCode)
    #                 change.it_systems_id = system.pk
    #         change.save()
    #         serializer = ChangeRequestSerializer(change)
    #         data = serializer.data
    #     return Response(data)


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