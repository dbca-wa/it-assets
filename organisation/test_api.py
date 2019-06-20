from datetime import datetime
import json
from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase
from unittest import skip
from uuid import uuid1

from django.test import TestCase, client
from django.urls import reverse

from organisation.models import DepartmentUser, Location

from django.conf import settings
import pytz
from dateutil.parser import parse


class ProfileTestCase(ApiTestCase):
    url = '/api/profile/'

    def test_profile_api_get(self):
        """Test the profile API endpoint GET response
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_profile_api_post(self):
        """Test the profile API endpoint GET response
        """
        response = self.client.get(self.url)
        j = response.json()
        obj = j['objects'][0]
        #self.assertFalse(obj['telephone'])
        #tel = '9111 1111'
        #response = self.client.post(self.url, {'telephone': tel})
        #self.assertEqual(response.status_code, 200)
        #j = response.json()
        #obj = j['objects'][0]
        #self.assertEqual(obj['telephone'], tel)

        self.assertFalse(obj['telephone'])
        tel = '9111 1111'
        for f, v in [
            ('telephone', '91111 1111'),
            ('mobile_phone', '9111 1112'),
            ('extension', '211'), ('other_phone', '9111 1113'), ('preferred_name', 'amy')
        ]:
            response = self.client.post(self.url, {f: v})
            self.assertEqual(response.status_code, 200)
            j = response.json()
            obj = j['objects'][0]
            self.assertEqual(obj[f], v)

    def test_profile_api_anon(self):
        """Test that anonymous users can't use the profile endpoint
        """
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class OptionResourceTestCase(ApiTestCase):

    @skip('Inconsistent testing results')
    def test_data_org_structure(self):
        """Test the data_org_structure API endpoint
        """
        url = '/api/options/?list=org_structure'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Division 1 will be present in the response.
        self.assertContains(response, self.div1.name)
        # Response can be deserialised into a dict.
        r = response.json()
        self.assertTrue(isinstance(r, dict))
        # Deserialised response contains a list.
        self.assertTrue(isinstance(r['objects'], list))
        # Make OrgUnit inactive to test exclusion.
        self.branch1.active = False
        self.branch1.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Division 1 won't be present in the response.
        self.assertNotContains(response, self.branch1.name)

    def test_data_cost_centre(self):
        """Test the data_cost_centre API endpoint
        """
        url = '/api/options/?list=cost_centre'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # 001 will be present in the response.
        self.assertContains(response, self.cc1.code)
        # Add 'inactive' to Division 1 name to inactivate the CC.
        self.div1.name = 'Division 1 (inactive)'
        self.div1.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # 001 won't be present in the response.
        self.assertNotContains(response, self.cc1.code)

    def test_data_org_unit(self):
        """Test the data_org_unit API endpoint
        """
        url = '/api/options/?list=org_unit'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Org unit names will be present in the response.
        self.assertContains(response, self.dept.name)
        self.assertContains(response, self.div1.name)
        self.assertContains(response, self.div2.name)

    def test_data_dept_user(self):
        """Test the data_dept_user API endpoint
        """
        url = '/api/options/?list=dept_user'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # User 1 will be present in the response.
        self.assertContains(response, self.user1.email)
        # Make a user inactive to test excludion
        self.user1.active = False
        self.user1.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # User 1 won't be present in the response.
        self.assertNotContains(response, self.user1.email)


class DepartmentUserResourceTestCase(ApiTestCase):

    def test_list(self):
        """Test the DepartmentUserResource list responses
        """
        url = '/api/users/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        r = response.json()
        self.assertTrue(isinstance(r['objects'], list))
        # Response should not contain inactive, contractors or shared accounts.
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.del_user.email)
        self.assertNotContains(response, self.contract_user.email)
        self.assertNotContains(response, self.shared.email)
        # Test the compact response.
        url = '/api/users/?compact=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Test the minimal response.
        url = '/api/users/?minimal=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_list_filtering(self):
        """Test the DepartmentUserResource filtered list responses
        """
        # Test the "all" response.
        url = '/api/users/?all=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.contract_user.email)
        self.assertContains(response, self.del_user.email)
        self.assertContains(response, self.shared.email)
        # Test filtering by ad_deleted.
        url = '/api/users/?ad_deleted=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.del_user.email)
        self.assertNotContains(response, self.user1.email)
        url = '/api/users/?ad_deleted=false'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.del_user.email)
        self.assertContains(response, self.user1.email)
        # Test filtering by email (should return only one object).
        url = '/api/users/?email={}'.format(self.user1.email)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        j = response.json()
        self.assertEqual(len(j['objects']), 1)
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.user2.email)
        # Test filtering by GUID (should return only one object).
        url = '/api/users/?ad_guid={}'.format(self.user1.ad_guid)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        j = response.json()
        self.assertEqual(len(j['objects']), 1)
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.user2.email)
        # Test filtering by cost centre (should return all, inc. inactive and contractors).
        url = '/api/users/?cost_centre={}'.format(self.cc2.code)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user2.email)
        self.assertContains(response, self.contract_user.email)
        self.assertContains(response, self.del_user.email)
        self.assertNotContains(response, self.user1.email)
        self.assertNotContains(response, self.shared.email)  # Belongs to CC1.
        # Test filtering by O365 licence status.
        self.user1.o365_licence = True
        self.user1.save()
        url = '/api/users/?o365_licence=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user1.email)
        self.assertNotContains(response, self.user2.email)

    def test_detail(self):
        """Test the DepartmentUserResource detail response
        """
        # Test detail URL using ad_guid.
        url = '/api/users/{}/'.format(self.user1.ad_guid)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Test URL using email also.
        url = '/api/users/{}/'.format(self.user1.email.lower())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_org_structure(self):
        """Test the DepartmentUserResource org_structure response
        """
        url = '/api/users/?org_structure=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # User 1 will be present in the response.
        self.assertContains(response, self.user1.email)
        # Division 1 will be present in the response.
        self.assertContains(response, self.div1.name)

    def test_org_structure_sync_0365(self):
        """Test the sync_o365=true request parameter
        """
        self.div1.sync_o365 = False
        self.div1.save()
        url = '/api/users/?org_structure=true&sync_o365=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Division 1 won't be present in the response.
        self.assertNotContains(response, self.div1.name)

    def test_org_structure_populate_groups_members(self):
        """Test populate_groups=true request parameter
        """
        self.user3.populate_primary_group = False
        self.user3.save()
        url = '/api/users/?org_structure=true&populate_groups=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # User 2 will be present in the response.
        self.assertContains(response, self.user2.email)
        # User 3 won't be present in the response.
        self.assertNotContains(response, self.user3.email)

    def test_create_invalid(self):
        """Test the DepartmentUserResource create response with missing data
        """
        url = '/api/users/'
        data = {}
        username = str(uuid1())[:8]
        # Response should be status 400 where essential parameters are missing.
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data['EmailAddress'] = '{}@dbca.wa.gov.au'.format(username)
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data['DisplayName'] = 'Doe, John'
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data['SamAccountName'] = username
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)  # Now valid.

    def test_create_valid(self):
        """Test the DepartmentUserResource create response with valid data
        """
        url = '/api/users/'
        username = str(uuid1())[:8]
        data = {
            'EmailAddress': '{}@dbca.wa.gov.au'.format(username),
            'DisplayName': 'Doe, John',
            'SamAccountName': username,
            'DistinguishedName': 'CN={},OU=Users,DC=domain'.format(username),
            'AccountExpirationDate': datetime.now().isoformat(),
            'Enabled': True,
            'ObjectGUID': str(uuid1()),
            'GivenName': 'John',
            'Surname': 'Doe',
            'Title': 'Content Creator',
            'Modified': datetime.now().isoformat(),
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        # A DepartmentUser with that email should now exist.
        self.assertTrue(DepartmentUser.objects.filter(email=data['EmailAddress']).exists())

    def test_create_valid_alt(self):
        """Test the DepartmentUserResource create response with alternate parameter names
        """
        url = '/api/users/'
        username = str(uuid1())[:8]
        data = {
            'email': '{}@dbca.wa.gov.au'.format(username),
            'name': 'Doe, John',
            'username': username,
            'ad_dn': 'CN={},OU=Users,DC=domain'.format(username),
            'expiry_date': datetime.now().isoformat(),
            'active': True,
            'ad_guid': str(uuid1()),
            'given_name': 'John',
            'surname': 'Doe',
            'title': 'Content Creator',
            'date_ad_updated': datetime.now().isoformat(),
        }
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(DepartmentUser.objects.filter(email=data['email']).exists())


    def test_update(self):
        """Test the DepartmentUserResource update response
        """
        tz = pytz.timezone(settings.TIME_ZONE)
        self.assertFalse(self.user1.o365_licence)
        url = '/api/users/{}/'.format(self.user1.ad_guid)
        data = {
            'Surname': 'Lebowski',
            'title': 'Bean Counter',
            'o365_licence': True,

            'email' : 'l@example.com' ,
            'name' : 'Mike' ,
            'username' : 'MikeLebowski' ,
            'ad_guid' : '123',
            'expiry_date' : '2019-03-12',
            'given_name' : 'Mike',
            #'Enabled' :'True',
            'active' : True,
            'deleted' : False,



        }
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        user = DepartmentUser.objects.get(pk=self.user1.pk)  # Refresh from db
        self.assertEqual(user.surname, data['Surname'])
        self.assertEqual(user.title, data['title'])

        self.assertEqual(user.name , data['name'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.username, data['username'])

        #self.assertEqual(user.expiry_date, data['expiry_date'])

        self.assertEqual(user.ad_guid, data['ad_guid'])

        self.assertEqual(user.expiry_date, tz.localize(parse(data['expiry_date'])))

        self.assertEqual(user.given_name, data['given_name'])
        #self.assertEqual(user.active, data['Enabled'])
        self.assertEqual(user.active, data['active'])
        self.assertEqual(user.ad_deleted, data['deleted'])

        self.assertTrue(user.o365_licence)
        self.assertTrue(user.in_sync)

    def test_disable(self):
        """Test the DepartmentUserResource update response (set user as inactive)
        """
        self.assertTrue(self.user1.active)
        self.assertFalse(self.user1.ad_deleted)
        url = '/api/users/{}/'.format(self.user1.ad_guid)
        data = {
            'Enabled': False,
        }
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        user = DepartmentUser.objects.get(pk=self.user1.pk)  # Refresh from db
        self.assertFalse(user.ad_deleted)
        self.assertFalse(user.active)
        self.assertTrue(user.in_sync)

    def test_delete(self):
        """Test the DepartmentUserResource update response (set user as 'AD deleted')
        """
        self.assertFalse(self.user1.ad_deleted)
        self.assertTrue(self.user1.active)
        url = '/api/users/{}/'.format(self.user1.ad_guid)
        data = {'Deleted': True}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        user = DepartmentUser.objects.get(pk=self.user1.pk)  # Refresh from db
        self.assertTrue(user.ad_deleted)
        self.assertFalse(user.active)
        self.assertTrue(user.in_sync)
        # Also delete a second object, to check for silly 'empty string' collisions.
        url = '/api/users/{}/'.format(self.user2.ad_guid)
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 202)


class LocationResourceTestCase(ApiTestCase):

    def test_list(self):
        """Test the LocationResource list response
        """
        loc_inactive = mixer.blend(Location, manager=None, active=False)
        url = '/api/locations/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Response should not contain the inactive Location.
        self.assertNotContains(response, loc_inactive.name)

    def test_filter(self):
        """Test the LocationResource filtered response
        """
        url = '/api/locations/?location_id={}'.format(self.loc1.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.loc1.name)
        # We can still return inactive locations by ID
        loc_inactive = mixer.blend(Location, manager=None, active=False)
        url = '/api/locations/?location_id={}'.format(loc_inactive.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, loc_inactive.name)

# Incomplete ..............
class UserSelectResourceTestCase(ApiTestCase):

    def test_list(self):

        url = '/api/user-select/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)



class DepartmentUserExportTestCase(ApiTestCase):

    def setUp(self):
        super(DepartmentUserExportTestCase, self).setUp()
        # Create some hardware.
        mixer.cycle(10).blend(DepartmentUser)


    def test_get(self):

        url = reverse('admin:departmentuser_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertTrue(response.has_header("Content-Disposition"))
        self.assertEqual(response['Content-Type'],
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
