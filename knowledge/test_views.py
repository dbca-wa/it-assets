from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase, Client
from mixer.backend.django import mixer
from organisation.models import DepartmentUser
from registers.models import ITSystem


User = get_user_model()


class KnowledgeViewsTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Create User and linked DepartmentUser objects.
        self.du1 = mixer.blend(DepartmentUser, username=mixer.RANDOM, photo=None)
        self.user1 = User.objects.create_user(
            username=self.du1.username, email=self.du1.email)
        self.user1.is_superuser = True
        self.user1.set_password('pass')
        self.user1.save()
        # Log in user1 by default.
        self.client.login(username=self.user1.username, password='pass')
        self.du2 = mixer.blend(DepartmentUser, username=mixer.RANDOM, photo=None)
        self.user2 = User.objects.create_user(
            username=self.du2.username, email=self.du2.email)
        self.user2.set_password('pass')
        self.user2.save()

        self.itsystem = mixer.blend(ITSystem)

    def test_km_address_book(self):
        """test the km_address_book GET response
        """
        url = reverse('km_address_book')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_km_user_accounts(self):
        """test the km_user_accounts GET response
        """
        url = reverse('km_user_accounts')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
