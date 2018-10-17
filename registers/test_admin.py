from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase

from registers.models import ITSystemHardware, Incident, IncidentLog
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
        # Create some ITSystemHardware objects
        self.itsys1 = mixer.blend(ITSystemHardware, computer=self.com1, production=True)
        self.itsys2 = mixer.blend(ITSystemHardware, computer=self.com2)
        # Attach ITSystemHardware to ITSystem objects.
        self.it1.hardwares.add(self.itsys1)
        self.it2.hardwares.add(self.itsys2)
        # Create some Incidents and IncidentLogs.
        mixer.cycle(3).blend(Incident)
        mixer.cycle(3).blend(IncidentLog)
        # Log in as admin user by default
        self.client.login(username='admin', password='pass')

    def test_itsystemhardware_export(self):
        """Test the ITSystemHardwareAdmin export view
        """
        url = reverse('admin:itsystemhardware_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_itsystem_export(self):
        """Test the ITSystemAdmin export view
        """
        url = reverse('admin:itsystem_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_itsystemdependency_reports(self):
        """Test the ITSystemDependencyAdmin reports view
        """
        url = reverse('admin:itsystem_dependency_reports')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_itsystemdependency_report_all(self):
        """Test the ITSystemDependencyAdmin reports/all view
        """
        url = reverse('admin:itsystem_dependency_report_all')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_itsystemdependency_report_nodeps(self):
        """Test the ITSystemDependencyAdmin reports/nodeps view
        """
        url = reverse('admin:itsystem_dependency_report_nodeps')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_incident_export(self):
        """Test the Incident export view
        """
        url = reverse('admin:incident_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
