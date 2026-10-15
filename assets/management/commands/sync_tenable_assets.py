import logging

from django.core.management.base import BaseCommand

from assets.tenable_requests import tenable_export_assets, tenable_export_vulns, tenable_export_web_app_vulns

from assets.models import Asset


class Command(BaseCommand):
    help = "Synchronises department assets with Tenable assets"

    def handle(self, *args, **options):
        """
        Retrieves all Tenable assets and uses that to create / update assets.
        """
        logger = logging.getLogger("assets")
        try:
            assets = tenable_export_assets()
            vulns = self.get_asset_vulns()
            count = 0
            total = len(assets)
            logger.info(f"Updating {len(assets)} department assets")
            for asset in assets:
                count += 1
                if self.is_valid_asset(asset):
                    found_asset, created = Asset.objects.get_or_create(tenable_id=asset["id"])
                    found_asset.update_from_tenable_data(tenable_data=asset, vuln_data=vulns.get(found_asset.tenable_id))
                    if created:
                        logger.info(
                            f"[{count}/{total}]: Created asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                        )
                    else:
                        logger.info(
                            f"[{count}/{total}]: Updated asset {found_asset.pk} - {found_asset.name or ''} | Vulns [{len(found_asset.get_vulns())}]"
                        )
            logger.info(f"Successfully processed {len(assets)} department assets")
        except Exception as exc:
            logger.warning("Failed to sync Tenable assets", exc_info=exc)

    def is_valid_asset(self, asset):
        # Temp rules for the asset mvp - should be changed later
        # Rules to be valid:
        # - Must have a device tag or be marked as a web app
        # - Any device tags must not have "user device", "new device", or "Edge Firewall"

        valid = None
        filtered_devices = ["User Device", "New Device", "Edge Firewall"]
        if "webapp" in asset.get("types"):
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

    def get_asset_vulns(self) -> dict:
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
