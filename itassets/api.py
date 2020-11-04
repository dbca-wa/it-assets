from django.conf.urls import include, url
from mptt.templatetags.mptt_tags import cache_tree_children
from restless.dj import DjangoResource
from restless.resources import skip_prepare

from assets.api import HardwareAssetResource, HardwareAssetCSV
from organisation.api import DepartmentUserResource, LocationResource, UserSelectResource, profile
from organisation.models import DepartmentUser, Location, OrgUnit, CostCentre
from registers.api import ITSystemResource
from registers.models import ITSystem


def recursive_node_to_dict(node):
    # http://stackoverflow.com/questions/12556268/fastest-way-to-create-json-to-reflect-a-tree-structure-in-python-django-using
    result = {
        'name': node.name, 'id': node.pk,
        'children': [recursive_node_to_dict(c) for c in node._cached_children]
    }
    if not result['children']:
        del result['children']
    return result


class OptionResource(DjangoResource):
    """Returns serialised lists of object data. Request parameter must include
    ``list`` value of a defined function (below), minus the ``data_`` prefix.
    Example:
    /api/options?list=org_structure
    """

    @skip_prepare
    def list(self):
        return getattr(self, 'data_' + self.request.GET['list'])()

    def data_org_structure(self):
        # Return the current org structure, excluding inactive OrgUnits.
        return [recursive_node_to_dict(cache_tree_children(dept.get_descendants_active(include_self=True))[0])
                for dept in OrgUnit.objects.filter(unit_type=0, active=True).order_by('name')]

    def data_cost_centre(self):
        return ['CC{} / {}'.format(*c) for c in CostCentre.objects.filter(active=True).exclude(org_position__name__icontains='inactive').values_list('code', 'org_position__name')]

    def data_org_unit(self):
        if 'parent_id' in self.request.GET and self.request.GET['parent_id']:
            # Filter OrgUnits to those with the specified parent.
            return [{'name': i.name, 'id': i.pk, 'parent_id': i.parent.pk} for i in OrgUnit.objects.filter(active=True, parent__pk=self.request.GET['parent_id']).order_by('name')]
        return [{'name': i.name, 'id': i.pk, 'parent_id': i.parent.pk if i.parent else ''} for i in OrgUnit.objects.filter(active=True).order_by('name')]

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
    url(r'^hardware-assets/csv/', HardwareAssetCSV.as_view()),
    url(r'^hardware-assets/', include(HardwareAssetResource.urls())),
    url(r'^itsystems/', include(ITSystemResource.urls())),
    url(r'^itsystems.csv', ITSystemResource.as_csv),
    url(r'^locations/', include(LocationResource.urls())),
    url(r'^locations.csv', LocationResource.as_csv),
    url(r'^users/', include(DepartmentUserResource.urls())),
    url(r'^user-select/', include(UserSelectResource.urls())),
    url(r'^profile/', profile, name='api_profile'),
    url(r'^options/', include(OptionResource.urls())),
]
