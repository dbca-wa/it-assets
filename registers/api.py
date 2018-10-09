from babel.dates import format_timedelta
from django.conf import settings
import itertools

from itassets.utils import CSVDjangoResource
from .models import ITSystem, ITSystemHardware


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
