from django.urls import path, include
from restless.dj import DjangoResource
from restless.resources import skip_prepare

from organisation.api import DepartmentUserResource, LocationResource, UserSelectResource, profile
from organisation.models import DepartmentUser, Location, OrgUnit, CostCentre
from registers.api import ITSystemResource
from registers.models import ITSystem


class OptionResource(DjangoResource):
    """Returns serialised lists of object data. Request parameter must include
    ``list`` value of a defined function (below), minus the ``data_`` prefix.
    Example:
    /api/options?list=cost_centre
    """

    @skip_prepare
    def list(self):
        return getattr(self, 'data_' + self.request.GET['list'])()

    def data_cost_centre(self):
        return ['CC{} / {}'.format(*c) for c in CostCentre.objects.filter(active=True).exclude(org_position__name__icontains='inactive').values_list('code', 'org_position__name')]

    def data_org_unit(self):
        return [{'name': i.name, 'id': i.pk, 'division_unit_id': i.division_unit.pk if i.division_unit else ''} for i in OrgUnit.objects.filter(active=True).order_by('name')]

    def data_dept_user(self):
        return [u[0] for u in DepartmentUser.objects.filter(
            active=True, email__iendswith='.wa.gov.au').order_by('email').values_list('email')]

    def data_itsystem(self):
        return ['{} {}'.format(*s) for s in ITSystem.objects.filter(status__in=[0, 2]).values_list('system_id', 'name')]

    def data_statuslogin(self):
        return [l[1] for l in list(ITSystem.STATUS_CHOICES) + list(ITSystem.ACCESS_CHOICES) + list(ITSystem.AUTHENTICATION_CHOICES)]

    def data_location(self):
        return [l.name for l in Location.objects.filter(active=True).order_by('name')]

    def data_division(self):
        return [{'id': i.pk, 'name': i.name} for i in OrgUnit.objects.filter(unit_type=1, active=True).order_by('name')]

    def data_dept(self):
        return [{'acronym': i.acronym, 'name': i.name} for i in OrgUnit.objects.filter(unit_type=0, active=True).order_by('name')]

    def data_department(self):
        return [i.name for i in OrgUnit.objects.filter(unit_type=0, active=True).order_by('name')]

    def data_branch(self):
        return [i.name for i in OrgUnit.objects.filter(unit_type=2, active=True).order_by('name')]

    def data_section(self):
        return [i.name for i in OrgUnit.objects.filter(unit_type=7, active=True).order_by('name')]

    def data_regiondistrict(self):
        return [i.name for i in OrgUnit.objects.filter(unit_type__in=[3, 6], active=True).order_by('name')]

    def data_office(self):
        return [i.name for i in OrgUnit.objects.filter(unit_type=5, active=True).order_by('name')]


api_urlpatterns = [
    path('itsystems/', include(ITSystemResource.urls())),
    path('itsystems.csv', ITSystemResource.as_csv),
    path('locations/', include(LocationResource.urls())),
    path('locations.csv', LocationResource.as_csv),
    path('users/', include(DepartmentUserResource.urls())),
    path('user-select/', include(UserSelectResource.urls())),
    path('profile/', profile, name='api_profile'),
    path('options/', include(OptionResource.urls())),
]
