from django.urls import reverse

from itassets.test_api import ApiTestCase


class ViewsTestCase(ApiTestCase):
    def test_view_address_book(self):
        """Test the Address Book view"""
        url = reverse("address_book")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user1.name)
        self.assertContains(resp, self.user2.name)
        # Check the exclusion rules.
        self.assertNotContains(resp, self.inactive_user.name)

    def test_view_address_book_filtered(self):
        """Test the filtered Address Book view"""
        url = reverse("address_book") + f"?q={self.user1.name}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user1.name)
        self.assertNotContains(resp, self.user2.name)

    def test_view_user_accounts(self):
        """Test the User Accounts view"""
        url = reverse("user_accounts")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.user1.name)
        self.assertContains(resp, self.user2.name)
        # Remove the license from a user and re-check.
        self.user1.assigned_licences = []
        self.user1.save()
        resp = self.client.get(url)
        self.assertNotContains(resp, self.user1.name)
        self.assertContains(resp, self.user2.name)
