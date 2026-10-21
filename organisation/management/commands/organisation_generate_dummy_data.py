"""Management command to generate dummy data for development purposes. Only runs when DEBUG=True."""

import logging
import random
from datetime import date, timedelta
from uuid import uuid1

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from organisation.models import DIVISION_CHOICES, CostCentre, DepartmentUser, Location

logger = logging.getLogger("organisation")

JOB_TITLES = (
    "Project Officer",
    "Ranger",
    "Data Analyst",
    "Service Desk Officer",
    "Administrative Officer",
    "Scientist",
    "Finance Officer",
    "Communications Officer",
    "Parks Officer",
    "Executive Assistant",
    "Fire Operations Officer",
    "Librarian",
)

DIVISION_NAMES = (
    "AUDIT, INTEGRITY AND RISK BRANCH",
    "BIODIVERSITY AND CONSERVATION SCIENCE",
    "BOTANIC GARDENS AND PARKS",
    "CONSERVATION AND PARKS COMMISSION",
    "PARKS AND VISITOR SERVICES DIVISION",
    "PARKS AND WILDLIFE SERVICE",
    "REGIONAL AND FIRE MANAGEMENT SERVICES",
    "ROTTNEST ISLAND AUTHORITY",
    "STRATEGY AND GOVERNANCE",
    "ZOOLOGICAL PARKS AUTHORITY",
)

BRANCH_NAMES = (
    "BUSINESS SERVICES",
    "REGIONAL OPERATIONS",
    "WILDLIFE MANAGEMENT",
    "VISITOR SERVICES",
    "CORPORATE SUPPORT",
    "POLICY AND PLANNING",
    "FINANCE",
    "PEOPLE AND CULTURE",
)

SUBURBS = (
    "PERTH",
    "KENSINGTON",
    "BENTLEY",
    "CRAWLEY",
    "WANNEROO",
    "ALBANY",
    "BUNBURY",
    "GERALDTON",
    "BROOME",
    "KUNUNURRA",
    "DULLSVILLE",
)

EMP_STATUS = ("PFA", "PFT", "CAS", "CFT", "SEAS", "EXT", "AO")

EMP_STATUS_DESC = {
    "PFA": "PERMANENT FULL-TIME AGREEMENT",
    "PFT": "PERMANENT FULL-TIME",
    "CAS": "CASUAL",
    "CFT": "CONTRACT FULL-TIME",
    "SEAS": "SEASONAL",
    "EXT": "EXITED",
    "AO": "AGENT/EXTERNAL",
}

CHART_ACCT_NAMES = (
    "GENERAL OPERATIONS",
    "PROJECT SUPPORT",
    "REGIONAL PROGRAMS",
    "CORPORATE SERVICES",
    "CAPITAL WORKS",
)


