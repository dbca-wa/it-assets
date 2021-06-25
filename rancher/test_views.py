from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from mixer.backend.django import mixer

from rancher.models import Cluster, Workload

User = get_user_model()


class RancherViewsTestCase(TestCase):
    client = Client()

    def setUp(self):
        # Create/log in a normal user.
        self.n_user = mixer.blend(User, username='normaluser', is_superuser=False, is_staff=False)
        self.n_user.set_password('pass')
        self.n_user.save()
        self.client.login(username='normaluser', password='pass')
        # Mixer throws an exception on generation of a Workload instance:
        # type object 'JSONField' has no attribute '_meta'
        #self.workload = mixer.blend(Workload, latest_containers=[1])
        self.cluster = Cluster.objects.create(
            name='test-cluster',
        )
        self.workload = Workload.objects.create(
            cluster=self.cluster,
            name='test-workload',
            kind='test',
            image='test-image',
            api_version='1',
            modified=datetime.now(timezone.utc),
            created=datetime.now(timezone.utc),
        )

    def test_workload_detail(self):
        url = reverse('workload_detail', kwargs={'pk': self.workload.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
