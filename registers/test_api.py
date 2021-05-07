from itassets.test_api import ApiTestCase


class ITSystemResourceTestCase(ApiTestCase):

    def test_list(self):
        """Test the ITSystemResource list response
        """
        url = '/api/v1/itsystems/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'development' & decommissioned IT systems won't be in the response.
        self.assertNotContains(response, self.it2.name)
        self.assertNotContains(response, self.it_dec.name)

    def test_list_all(self):
        """Test the ITSystemResource list response with all param
        """
        url = '/api/v1/itsystems/?all'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # The 'development' IT system will be in the response.
        self.assertContains(response, self.it2.name)

    def test_list_filter(self):
        """Test the ITSystemResource list response with system_id param
        """
        url = '/api/v1/itsystems/?system_id={}'.format(self.it1.system_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.it1.name)
        self.assertNotContains(response, self.it2.name)
