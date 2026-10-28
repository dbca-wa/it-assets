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

    logger = logging.getLogger("assets")

    def handle(self, *args, **options):
        """
        Syncs asset and vulnerability data to tenable.
        Prunes vulnerabilities older than the VULN_LAST_SEEN_LIMIT
        """
        try:
            # Prune aged-out vulns
            self.prune_aged_out_vulns()
            # Retrieve assets
            assets = tenable_export_assets()
            # Retrieve vulns
            vulns = self.get_vulns_per_asset()
            # Update asset and vuln database
            self.update_assets_and_vulns(assets, vulns)
        

        except Exception as exc:
            self.logger.warning("Failed to sync Tenable assets", exc_info=exc)
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

    def update_assets_and_vulns(self, assets: list[Asset], vulns: list[dict[str,Vulnerability]]):
        """
        Loads all assets and vulnerabilities into the database, updating existing records and creating new ones where applicable.
        Separated into it's own method for easier testing.
        """
        # Init stats for logging
        count = 0
        assets_created = 0
        assets_updated = 0
        assets_skipped = 0
        total = len(assets)

        # Process assets
        self.logger.info(f"Processing {total} found assets")
        for asset in assets:
            count += 1
            # If it's a valid asset, add or update it the asset and any associated vulns
            if self.passes_filter(asset):
                found_asset, created = Asset.objects.get_or_create(tenable_id=asset["id"])
                found_asset.update_from_raw_data(tenable_data=asset, vuln_data=vulns.get(found_asset.tenable_id, []))
                if created:
                    self.logger.info(
                        f"[{count}/{total}]: CREATED asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                    )
                    assets_created += 1
                else:
                    self.logger.info(
                        f"[{count}/{total}]: UPDATED asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                    )
                    assets_updated += 1
            else:
                assets_skipped += 1

        self.logger.info(f"Successfully processed {total} department assets")
        self.logger.info(f"{assets_updated} UPDATED | {assets_created} CREATED | {assets_skipped} SKIPPED")
            


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

    def get_vulns_per_asset(self) -> list[dict[str,Vulnerability]]:
        """
        Retrieves vulnerabilities for each asset, returning a the dict of vuln lists per asset uuid {tenable_uuid <str> : [{vuln},]}
        """
        vuln_store = {}
        try:
            # Retrieve vulnerabilities from the standard asset vuln export and the web app vuln export
            vulns = tenable_export_vulns() + tenable_export_web_app_vulns()
            self.logger.info(f"Updating {len(vulns)} asset vulns")
            for vuln in vulns:
                # Assign vulns to an asset
                if "uuid" in vuln["asset"]:
                    if vuln_store.get(vuln["asset"]["uuid"]):
                        vuln_store[vuln["asset"]["uuid"]].append(vuln)
                    else:
                        vuln_store[vuln["asset"]["uuid"]] = [vuln]
        except Exception as exc:
            self.logger.warning("Failed to sync Tenable vulns", exc_info=exc)

        return vuln_store

    def prune_aged_out_vulns(self):
        """
        Deletes any vulnerabilities in the database older than VULN_LAST_SEEN_LIMIT in days
        This function was separated out for ease of testing
        """
        age_limit = settings.VULN_LAST_SEEN_LIMIT
        self.logger.info(f"Pruning vulns older than {age_limit} days")
        aged_out_vulns = Vulnerability.objects.filter(last_found__lte=now() - timedelta(days=age_limit))
        deleted = len(aged_out_vulns)
        if aged_out_vulns.exists():
            aged_out_vulns.delete()
            self.logger.info(f"Pruned {deleted} vulns")
        else:
            self.logger.info("No vulns pruned")
