from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from mixer.backend.django import mixer
from random import randint

from assets.models import HardwareAsset, SoftwareAsset

User = get_user_model()


def random_datetime(days=3650):
    # Return a random datetime, no more than `days` old.
    return datetime.now() - timedelta(days=randint(1, days))


class AssetsAdminTestCase(TestCase):

    def setUp(self):
        super(AssetsAdminTestCase, self).setUp()
        # Create/log in an admin user.
        self.admin_user = mixer.blend(User, username='admin', is_superuser=True, is_staff=True)
        self.admin_user.set_password('pass')
        self.admin_user.save()
        self.client.login(username='admin', password='pass')
        mixer.cycle(5).blend(
            HardwareAsset, purchased_value=randint(100, 1000), date_purchased=random_datetime)

        mixer.cycle(5).blend(
            SoftwareAsset, support_expiry=random_datetime)

    def test_hardwareasset_changelist(self):
        """Test the HardwareAssetAdmin changelist view
        """
        url = reverse('admin:assets_hardwareasset_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_hardwareasset_import(self):
        """Test the HardwareAssetAdmin asset_import view
        """
        url = reverse('admin:asset_import')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/hardwareasset_import_start.html')

    def test_hardwareasset_import_confirm(self):
        """Test the HardwareAssetAdmin asset_import POST response
        """
        url = reverse('admin:asset_import')
        f = SimpleUploadedFile('file.txt', b'file_content')
        response = self.client.post(url, {'file': f})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/hardwareasset_import_start.html')

    # find/create path url for admin assets , Test incomplete
    # def test_softwareasset(self):
    #
    #     url = reverse('admin:assets_softwareasset')
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, 200)
