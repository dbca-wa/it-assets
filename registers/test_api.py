from django.urls import reverse
from itassets.test_api import ApiTestCase


class ITSystemAPIResourceTestCase(ApiTestCase):

    def test_list(self):
        """Test the ITSystemAPIResource list response
        """
        url = reverse('it_system_api_resource')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.it_prod.name)
        self.assertContains(response, self.it_leg.name)
        # The 'development' & decommissioned IT systems won't be in the response.
        self.assertNotContains(response, self.it_dev.name)
        self.assertNotContains(response, self.it_dec.name)

    def test_list_filtering(self):
        """Test the ITSystemAPIResource filtered responses
        """
        url = reverse('it_system_api_resource', kwargs={'pk': self.it_prod.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.it_prod.name)
        self.assertNotContains(response, self.it_leg.name)
        url = '{}?q={}'.format(reverse('it_system_api_resource'), self.it_leg.name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.it_prod.name)
        self.assertContains(response, self.it_leg.name)

    def test_list_tailored(self):
        """Test the ITSystemAPIResource tailored list responses
        """
        url = '{}?selectlist='.format(reverse('it_system_api_resource'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
