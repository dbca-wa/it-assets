from mixer.backend.django import mixer
from itassets.test_api import ApiTestCase

from django.urls import reverse
from django.test import TestCase

from assets.models import HardwareAsset

from django.contrib.auth import get_user_model
from django.test import Client
import json


class HardwareAssetResourceTestCase(ApiTestCase):

    def setUp(self):
        super(HardwareAssetResourceTestCase, self).setUp()

        # Create some hardware.
        mixer.cycle(2).blend(HardwareAsset)

    def test_list(self):
        url = '/api/hardware-assets/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # incomplete test case
    def test_list_filter(self):
        url = '/api/hardware-assets/?all=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url = '/api/hardware-assets/?asset_tag'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        url = '/api/hardware-assets/?cost_centre'
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


# To Do: Add test to check content type (i.e csv) and record content
class HardwareAssetCSVTestCase(TestCase):
    def test_get(self):

        url = '/api/hardware-assets/csv/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


#Test for the HardwareAssetExport view
class HardwareAssetExportTestCase(ApiTestCase):

    def setUp(self):
        super(HardwareAssetExportTestCase, self).setUp()
        mixer.cycle(5).blend(HardwareAsset)

    def test_get(self):
        url =reverse('admin:hardwareasset_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        #import ipdb; ipdb.set_trace()

        self.assertTrue(response.has_header("Content-Disposition"))
        self.assertEqual(response['Content-Type'],
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        #self.assertNotEqual(response['Content-Type'],'text/csv')

    # def test_excel_export(self):
    #     url = reverse('admin:hardwareasset_export')
    #     response = self.client.get(url)
    #
    #     content = response.content.decode('utf-8')
    #     excel_reader = csv.reader(io.BytesIO(content))
    #     body = list(cvs_reader)
    #     headers = body.pop(0)
    #
    #     print(body)
    #     print(headers)
