from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from mixer.backend.django import mixer
from random import randint
from recoup import models
User = get_user_model()


class RecoupTestCase(TestCase):
    client = Client()

    def setUp(self):
        super(RecoupTestCase, self).setUp()
        # Create/log in an admin user.
        self.admin_user = mixer.blend(User, username='admin', is_superuser=True, is_staff=True)
        self.admin_user.set_password('pass')
        self.admin_user.save()
        self.client.login(username='admin', password='pass')
        mixer.cycle(3).blend(models.FinancialYear)
        mixer.cycle(3).blend(models.Contract)
        mixer.cycle(3).blend(models.Bill)
        mixer.cycle(3).blend(models.ServicePool)
        mixer.cycle(3).blend(models.Cost)
        # Can't have any zero-user divisions.
        mixer.cycle(3).blend(models.Division, user_count=randint(1, 100))
        mixer.cycle(3).blend(models.CostCentreLink)
        mixer.cycle(3).blend(models.EndUserService)
        mixer.cycle(3).blend(models.EndUserCost)
        mixer.cycle(3).blend(models.ITPlatform)
        mixer.cycle(3).blend(models.ITPlatformCost)
        mixer.cycle(3).blend(models.DivisionITSystem)
        mixer.cycle(3).blend(models.SystemDependency)

    def test_summary_view(self):
        """Test the recoup summary view loads
        """
        url = reverse('recoup_summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'recoup/summary.html')

    def test_bill_view(self):
        """Test the recoup summary view loads
        """
        for div in models.Division.objects.all():
            url = "{}?division={}".format(reverse('recoup_bill'), div.pk)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'recoup/bill.html')

    def test_duc_report(self):
        """Test the DUC report view
        """
        url = reverse('recoup_report')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_bills_changelist(self):
        """Test the BillAdmin changelist view
        """
        url = reverse('admin:recoup_bill_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_contracts_changelist(self):
        """Test the ContractAdmin changelist view
        """
        url = reverse('admin:recoup_contract_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_costcentrelink_changelist(self):
        """Test the CostCentreLinkAdmin changelist view
        """
        url = reverse('admin:recoup_costcentrelink_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_division_changelist(self):
        """Test the DivisionAdmin changelist view
        """
        url = reverse('admin:recoup_division_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_divisionitsystem_changelist(self):
        """Test the DivisionITSystemAdmin changelist view
        """
        url = reverse('admin:recoup_divisionitsystem_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_enduserservice_changelist(self):
        """Test the EndUserServiceAdmin changelist view
        """
        url = reverse('admin:recoup_enduserservice_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_itplatform_changelist(self):
        """Test the ITPlatformAdmin changelist view
        """
        url = reverse('admin:recoup_itplatform_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_servicepool_changelist(self):
        """Test the ServicePoolAdmin changelist view
        """
        url = reverse('admin:recoup_servicepool_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
