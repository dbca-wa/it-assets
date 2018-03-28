from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase

from assets.models import HardwareAsset


class HardwareAssetResourceTestCase(ApiTestCase):

    def setUp(self):
        super(HardwareAssetResourceTestCase, self).setUp()
        # Create some hardware.
        mixer.cycle(2).blend(HardwareAsset)

    def test_list(self):
        url = '/api/hardware-assets/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_csv(self):
        url = '/api/hardware-assets/csv/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail(self):
        hw = HardwareAsset.objects.first()
        url = '/api/hardware-assets/{}/'.format(hw.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail_tag(self):
        hw = HardwareAsset.objects.first()
        hw.asset_tag = 'IT12345'
        hw.save()
        url = '/api/hardware-assets/{}/'.format(hw.asset_tag)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        url = '/api/hardware-assets/{}/'.format(hw.asset_tag.lower())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
