from django.urls import reverse

from itassets.test_api import ApiTestCase


class ViewsTestCase(ApiTestCase):
    def test_view_address_book(self):
        """Test the Address Book view"""
        url = reverse("address_book")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user_permanent.name)
        self.assertContains(resp, self.user_contract.name)
        # Check the exclusion rules.
        self.assertNotContains(resp, self.inactive_user.name)

    def test_view_address_book_filtered(self):
        """Test the filtered Address Book view"""
        url = reverse("address_book") + f"?q={self.user_permanent.name}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user_permanent.name)
        self.assertNotContains(resp, self.user_contract.name)

    def test_view_user_accounts(self):
        """Test the User Accounts view"""
        url = reverse("user_accounts")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user_permanent.name)
        self.assertContains(resp, self.user_contract.name)

    def test_view_user_accounts_no_license(self):
        """Test the User Accounts view excludes users without a licence"""
        self.user_permanent.assigned_licences = None
        self.user_permanent.save()
        url = reverse("user_accounts")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user_contract.name)
        self.assertNotContains(resp, self.user_permanent.name)
