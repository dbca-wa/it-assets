from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from pytz import timezone

from registers.models import ITSystem, Incident, ChangeRequest, ChangeLog

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
        mixer.cycle(2).blend(ChangeRequest)
        mixer.cycle(2).blend(ChangeLog)
        self.rfc = ChangeRequest.objects.first()
        mixer.blend(ITSystem)
        mixer.blend(Incident)
        self.incident = Incident.objects.first()

    def test_itsystem_export(self):
        url = reverse('itsystem_export')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_incident_list(self):
        url = reverse('incident_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_incident_detail(self):
        url = reverse('incident_detail', kwargs={'pk': self.incident.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

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

    def test_changerequest_create(self):
        url = reverse('change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create a draft change request')

    def test_std_changerequest_create(self):
        url = reverse('std_change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create a draft standard change request')

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

    def test_change_request_export(self):
        url = reverse('change_request_export')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