class Command(BaseCommand):
    help = "Generates dummy data (Location, CostCentre, DepartmentUser) for development purposes. Only runs when DEBUG=True; never use in production."

    def add_arguments(self, parser):
        parser.add_argument(
            "--locations",
            action="store",
            type=int,
            default=5,
            dest="locations",
            help="Number of dummy Location records to generate (default 5)",
        )
        parser.add_argument(
            "--cost-centres",
            action="store",
            type=int,
            default=5,
            dest="cost_centres",
            help="Number of dummy CostCentre records to generate (default 5)",
        )
        parser.add_argument(
            "--department-users",
            action="store",
            type=int,
            default=20,
            dest="department_users",
            help="Number of dummy DepartmentUser records to generate (default 20)",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This command generates dummy data and may only be run with DEBUG=True (development use only).")

        for name in ("locations", "cost_centres", "department_users"):
            if options[name] < 0:
                raise CommandError(f"{name} must be a non-negative integer (got {options[name]})")

        logger.info("Generating dummy data for development purposes")

        from mixer.backend.django import mixer

        with transaction.atomic():
            locations = self._generate_locations(mixer, options["locations"])
            cost_centres = self._generate_cost_centres(mixer, options["cost_centres"])
            users = self._generate_department_users(mixer, locations, cost_centres, options["department_users"])
            self._assign_cost_centre_managers(cost_centres, users)

        summary = f"Created {len(locations)} locations, {len(cost_centres)} cost centres and {len(users)} department users (dummy data for development)"
        logger.info(summary)
        self.stdout.write(self.style.SUCCESS(summary))

    def _generate_locations(self, mixer, count):
        locations = []
        for _ in range(count):
            suburb = random.choice(SUBURBS)
            name = f"{random.randint(1, 999)} Fake Street, {suburb}"
            location = mixer.blend(
                Location,
                name=name,
                address=f"{random.randint(1, 999)} Fake Street",
                pobox="",
                phone=f"08 9{random.randint(1000000, 8999999)}",
                fax=None,
                point=Point(115.8600 + random.uniform(-0.5, 0.5), -31.9500 + random.uniform(-0.5, 0.5), srid=4326),
                ascender_code=str(random.randint(1000, 9999)),
                ascender_desc=name,
                active=True,
            )
            locations.append(location)
        return locations

    def _generate_cost_centres(self, mixer, count):
        cost_centres = []
        for _ in range(count):
            code = str(random.randint(10000, 99999))
            cc = mixer.blend(
                CostCentre,
                active=True,
                code=code,
                chart_acct_name=random.choice(CHART_ACCT_NAMES),
                division_name=random.choice(DIVISION_CHOICES)[0],
                manager=None,
                ascender_code=code,
            )
            cost_centres.append(cc)
        return cost_centres

    def _generate_department_users(self, mixer, locations, cost_centres, count):
        employee_ids = random.sample(range(100000, 999999), k=count)
        users = []
        for i in range(count):
            given = mixer.faker.first_name()
            surname = mixer.faker.last_name()
            job_title = random.choice(JOB_TITLES)
            emp_status = random.choice(EMP_STATUS)
            licences = random.choice((["MICROSOFT 365 E5"], ["MICROSOFT 365 F3"], None))
            licence_type = "ONPUL" if "MICROSOFT 365 E5" in (licences or []) else ("CLDUL" if licences else None)
            cc = random.choice(cost_centres) if cost_centres else None
            loc = random.choice(locations) if locations else None
            manager = random.choice(users) if users else None
            ascender_data = {
                "employee_id": str(employee_ids[i]),
                "first_name": given.upper(),
                "second_name": None,
                "surname": surname.upper(),
                "preferred_name": None,
                "occup_pos_title": job_title.upper(),
                "emp_stat_desc": EMP_STATUS_DESC[emp_status],
                "geo_location_desc": (loc.ascender_desc or loc.name) if loc else None,
                "paypoint": cc.code if cc else None,
                "clevel1_id": "BCA",
                "clevel1_desc": "DEPT BIODIVERSITY, CONSERVATION AND ATTRACTIONS",
                "clevel2_desc": random.choice(DIVISION_NAMES),
                "clevel3_desc": random.choice(BRANCH_NAMES),
                "clevel4_desc": "CENTRAL OFFICE",
                "clevel5_desc": None,
                "emp_status": emp_status,
                "position_no": str(random.randint(10000000, 99999999)),
                "job_start_date": (date.today() - timedelta(days=random.randint(30, 1825))).strftime("%Y-%m-%d"),
                "job_end_date": (date.today() + timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d")
                if random.random() < 0.15
                else None,
                "licence_type": licence_type,
                "manager_emp_no": manager.employee_id if manager else None,
                "manager_name": f"{manager.given_name} {manager.surname}".upper() if manager else None,
            }
            user = mixer.blend(
                DepartmentUser,
                active=random.random() > 0.1,
                email=f"{given}.{surname}@dbca.wa.gov.au".lower(),
                name=f"{given} {surname}",
                given_name=given,
                surname=surname,
                preferred_name=None,
                maiden_name=None,
                title=job_title,
                telephone=f"08 9{random.randint(1000000, 8999999)}",
                mobile_phone=f"04{random.randint(10000000, 89999999)}",
                manager=manager,
                cost_centre=cc,
                location=loc,
                proxy_addresses=None,
                assigned_licences=licences,
                update_reference=None,
                account_type=None,
                employee_id=str(employee_ids[i]),
                ascender_data=ascender_data,
                position_no=None,
                ad_guid=uuid1,
                ad_data=None,
                azure_guid=uuid1,
                azure_ad_data=None,
                dir_sync_enabled=None,
                last_signin=(timezone.now() - timedelta(days=random.randint(0, 365))) if random.random() > 0.1 else None,
                assigned_entra_groups=None,
            )
            users.append(user)
        return users

    def _assign_cost_centre_managers(self, cost_centres, users):
        for cc in cost_centres:
            candidates = [u for u in users if u.cost_centre == cc] or users
            if candidates:
                cc.manager = random.choice(candidates)
                cc.save()
