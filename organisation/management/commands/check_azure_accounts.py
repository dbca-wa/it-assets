import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import CostCentre, DepartmentUser, Location
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = "Checks licensed user accounts from Entra ID and updates linked DepartmentUser objects"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Querying Microsoft Graph API for Entra ID user accounts")
        # Optionally run this management command in the context of a Sentry cron monitor.
        if settings.SENTRY_CRON_CHECK_AZURE:
            with monitor(monitor_slug=settings.SENTRY_CRON_CHECK_AZURE):
                logger.info(f"Applying Sentry Cron Monitor: {settings.SENTRY_CRON_CHECK_AZURE}")
                self.check_azure_accounts(logger)
        else:
            self.check_azure_accounts(logger)

        logger.info("Completed")

    def check_azure_accounts(self, logger):
        """Separate the body of this management command to allow running it in context with
        the Sentry monitor process.
        """
        azure_users = ms_graph_users()

        if not azure_users:
            logger.error("Microsoft Graph API returned no data")
            return

        logger.info("Comparing Department Users to Entra ID user accounts")

        # Initially, check for any invalid Entra ID GUID values that are cached.
        logger.info("Checking cached Entra ID GUID values for validity")
        valid_azure_guids = [i["objectId"] for i in azure_users]
        cached_azure_guids = DepartmentUser.objects.filter(azure_guid__isnull=False).values_list("azure_guid", flat=True)
        for guid in cached_azure_guids:
            if guid not in valid_azure_guids:
                du = DepartmentUser.objects.get(azure_guid=guid)
                du.azure_guid = None
                du.save()
                logger.info(f"Removed invalid Entra ID GUID {guid} from department user {du}")

        logger.info("Checking Entra ID accounts against DepartmentUser records")
        licences = set([MS_PRODUCTS["MICROSOFT 365 E5"], MS_PRODUCTS["MICROSOFT 365 F3"]])
        for az in azure_users:
            try:
                # No existing DepartmentUser is linked to this Entra ID user.
                if not DepartmentUser.objects.filter(azure_guid=az["objectId"]).exists():
                    # EDGE CASE 1: a department user with matching email may already exist with a different azure_guid.
                    # This should be cleaned up by the 'invalid GUID' check above in most cases.
                    # We'll need to correct this issue manually. Email a warning to admins and skip the account.
                    if (
                        az["userPrincipalName"]
                        and DepartmentUser.objects.filter(email=az["userPrincipalName"], azure_guid__isnull=False).exists()
                    ):
                        existing_user = DepartmentUser.objects.filter(email=az["userPrincipalName"]).first()
                        message = f"Skipped {az['userPrincipalName']} ({az['objectId']}): email exists and is already associated with Entra ID {existing_user.azure_guid}"
                        logger.warning(message)
                        mail.send_mail(
                            subject=f"ENTRA ID SYNC: DepartmentUser with duplicate email while syncing Entra ID account {az['objectId']}",
                            message=message,
                            from_email=settings.NOREPLY_EMAIL,
                            recipient_list=settings.ADMIN_EMAILS,
                            fail_silently=True,
                        )
                        continue

                    # EDGE CASE 2: a department user with matching employee ID may already exist with a different azure_guid.
                    # We'll need to correct this issue manually. Email a warning to admins and skip the account.
                    if az["employeeId"] and DepartmentUser.objects.filter(employee_id=az["employeeId"], azure_guid__isnull=True).exists():
                        existing_user = DepartmentUser.objects.filter(employee_id=az["employeeId"]).first()
                        message = f"Skipped {az['userPrincipalName']} ({az['objectId']}): employeeId exists and is already associated with {existing_user}"
                        logger.warning(message)
                        mail.send_mail(
                            subject=f"ENTRA ID SYNC: DepartmentUser with duplicate employee_id while syncing Entra ID account {az['objectId']}",
                            message=message,
                            from_email=settings.NOREPLY_EMAIL,
                            recipient_list=settings.ADMIN_EMAILS,
                            fail_silently=True,
                        )
                        continue

                    # A department user with matching email may already exist in IT Assets with no azure_guid.
                    # If so, associate the Entra ID objectId with that user record.
                    if DepartmentUser.objects.filter(email=az["userPrincipalName"], azure_guid__isnull=True).exists():
                        existing_user = DepartmentUser.objects.get(email=az["userPrincipalName"])
                        existing_user.azure_guid = az["objectId"]
                        existing_user.azure_ad_data = az
                        existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                        existing_user.update_from_entra_id_data()  # This method calls save()
                        logger.info(f"Linked existing user {existing_user.email} with Azure objectId {az['objectId']}")
                        continue  # Skip to the next Azure user.

                    # Only create a new DepartmentUser instance if the Entra ID account has an E5 or F3 licence assigned.
                    if az["assignedLicenses"] and not licences.isdisjoint(az["assignedLicenses"]):
                        if az["companyName"] and CostCentre.objects.filter(code=az["companyName"]).exists():
                            cost_centre = CostCentre.objects.get(code=az["companyName"])
                        else:
                            cost_centre = None

                        if az["officeLocation"] and Location.objects.filter(name=az["officeLocation"]).exists():
                            location = Location.objects.get(name=az["officeLocation"])
                        else:
                            location = None

                        new_user = DepartmentUser.objects.create(
                            azure_guid=az["objectId"],
                            azure_ad_data=az,
                            azure_ad_data_updated=datetime.now(timezone.utc),
                            active=az["accountEnabled"],
                            email=az["userPrincipalName"],
                            name=az["displayName"],
                            given_name=az["givenName"],
                            surname=az["surname"],
                            title=az["jobTitle"],
                            telephone=az["telephoneNumber"],
                            mobile_phone=az["mobilePhone"],
                            employee_id=az["employeeId"],
                            cost_centre=cost_centre,
                            location=location,
                            dir_sync_enabled=az["onPremisesSyncEnabled"],
                        )
                        new_user.update_from_entra_id_data()
                        logger.info(f"Created new department user {new_user}")
                # An existing DepartmentUser is linked to this Entra ID user - cache the Azure data on it.
                elif DepartmentUser.objects.filter(azure_guid=az["objectId"]).exists():
                    # Update the existing DepartmentUser object fields with values from Azure.
                    existing_user = DepartmentUser.objects.get(azure_guid=az["objectId"])
                    existing_user.azure_ad_data = az
                    existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                    existing_user.update_from_entra_id_data()  # This method calls save()
            except Exception as e:
                # In the event of an exception, fail gracefully and alert the admins.
                subject = f"ENTRA ID SYNC: exception during sync of Entra ID account {az['objectId']}"
                logger.exception(subject)
                message = f"Azure data:\n{json.dumps(az, indent=2)}\nException:\n{str(e)}\n"
                html_message = f"<p>Azure data:</p><p>{json.dumps(az, indent=2)}</p><p>Exception:</p><p>{str(e)}\n</p>"
                mail.send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.NOREPLY_EMAIL,
                    recipient_list=settings.ADMIN_EMAILS,
                    html_message=html_message,
                    fail_silently=True,
                )
