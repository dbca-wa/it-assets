from dateutil.parser import parse
from django.conf import settings
from django.urls import path, re_path
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
import json
import logging
import pytz
from restless.constants import OK
from restless.dj import DjangoResource
from restless.exceptions import BadRequest
from restless.preparers import FieldsPreparer
from restless.resources import skip_prepare
from restless.utils import MoreTypesJSONEncoder

from itassets.utils import FieldsFormatter, CSVDjangoResource
from .models import DepartmentUser, Location, OrgUnit, CostCentre


ACCOUNT_TYPE_DICT = dict(DepartmentUser.ACCOUNT_TYPE_CHOICES)
LOGGER = logging.getLogger('sync_tasks')
TIMEZONE = pytz.timezone(settings.TIME_ZONE)


def format_fileField(request, value):
    if value:
        return request.build_absolute_uri('{}{}'.format(settings.MEDIA_URL, value))
    else:
        return value


def format_position_type(request, value):
    position_type = dict(DepartmentUser.POSITION_TYPE_CHOICES)
    if value is not None:
        return position_type[value]
    else:
        return value


def format_account_type(request, value):
    if value is not None:
        return ACCOUNT_TYPE_DICT[value]
    else:
        return value


def format_location(request, value):
    if value is not None:
        location = Location.objects.get(pk=value)
        return location.as_dict()
    else:
        return None


