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
from .models import ITSystem, ChangeRequest, StandardChange
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
