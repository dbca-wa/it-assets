from io import BytesIO

from mixer.backend.django import mixer

from itassets.test_api import ApiTestCase
from organisation.models import AscenderActionLog, DepartmentUser
from organisation.reports import department_user_export, user_account_export, user_changes_export


class ReportsTestCase(ApiTestCase):
    def test_department_user_export(self):
        report = department_user_export(BytesIO(), DepartmentUser.objects.all())
        self.assertTrue(report.getbuffer().nbytes > 0)

    def test_user_account_export(self):
        report = user_account_export(BytesIO(), DepartmentUser.objects.all())
        self.assertTrue(report.getbuffer().nbytes > 0)

    def test_user_changes_export(self):
        # Generate some logs.
        mixer.cycle(2).blend(AscenderActionLog, level="INFO", log=f"{self.user_permanent.email} {mixer.faker.text()}")
        report = user_changes_export(BytesIO(), AscenderActionLog.objects.all())
        self.assertTrue(report.getbuffer().nbytes > 0)
