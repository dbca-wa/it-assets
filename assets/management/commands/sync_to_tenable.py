import logging
from datetime import timedelta
from django.utils.timezone import localtime as now

from django.core.management.base import BaseCommand

from assets.tenable_requests import tenable_export_assets, tenable_export_vulns, tenable_export_web_app_vulns
from assets.models import Asset, Vulnerability

from django.conf import settings
# from django.core import mail



class Command(BaseCommand):
    help = "Synchronises department assets and vulns with Tenable"

    def handle(self, *args, **options):
        """
        Syncs asset and vulnerability data to tenable.
        Prunes vulnerabilities older than the VULN_LAST_SEEN_LIMIT
        """
        logger = logging.getLogger("assets")
        try:
            # Prune aged-out vulns
            age_limit = settings.VULN_LAST_SEEN_LIMIT
            logger.info(f"Pruning vulns older than {age_limit} days")
            aged_out_vulns = Vulnerability.objects.filter(last_found__lte=now()-timedelta(days=age_limit))
            deleted = len(aged_out_vulns)
            if aged_out_vulns.exists():
                aged_out_vulns.delete()
                logger.info(f"Pruned {deleted} vulns")
            else:
                logger.info(f"No vulns pruned")


            # Retrieve assets and all vulnerabilities
            assets = tenable_export_assets()
            vulns = self.get_vulns_per_asset()

            # Init stats for logging
            count = 0
            assets_created = 0
            assets_updated = 0
            assets_skipped = 0
            total = len(assets)

            #Process assets
            logger.info(f"Processing {total} found assets")
            for asset in assets:
                count += 1
                # If it's a valid asset, add or update it the asset and any associated vulns
                if self.passes_filter(asset):
                    found_asset, created = Asset.objects.get_or_create(tenable_id=asset["id"])
                    found_asset.update_from_raw_data(tenable_data=asset, vuln_data=vulns.get(found_asset.tenable_id,[]))
                    if created:
                        logger.info(
                            f"[{count}/{total}]: CREATED asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                        )
                        assets_created += 1
                    else:
                        logger.info(
                            f"[{count}/{total}]: UPDATED asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                        )
                        assets_updated += 1
                else:
                    assets_skipped += 1
            logger.info(f"Successfully processed {total} department assets")
            logger.info(f"{assets_updated} UPDATED | {assets_created} CREATED | {assets_skipped} SKIPPED")

        except Exception as exc:
            logger.warning("Failed to sync Tenable assets", exc_info=exc)
            raise exc
            # # In the event of an exception, fail gracefully and alert the admins.
            # subject = f"TENABLE SYNC: exception during the tenable sync process"
            # logger.exception(subject)
            # message = f"Exception:\n{str(exc)}\n"
            # html_message = f"<p>Exception:</p><p>{str(exc)}\n</p>"
            # mail.send_mail(
            #     subject=subject,
            #     message=message,
            #     from_email=settings.NOREPLY_EMAIL,
            #     recipient_list=settings.ADMIN_EMAILS,
            #     html_message=html_message,
            #     fail_silently=True,
            # )

    def passes_filter(self, asset: dict) -> bool:
        """
        Checks if the asset passes an arbitrary filter set by business rules.
        Current applied business rules:
            - The asset must have a device tag, or be collected via web app scan
            - If the asset has a device tag, it must not be a user device, new device, or edge firewall
        """

        valid = None
        filtered_devices = ["User Device", "New Device", "Edge Firewall"]
        if "webapp" in str(asset.get("types")):
            valid = True
        else:
            # Gets all valid device tag values
            device_tags = [t["value"] for t in asset["tags"] if t["key"] == "Devices"] if "tags" in asset else []
            if len(device_tags) > 0:
                invalid_device_tags = [t for t in device_tags if t in filtered_devices]
                if len(invalid_device_tags) < 1:
                    valid = True
                else:
                    valid = False
            else:
                valid = False
        return valid

    def get_vulns_per_asset(self) -> dict:
        """
        Retrieves vulnerabilities for each asset, returning a the dict of vuln lists per asset uuid {tenable_uuid <str> : [{vuln},]}
        """
        logger = logging.getLogger("assets")
        vuln_store = {}
        try:
            vulns = tenable_export_vulns() + tenable_export_web_app_vulns()
            logger.info(f"Updating {len(vulns)} asset vulns")
            for vuln in vulns:
                if "uuid" in vuln["asset"]:
                    if vuln_store.get(vuln["asset"]["uuid"]):
                        vuln_store[vuln["asset"]["uuid"]].append(vuln)
                    else:
                        vuln_store[vuln["asset"]["uuid"]] = [vuln]
        except Exception as exc:
            logger.warning("Failed to sync Tenable vulns", exc_info=exc)

        return vuln_store
