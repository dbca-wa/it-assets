from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from mixer.backend.django import mixer

from organisation.models import DepartmentUser

User = get_user_model()


class DepartmentUserAdminTestCase(TestCase):

    def setUp(self):
        super(DepartmentUserAdminTestCase, self).setUp()
        # Create & log in an admin user.
        self.admin_user = mixer.blend(User, username='admin', is_superuser=True, is_staff=True)
        self.admin_user.set_password('pass')
        self.admin_user.save()
        self.client.login(username='admin', password='pass')
        mixer.cycle(5).blend(DepartmentUser)

    def test_departmentuser_export(self):
        """Test the DepartmentUserExport admin view
        """
        url = reverse('admin:departmentuser_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header("Content-Disposition"))
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
