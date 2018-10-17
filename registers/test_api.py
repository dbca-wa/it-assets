from itassets.test_api import ApiTestCase


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
