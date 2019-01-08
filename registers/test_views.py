from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from mixer.backend.django import mixer

from .models import ChangeRequest, ChangeLog

User = get_user_model()


class RegistersViewsTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Create/log in a normal user.
        self.n_user = mixer.blend(User, username='normaluser', is_superuser=False, is_staff=False)
        self.n_user.set_password('pass')
        self.n_user.save()
        self.client.login(username='normaluser', password='pass')
        mixer.blend(ChangeRequest)
        mixer.cycle(2).blend(ChangeLog)
        self.rfc = ChangeRequest.objects.first()

    def test_changerequest_list(self):
        url = reverse('change_request_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_changerequest_detail(self):
        url = reverse('change_request_detail', kwargs={'pk': self.rfc.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_changerequest_create(self):
        url = reverse('change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_std_changerequest_create(self):
        url = reverse('std_change_request_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
