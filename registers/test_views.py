from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from pytz import timezone

from registers.models import ITSystem, ChangeRequest, ChangeLog
from organisation.models import DepartmentUser

User = get_user_model()
TZ = timezone(settings.TIME_ZONE)


class RegistersViewsTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Create/log in a normal user.
        self.n_user = mixer.blend(User, username='normaluser', is_superuser=False, is_staff=False)
        self.n_user.set_password('pass')
        self.n_user.save()
        self.client.login(username='normaluser', password='pass')
        mixer.blend(ITSystem)
        mixer.blend(DepartmentUser)
        mixer.blend(ChangeRequest)
        mixer.blend(ChangeLog)
        self.rfc = ChangeRequest.objects.first()

    def test_changerequest_list(self):
        url = reverse('change_request_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_changerequest_list_filter(self):
        q = self.rfc.title.split()[0]
        url = '{}?q={}'.format(reverse('change_request_list'), q)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.rfc.title)

    def test_changerequest_detail(self):
        url = reverse('change_request_detail', kwargs={'pk': self.rfc.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_changerequest_create_get(self):
        url = reverse('change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create a draft change request')

    def test_changerequest_create_post(self):
        self.assertFalse(ChangeRequest.objects.filter(title='A new test RFC'))
        url = reverse('change_request_create')
        resp = self.client.post(url, {'title': 'A new test RFC'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ChangeRequest.objects.filter(title='A new test RFC'))

    def test_changerequest_change(self):
        url = reverse('change_request_change', kwargs={'pk': self.rfc.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Change the RFC status to something other than 'draft'; the view should redirect instead.
        self.rfc.status = 6
        self.rfc.save()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    # TODO: test the business logic around 'Save and submit for endorsement'.

    def test_changerequest_endorse(self):
        url = reverse('change_request_endorse', kwargs={'pk': self.rfc.pk})
        resp = self.client.get(url)
        # A draft RFC should redirect instead of returning.
        self.assertEqual(resp.status_code, 302)
        # Change the status to 'submitted'; it should still redirect because we have no endorser recorded.
        self.rfc.status = 1
        self.rfc.save()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        # To properly test the endorse view, we need both a User and a DepartmentUser with
        # matching email addresses. The User needs to be the one making the HTTP request.
        # Create & login our new User.
        user = mixer.blend(User, username='endorser', email='endorser@email.wow', is_superuser=False, is_staff=False)
        user.set_password('pass')
        user.save()
        self.client.logout()
        self.client.login(username='endorser', password='pass')
        # Set the matching DepartmentUser as the RFC endorser; the view should now return.
        self.rfc.endorser = mixer.blend(DepartmentUser, email=user.email)
        self.rfc.save()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_changerequest_export(self):
        url = reverse('change_request_export')
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.has_header("Content-Disposition"))
        self.assertEqual(resp['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_changerequest_calendar(self):
        url = reverse('change_request_calendar')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_std_changerequest_create(self):
        url = reverse('std_change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create a draft standard change request')

    def test_std_changerequest_list(self):
        url = reverse('standard_change_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_calendar(self):
        url = reverse('change_request_calendar')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_change_calendar_date(self):
        self.rfc.planned_start = datetime.now().astimezone(TZ)
        self.rfc.save()
        url = '{}{}/'.format(reverse('change_request_calendar'), self.rfc.planned_start.strftime('%Y-%m-%d'))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.rfc.title)

    def test_change_calendar_month(self):
        self.rfc.planned_start = datetime.now().astimezone(TZ)
        self.rfc.save()
        url = '{}{}/'.format(reverse('change_request_calendar'), self.rfc.planned_start.strftime('%Y-%m'))
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.rfc.title)