class DepartmentUserResource(DjangoResource):
    """An API Resource class to represent DepartmentUser objects.
    This class is used to create & update synchronised user account data from
    Active Directory.
    It also includes custom endpoints to return the P&W organisation
    structure membership.
    """
    COMPACT_ARGS = (
        'pk', 'name', 'title', 'email', 'telephone',
        'mobile_phone', 'extension', 'org_data', 'parent__email',
        'parent__name', 'username', 'org_unit__location__id',
        'org_unit__location__name', 'org_unit__location__address',
        'org_unit__location__pobox', 'org_unit__location__phone',
        'org_unit__location__fax', 'ad_guid', 'employee_id',
        'location', 'preferred_name', 'expiry_date', 'o365_licence')
    VALUES_ARGS = COMPACT_ARGS + (
        'ad_data', 'date_updated', 'active',
        'given_name', 'surname', 'home_phone',
        'other_phone', 'notes', 'working_hours', 'position_type',
        'account_type', 'shared_account')
    MINIMAL_ARGS = (
        'pk', 'name', 'preferred_name', 'title', 'email', 'telephone', 'mobile_phone')
    PROPERTY_ARGS = ('password_age_days',)

    formatters = FieldsFormatter(formatters={
        'position_type': format_position_type,
        'account_type': format_account_type,
        'location': format_location,
    })

    def __init__(self, *args, **kwargs):
        super(DepartmentUserResource, self).__init__(*args, **kwargs)
        self.http_methods.update({
            'list_fast': {'GET': 'list_fast'}
        })

    def prepare(self, data):
        """Modify the returned object to append the GAL Department value.
        """
        prepped = super(DepartmentUserResource, self).prepare(data)

        if 'pk' in data:
            prepped['gal_department'] = DepartmentUser.objects.get(pk=data['pk']).get_gal_department()
        if 'date_updated' in data and data['date_updated']:
            prepped['date_updated'] = data['date_updated'].astimezone(TIMEZONE)
        if 'expiry_date' in data and data['expiry_date']:
            prepped['expiry_date'] = data['expiry_date'].astimezone(TIMEZONE)
            if data['expiry_date'] < timezone.now():
                data['ad_expired'] = True
            else:
                data['ad_expired'] = False
        return prepped

    @classmethod
    def urls(self, name_prefix=None):
        """Override the DjangoResource ``urls`` class method so the detail view
        accepts a GUID parameter instead of PK.
        """
        return [
            path('', self.as_list(), name=self.build_url_name('list', name_prefix)),
            path('fast/', self.as_view('list_fast'), name=self.build_url_name('list_fast', name_prefix)),
            re_path(r'^(?P<guid>[0-9A-Za-z-_@\'&\.]+)/$', self.as_detail(), name=self.build_url_name('detail', name_prefix)),
        ]

    def build_response(self, data, status=OK):
        resp = super(DepartmentUserResource, self).build_response(data, status)
        # Require a short caching expiry for certain request types (if defined).
        if settings.API_RESPONSE_CACHE_SECONDS:
            if any(k in self.request.GET for k in ['email', 'compact', 'minimal']):
                resp['Cache-Control'] = 'max-age={}, public'.format(settings.API_RESPONSE_CACHE_SECONDS)
        return resp

    def is_authenticated(self):
        """This method is currently required for create/update to work via the
        AD sync scripts.
        TODO: implement optional token-based auth to secure this.
        """
        return True

    # Hack: duplicate list() method, decorated with skip_prepare in order to improve performance.
    @skip_prepare
    def list_fast(self):
        resp = cache.get(self.request.get_full_path())
        if resp:
            return resp
        FILTERS = {}
        # DepartmentUser object response.
        # Some of the request parameters below are mutually exclusive.
        if 'all' in self.request.GET:
            # Return all objects, including those deleted in AD.
            users = DepartmentUser.objects.all()
        elif 'email' in self.request.GET:
            # Always return an object by email.
            users = DepartmentUser.objects.filter(email__iexact=self.request.GET['email'])
        elif 'ad_guid' in self.request.GET:
            # Always return an object by UUID.
            users = DepartmentUser.objects.filter(ad_guid=self.request.GET['ad_guid'])
        elif 'cost_centre' in self.request.GET:
            # Always return all objects by cost centre (inc inactive & contractors).
            users = DepartmentUser.objects.filter(cost_centre__code__icontains=self.request.GET['cost_centre'])
        elif 'pk' in self.request.GET:
            # Return the sole user requested.
            users = DepartmentUser.objects.filter(pk=self.request.GET['pk'])
        else:
            # No other filtering:
            # Return 'active' DU objects, excluding predefined account types and contractors
            # and expired accounts.
            FILTERS = DepartmentUser.ACTIVE_FILTER.copy()
            users = DepartmentUser.objects.filter(**FILTERS)
            users = users.exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
            users = users.exclude(expiry_date__lte=timezone.now())
        # Parameters to modify the API output.
        if 'minimal' in self.request.GET:
            # For the minimal response, we don't need a prefetch_related.
            self.VALUES_ARGS = self.MINIMAL_ARGS
        else:
            if 'compact' in self.request.GET:
                self.VALUES_ARGS = self.COMPACT_ARGS
            users = users.prefetch_related('org_unit', 'org_unit__location', 'parent')

        user_values = list(users.order_by('name').values(*self.VALUES_ARGS))
        resp = self.formatters.format(self.request, user_values)
        resp = {'objects': resp}
        # Cache the response for 300 seconds.
        cache.set(self.request.get_full_path(), resp, timeout=300)
        return resp

    # NOTE: skip_prepare provides a huge performance improvement to this method, but at present we
    # cannot use it because we need to modify the serialised object.
    # @skip_prepare
    def list(self):
        """Pass query params to modify the API output.
        Include `org_structure=true` and `sync_o365=true` to output only
        OrgUnits with sync_o365 == True.
        """
        FILTERS = {}
        sync_o365 = True
        if 'sync_o365' in self.request.GET and self.request.GET['sync_o365'] == 'false':
            sync_o365 = False
        else:
            sync_o365 = True
        # org_structure response.
        if 'org_structure' in self.request.GET:
            resp = self.org_structure(sync_o365=sync_o365)
            cache.set(self.request.get_full_path(), resp, timeout=300)
            return resp
        # DepartmentUser object response.
        # Some of the request parameters below are mutually exclusive.
        if 'all' in self.request.GET:
            # Return all objects, including those deleted in AD.
            users = DepartmentUser.objects.all()
        elif 'email' in self.request.GET:
            # Always return an object by email.
            users = DepartmentUser.objects.filter(email__iexact=self.request.GET['email'])
        elif 'ad_guid' in self.request.GET:
            # Always return an object by UUID.
            users = DepartmentUser.objects.filter(ad_guid=self.request.GET['ad_guid'])
        elif 'cost_centre' in self.request.GET:
            # Always return all objects by cost centre (inc inactive & contractors).
            users = DepartmentUser.objects.filter(cost_centre__code__icontains=self.request.GET['cost_centre'])
        else:
            # No other filtering:
            # Return 'active' DU objects, excluding predefined account types and contractors
            # and expired accounts.
            FILTERS = DepartmentUser.ACTIVE_FILTER.copy()
            users = DepartmentUser.objects.filter(**FILTERS)
            users = users.exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
            users = users.exclude(expiry_date__lte=timezone.now())
        # Non-mutually-exclusive filters:
        if 'o365_licence' in self.request.GET:
            if self.request.GET['o365_licence'].lower() == 'true':
                users = users.filter(o365_licence=True)
            elif self.request.GET['o365_licence'].lower() == 'false':
                users = users.filter(o365_licence=False)

        # Parameters to modify the API output.
        if 'minimal' in self.request.GET:
            # For the minimal response, we don't need a prefetch_related.
            self.VALUES_ARGS = self.MINIMAL_ARGS
        else:
            if 'compact' in self.request.GET:
                self.VALUES_ARGS = self.COMPACT_ARGS
            users = users.prefetch_related('org_unit', 'org_unit__location', 'parent')

        user_values = list(users.order_by('name').values(*self.VALUES_ARGS))
        resp = self.formatters.format(self.request, user_values)
        return resp

    def detail(self, guid):
        """Detail view for a single DepartmentUser object.
        """
        resp = cache.get(self.request.get_full_path())
        if resp:
            return resp
        user = DepartmentUser.objects.filter(ad_guid=guid)
        if not user:
            user = DepartmentUser.objects.filter(email__iexact=guid.lower())
        user_values = list(user.values(*self.VALUES_ARGS))
        resp = self.formatters.format(self.request, user_values)[0]
        cache.set(self.request.get_full_path(), resp, timeout=300)
        return resp

    @skip_prepare
    def create(self):
        """Call this endpoint from on-prem AD or from Azure AD.
        Match either AD-object key values or Departmentuser field names.
        """
        # Short-circuit: check if the POST request has been made with `azure_guid` as a param.
        # If so, check if that value matches an existing object and use it instead of
        # creating a new object. All the "new" object values should be passed in and updated
        # anyway.
        # Rationale: we seem to have trouble getting the sync script to check for existing
        # objects by Azure AD GUID.
        if 'azure_guid' in self.data:
            if DepartmentUser.objects.filter(azure_guid=self.data['azure_guid']):
                user = DepartmentUser.objects.get(azure_guid=self.data['azure_guid'])
                LOGGER.warning('POST request sent but existing user {} matched by Azure AD GUID'.format(user.email))
        else:
            user = DepartmentUser()

        # Check for essential request params.
        if 'EmailAddress' not in self.data and 'email' not in self.data:
            raise BadRequest('Missing email parameter value')
        if 'DisplayName' not in self.data and 'name' not in self.data:
            raise BadRequest('Missing name parameter value')
        if 'SamAccountName' not in self.data and 'username' not in self.data:
            raise BadRequest('Missing account name parameter value')

        # Make an assumption that EmailAddress or email is passed in.
        if 'EmailAddress' in self.data:
            LOGGER.info('Creating user {}'.format(self.data['EmailAddress'].lower()))
        else:
            LOGGER.info('Creating user {}'.format(self.data['email'].lower()))

        # Required: email, name and sAMAccountName.
        if 'EmailAddress' in self.data:
            user.email = self.data['EmailAddress'].lower()
        elif 'email' in self.data:
            user.email = self.data['email'].lower()
        if 'DisplayName' in self.data:
            user.name = self.data['DisplayName']
        elif 'name' in self.data:
            user.name = self.data['name']
        if 'SamAccountName' in self.data:
            user.username = self.data['SamAccountName']
        elif 'username' in self.data:
            user.username = self.data['username']
        # Optional fields.
        if 'Enabled' in self.data:
            user.active = self.data['Enabled']
        elif 'active' in self.data:
            user.active = self.data['active']
        if 'ObjectGUID' in self.data:
            user.ad_guid = self.data['ObjectGUID']
        elif 'ad_guid' in self.data:
            user.ad_guid = self.data['ad_guid']
        if 'azure_guid' in self.data:  # Exception to the if/elif rule.
            user.azure_guid = self.data['azure_guid']
        if 'AccountExpirationDate' in self.data and self.data['AccountExpirationDate']:
            user.expiry_date = TIMEZONE.localize(parse(self.data['AccountExpirationDate']))
        elif 'expiry_date' in self.data and self.data['expiry_date']:
            user.expiry_date = TIMEZONE.localize(parse(self.data['expiry_date']))
        if 'Title' in self.data:
            user.title = self.data['Title']
        elif 'title' in self.data:
            user.title = self.data['title']
        if 'GivenName' in self.data:
            user.given_name = self.data['GivenName']
        elif 'given_name' in self.data:
            user.given_name = self.data['given_name']
        if 'Surname' in self.data:
            user.surname = self.data['Surname']
        elif 'surname' in self.data:
            user.surname = self.data['surname']

        try:
            user.save()
        except Exception as e:
            LOGGER.exception('Error creating user {}'.format(user.email))
            return self.formatters.format(self.request, {'Error': repr(e)})

        # Serialise and return the newly-created DepartmentUser.
        data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
        return self.formatters.format(self.request, data)

    def update(self, guid):
        """Update view to handle changes to a DepartmentUser object.
        This view also handles marking users as 'Inactive' or 'Deleted'
        within AD.
        """
        try:
            user = DepartmentUser.objects.get(ad_guid=guid)
        except DepartmentUser.DoesNotExist:
            try:
                user = DepartmentUser.objects.get(email__iexact=guid.lower())
            except DepartmentUser.DoesNotExist:
                raise BadRequest('Object not found')

        LOGGER.info('Updating user guid/email {}'.format(guid))

        try:
            if 'EmailAddress' in self.data and self.data['EmailAddress']:
                user.email = self.data['EmailAddress'].lower()
            elif 'email' in self.data and self.data['email']:
                user.email = self.data['email'].lower()
            if 'DisplayName' in self.data and self.data['DisplayName']:
                user.name = self.data['DisplayName']
            elif 'name' in self.data and self.data['name']:
                user.name = self.data['name']
            if 'SamAccountName' in self.data and self.data['SamAccountName']:
                user.username = self.data['SamAccountName']
            elif 'username' in self.data and self.data['username']:
                user.username = self.data['username']
            if 'ObjectGUID' in self.data and self.data['ObjectGUID']:
                user.ad_guid = self.data['ObjectGUID']
            elif 'ad_guid' in self.data and self.data['ad_guid']:
                user.ad_guid = self.data['ad_guid']
            if 'AccountExpirationDate' in self.data and self.data['AccountExpirationDate']:
                user.expiry_date = TIMEZONE.localize(parse(self.data['AccountExpirationDate']))
            elif 'expiry_date' in self.data and self.data['expiry_date']:
                user.expiry_date = TIMEZONE.localize(parse(self.data['expiry_date']))
            if 'Title' in self.data and self.data['Title']:
                user.title = self.data['Title']
            elif 'title' in self.data and self.data['title']:
                user.title = self.data['title']
            if 'GivenName' in self.data and self.data['GivenName']:
                user.given_name = self.data['GivenName']
            elif 'given_name' in self.data and self.data['given_name']:
                user.given_name = self.data['given_name']
            if 'Surname' in self.data and self.data['Surname']:
                user.surname = self.data['Surname']
            elif 'surname' in self.data and self.data['surname']:
                user.surname = self.data['surname']
            if 'o365_licence' in self.data:  # Boolean; don't only work on True!
                user.o365_licence = self.data['o365_licence']
            if 'azure_guid' in self.data and self.data['azure_guid']:
                user.azure_guid = self.data['azure_guid']
            if 'Enabled' in self.data:  # Boolean; don't only work on True!
                user.active = self.data['Enabled']
            if 'active' in self.data:  # Boolean; don't only work on True!
                user.active = self.data['active']
            if 'Deleted' in self.data and self.data['Deleted']:
                user.active = False
                user.ad_guid, user.azure_guid = None, None
                data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
                LOGGER.info('Set user {} as deleted in AD'.format(user.name))
            user.ad_data = self.data  # Store the raw request data.
            user.ad_updated = True
            user.save()
        except Exception as e:
            LOGGER.exception('Error updating user {}'.format(user.email))
            return self.formatters.format(self.request, {'Error': repr(e)})

        data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
        return self.formatters.format(self.request, data)

    def org_structure(self, sync_o365=False):
        """A custom API endpoint to return the organisation structure: a list
        of each organisational unit's metadata (name, manager, members).
        Includes OrgUnits, cost centres, locations and secondary locations.
        """
        qs = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER)
        # Exclude predefined account types:
        qs = qs.exclude(account_type__in=DepartmentUser.ACCOUNT_TYPE_EXCLUDE)
        structure = []
        if sync_o365:  # Exclude certain things from populating O365/AD
            orgunits = OrgUnit.objects.filter(active=True, unit_type__in=[0, 1], sync_o365=True)
            costcentres = []
            locations = Location.objects.filter(active=True)
        else:
            orgunits = OrgUnit.objects.filter(active=True)
            costcentres = CostCentre.objects.filter(active=True)
            locations = Location.objects.filter(active=True)
        defaultowner = None
        for obj in orgunits:
            members = [d[0] for d in qs.filter(org_unit__in=obj.get_descendants(include_self=True)).values_list('email')]
            # We also need to iterate through DepartmentUsers to add those with
            # secondary OrgUnits to each OrgUnit.
            for i in DepartmentUser.objects.filter(org_units_secondary__isnull=False):
                if obj in i.org_units_secondary.all():
                    members.append(i.email)
            structure.append({'id': 'db-org_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name),
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': list(set(members))})
        for obj in costcentres:
            members = [d[0] for d in qs.filter(cost_centre=obj).values_list('email')]
            # We also need to iterate through DepartmentUsers to add those with
            # secondary CCs as members to each CostCentre.
            for i in DepartmentUser.objects.filter(cost_centres_secondary__isnull=False):
                if obj in i.cost_centres_secondary.all():
                    members.append(i.email)
            structure.append({'id': 'db-cc_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name),
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': list(set(members))})
        for obj in locations:
            members = [d[0] for d in qs.filter(location=obj).values_list('email')]
            structure.append({'id': 'db-loc_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name) + '-location',
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': members})
        for row in structure:
            if row['members']:
                row['email'] = '{}@{}'.format(
                    row['email'], row['members'][0].split('@', 1)[1])
        return structure


class LocationResource(CSVDjangoResource):
    VALUES_ARGS = (
        'pk', 'name', 'address', 'phone', 'fax', 'email', 'point', 'url', 'bandwidth_url', 'active')

    def list_qs(self):
        FILTERS = {}
        if 'location_id' in self.request.GET:
            FILTERS['pk'] = self.request.GET['location_id']
        else:
            FILTERS['active'] = True
        return Location.objects.filter(**FILTERS).values(*self.VALUES_ARGS)

    @skip_prepare
    def list(self):
        data = list(self.list_qs())
        for row in data:
            if row['point']:
                row['point'] = row['point'].wkt
        return data


class UserSelectResource(DjangoResource):
    """A small API resource to provide DepartmentUsers for select lists.
    """
    preparer = FieldsPreparer(fields={
        'id': 'id',
        'text': 'email',
    })

    def list(self):
        FILTERS = DepartmentUser.ACTIVE_FILTER.copy()
        users = DepartmentUser.objects.filter(**FILTERS)
        if 'q' in self.request.GET:
            users = DepartmentUser.objects.filter(email__icontains=self.request.GET['q'])
        return users


@csrf_exempt
def profile(request):
    """An API view that returns the profile for the request user.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    # Profile API view should return one object only.
    self = DepartmentUserResource()
    if not hasattr(request, 'user') or not request.user.email:
        return HttpResponseBadRequest('No user email in request')
    qs = DepartmentUser.objects.filter(email__iexact=request.user.email)
    if qs.count() > 1 or qs.count() < 1:
        return HttpResponseBadRequest('API request for {} should return one profile; it returned {}!'.format(
            request.user.email, qs.count()))
    user = qs.get(email__iexact=request.user.email)

    if request.method == 'GET':
        data = qs.values(*self.VALUES_ARGS)[0]
        # Add the password_age_days property to the API response.
        data['password_age_days'] = user.password_age_days
    elif request.method == 'POST':
        if 'telephone' in request.POST:
            user.telephone = request.POST['telephone']
        if 'mobile_phone' in request.POST:
            user.mobile_phone = request.POST['mobile_phone']
        if 'extension' in request.POST:
            user.extension = request.POST['extension']
        if 'other_phone' in request.POST:
            user.other_phone = request.POST['other_phone']
        if 'preferred_name' in request.POST:
            user.preferred_name = request.POST['preferred_name']
        user.save()
        data = DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS)[0]

    return HttpResponse(json.dumps(
        {'objects': [self.formatters.format(request, data)]}, cls=MoreTypesJSONEncoder),
        content_type='application/json')
