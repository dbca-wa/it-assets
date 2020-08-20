from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase

from tracking.models import Computer
User = get_user_model()


class RegistersAdminTestCase(ApiTestCase):
    client = Client()

    def setUp(self):
        super(RegistersAdminTestCase, self).setUp()
        # Create an admin user.
        self.admin_user = mixer.blend(User, username='admin', is_superuser=True, is_staff=True)
        self.admin_user.set_password('pass')
        self.admin_user.save()
        # Create some Computers
        self.com1 = mixer.blend(Computer)
        self.com2 = mixer.blend(Computer)
        # Log in as admin user by default
        self.client.login(username='admin', password='pass')

    def test_itsystem_export(self):
        """Test the ITSystemAdmin export view
        """
        url = reverse('admin:itsystem_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header("Content-Disposition"))
        self.assertEqual(response['Content-Type'],
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
