import logging
from datetime import datetime, timedelta, timezone

import requests
from dateutil.parser import parse
from django.conf import settings
from django.core.management.base import BaseCommand

from itassets.utils import ms_graph_client_token
from organisation.models import DepartmentUser


class Command(BaseCommand):
    help = "Query Entra ID sign-in audit logs and update last_signin property for DepartmentUser records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            action="store",
            default=5,
            type=int,
            help="Query sign-ins for the previous number of minutes (default 5)",
            dest="minutes",
        )
        parser.add_argument(
            "--logging",
            action="store_true",
            dest="logging",
            help="Display verbose logging output",
        )

    def handle(self, *args, **options):
        log = options["logging"]

        if log:
            logger = logging.getLogger("organisation")

        token = ms_graph_client_token()
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
        }
        # Filters: interactive logins, and within the previous n minutes.
        minutes = options["minutes"]
        t = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        ts = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "$orderby": "createdDateTime desc",
            "$filter": f"(isInteractive eq true and createdDateTime ge {ts})",
        }
        # Reference: https://learn.microsoft.com/en-us/graph/api/signin-list
        url = "https://graph.microsoft.com/v1.0/auditLogs/signIns"

        if log:
            logger.info(f"Querying user interactive sign-ins since {ts}")

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        j = resp.json()
        signins = j["value"]

        for signin in signins:
            try:
                du = DepartmentUser.objects.get(azure_guid=signin["userId"])
            except DepartmentUser.DoesNotExist:
                continue

            last_signin = parse(signin["createdDateTime"]).astimezone(settings.TZ)
            if not du.last_signin or last_signin > du.last_signin:
                du.last_signin = last_signin
                du.save()
                if log:
                    logger.info(f"Updated last_signin for {du} to {last_signin}")
