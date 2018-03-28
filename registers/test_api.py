from datetime import timedelta
from django.utils import timezone
from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase

from registers.models import ITSystemEvent


class ITSystemResourceTestCase(ApiTestCase):

    def test_list(self):
        """Test the ITSystemResource list response
        """
        url = '/api/itsystems/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'development' & decommissioned IT systems won't be in the response.
        self.assertNotContains(response, self.it2.name)
        self.assertNotContains(response, self.it_dec.name)
        # Test all request parameter.
        url = '/api/itsystems/?all'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'development' IT system will be in the response.
        self.assertContains(response, self.it2.name)
        # Test filtering by system_id
        url = '/api/itsystems/?system_id={}'.format(self.it1.system_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.it1.name)
        self.assertNotContains(response, self.it2.name)


class ITSystemHardwareResourceTestCase(ApiTestCase):

    def test_list(self):
        url = '/api/itsystem-hardware/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'decommissioned' IT system won't be in the response.
        self.assertNotContains(response, self.it_dec.name)


class ITSystemEventResourceTestCase(ApiTestCase):

    def setUp(self):
        super(ITSystemEventResourceTestCase, self).setUp()
        # Create some events
        self.event_current = mixer.blend(ITSystemEvent, planned=False, start=timezone.now())
        self.event_past = mixer.blend(
            ITSystemEvent, planned=True, start=timezone.now() - timedelta(hours=1),
            end=timezone.now(), current=False)

    def test_list(self):
        url = '/api/events/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail(self):
        url = '/api/events/{}/'.format(self.event_current.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_current(self):
        url = '/api/events/current/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'non-current' event won't be in the response.
        self.assertNotContains(response, self.event_past.description)
