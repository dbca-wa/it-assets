# Generated by Django 4.2.10 on 2024-02-23 02:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("organisation", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ITSystem",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_created", models.DateTimeField(auto_now_add=True)),
                ("date_updated", models.DateTimeField(auto_now=True)),
                (
                    "system_id",
                    models.CharField(
                        max_length=16, unique=True, verbose_name="system ID"
                    ),
                ),
                ("name", models.CharField(max_length=128, unique=True)),
                ("acronym", models.CharField(blank=True, max_length=16, null=True)),
                (
                    "status",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Production"),
                            (1, "Development"),
                            (2, "Production (Legacy)"),
                            (3, "Decommissioned"),
                            (4, "Unknown"),
                        ],
                        default=4,
                    ),
                ),
                (
                    "link",
                    models.CharField(
                        blank=True,
                        help_text="URL to web application",
                        max_length=2048,
                        null=True,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "documentation",
                    models.CharField(
                        blank=True,
                        help_text="A link/URL to end-user documentation",
                        max_length=2048,
                        null=True,
                    ),
                ),
                (
                    "technical_documentation",
                    models.CharField(
                        blank=True,
                        help_text="A link/URL to technical documentation",
                        max_length=2048,
                        null=True,
                    ),
                ),
                (
                    "status_url",
                    models.URLField(
                        blank=True,
                        help_text="URL to status/uptime info",
                        max_length=2048,
                        null=True,
                        verbose_name="status URL",
                    ),
                ),
                (
                    "availability",
                    models.PositiveIntegerField(
                        blank=True,
                        choices=[(1, "24/7/365"), (2, "Business hours")],
                        help_text="Expected availability for this system",
                        null=True,
                    ),
                ),
                (
                    "application_server",
                    models.TextField(
                        blank=True,
                        help_text="Application server(s) that host this system",
                    ),
                ),
                (
                    "database_server",
                    models.TextField(
                        blank=True,
                        help_text="Database server(s) that host this system's data",
                    ),
                ),
                (
                    "network_storage",
                    models.TextField(
                        blank=True,
                        help_text="Network storage location(s) used by this system",
                    ),
                ),
                (
                    "backups",
                    models.PositiveIntegerField(
                        blank=True,
                        choices=[
                            (1, "Point in time database with daily local"),
                            (2, "Daily local"),
                            (3, "Vendor-managed"),
                        ],
                        help_text="Data backup arrangements for this system",
                        null=True,
                    ),
                ),
                (
                    "system_reqs",
                    models.TextField(
                        blank=True,
                        help_text="A written description of the requirements to use the system (e.g. web browser version)",
                        verbose_name="system requirements",
                    ),
                ),
                (
                    "recovery_category",
                    models.PositiveIntegerField(
                        blank=True,
                        choices=[
                            (1, "MTD: 1+ week; RTO: 5+ days"),
                            (2, "MTD: 72 hours; RTO: 48 hours"),
                            (3, "MTD: 8 hours; RTO: 4 hours"),
                        ],
                        help_text="The recovery requirements for this system",
                        null=True,
                    ),
                ),
                (
                    "seasonality",
                    models.PositiveIntegerField(
                        blank=True,
                        choices=[
                            (1, "Bushfire season"),
                            (2, "End of financial year"),
                            (3, "Annual reporting"),
                            (4, "School holidays"),
                            (5, "Default"),
                        ],
                        help_text="Season/period when this system is most important",
                        null=True,
                    ),
                ),
                (
                    "user_notification",
                    models.EmailField(
                        blank=True,
                        help_text="Users (group email address) to be advised of any changes (outage or upgrade) to the system",
                        max_length=254,
                        null=True,
                    ),
                ),
                (
                    "emergency_operations",
                    models.BooleanField(
                        default=False,
                        help_text="System is used for emergency operations",
                    ),
                ),
                (
                    "online_bookings",
                    models.BooleanField(
                        default=False, help_text="System is used for online bookings"
                    ),
                ),
                (
                    "visitor_safety",
                    models.BooleanField(
                        default=False, help_text="System is used for visitor safety"
                    ),
                ),
                (
                    "authentication",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Domain/application Credentials"),
                            (2, "Single Sign On"),
                            (3, "Externally Managed"),
                        ],
                        default=1,
                        help_text="The method by which users authenticate themselve to the system.",
                        null=True,
                    ),
                ),
                (
                    "access",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Public Internet"),
                            (2, "Authenticated Extranet"),
                            (3, "Corporate Network"),
                            (4, "Local System (Networked)"),
                            (5, "Local System (Standalone)"),
                        ],
                        default=3,
                        help_text="The network upon which this system is accessible.",
                        null=True,
                    ),
                ),
                (
                    "application_type",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Web application"),
                            (2, "Client application"),
                            (3, "Mobile application"),
                            (5, "Externally hosted application"),
                            (4, "Service"),
                            (6, "Platform"),
                            (7, "Infrastructure"),
                        ],
                        null=True,
                    ),
                ),
                (
                    "system_type",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Department commercial services"),
                            (2, "Department fire services"),
                            (3, "Department visitor services"),
                        ],
                        null=True,
                    ),
                ),
                (
                    "oim_internal_only",
                    models.BooleanField(
                        default=False,
                        help_text="For OIM use only",
                        verbose_name="OIM internal only",
                    ),
                ),
                (
                    "biller_code",
                    models.CharField(
                        blank=True,
                        help_text="BPAY biller code for this system (must be unique).",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "retention_reference_no",
                    models.CharField(
                        blank=True,
                        help_text="Retention/disposal reference no. in the current retention and disposal schedule",
                        max_length=256,
                        null=True,
                    ),
                ),
                (
                    "defunct_date",
                    models.DateField(
                        blank=True,
                        help_text="Date on which the IT System first becomes a production (legacy) or decommissioned system",
                        null=True,
                    ),
                ),
                (
                    "disposal_action",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Retain in agency"),
                            (2, "Required as State Archive"),
                            (3, "Destroy"),
                        ],
                        help_text="Final disposal action required once the custody period has expired",
                        null=True,
                        verbose_name="Disposal action",
                    ),
                ),
                (
                    "custody",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "Migrate records and maintain for the life of agency"),
                            (
                                2,
                                "Retain in agency, migrate records to new database or transfer to SRO when superseded",
                            ),
                            (
                                3,
                                "Destroy datasets when superseded, migrate records and maintain for life of agency",
                            ),
                            (
                                4,
                                "Retain 12 months after data migration and decommission (may retain for reference)",
                            ),
                        ],
                        help_text="Period the records will be retained before they are archived or destroyed",
                        null=True,
                    ),
                ),
                (
                    "retention_comments",
                    models.TextField(
                        blank=True,
                        help_text="Comments/notes related to retention and disposal",
                        null=True,
                        verbose_name="comments",
                    ),
                ),
                (
                    "infrastructure_location",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "On premises"),
                            (2, "Azure cloud"),
                            (3, "AWS cloud"),
                            (4, "Other provider cloud"),
                        ],
                        help_text="The primary location of the infrastructure on which this system runs",
                        null=True,
                    ),
                ),
                ("extra_data", models.JSONField(blank=True, null=True)),
                (
                    "ah_support",
                    models.ForeignKey(
                        blank=True,
                        help_text="After-hours support contact",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ah_support",
                        to="organisation.departmentuser",
                        verbose_name="after hours support",
                    ),
                ),
                (
                    "bh_support",
                    models.ForeignKey(
                        blank=True,
                        help_text="Business hours support contact",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bh_support",
                        to="organisation.departmentuser",
                        verbose_name="business hours support",
                    ),
                ),
                (
                    "cost_centre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organisation.costcentre",
                    ),
                ),
                (
                    "information_custodian",
                    models.ForeignKey(
                        blank=True,
                        help_text="Information custodian",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="systems_info_custodianed",
                        to="organisation.departmentuser",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        help_text="IT system owner",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="systems_owned",
                        to="organisation.departmentuser",
                        verbose_name="system owner",
                    ),
                ),
                (
                    "technology_custodian",
                    models.ForeignKey(
                        blank=True,
                        help_text="Technology custodian",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="systems_tech_custodianed",
                        to="organisation.departmentuser",
                    ),
                ),
            ],
            options={
                "verbose_name": "IT System",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ITSystemUserGroup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=2048, unique=True)),
                ("user_count", models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="StandardChange",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=256)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "implementation",
                    models.TextField(
                        blank=True,
                        help_text="Implementation/deployment instructions",
                        null=True,
                    ),
                ),
                (
                    "implementation_docs",
                    models.FileField(
                        blank=True,
                        help_text="Implementation/deployment instructions (attachment)",
                        null=True,
                        upload_to="uploads/%Y/%m/%d",
                    ),
                ),
                ("expiry", models.DateField(blank=True, null=True)),
                (
                    "endorser",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organisation.departmentuser",
                    ),
                ),
                (
                    "it_systems",
                    models.ManyToManyField(
                        blank=True,
                        help_text="IT System(s) affected by the standard change",
                        to="registers.itsystem",
                        verbose_name="IT Systems",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="itsystem",
            name="user_groups",
            field=models.ManyToManyField(
                blank=True,
                help_text="User group(s) that use this system",
                to="registers.itsystemusergroup",
            ),
        ),
        migrations.CreateModel(
            name="ChangeRequest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "title",
                    models.CharField(
                        help_text="A short summary title for this change",
                        max_length=255,
                    ),
                ),
                (
                    "change_type",
                    models.SmallIntegerField(
                        choices=[(0, "Normal"), (1, "Standard"), (2, "Emergency")],
                        db_index=True,
                        default=0,
                        help_text="The change type",
                    ),
                ),
                (
                    "status",
                    models.SmallIntegerField(
                        choices=[
                            (0, "Draft"),
                            (1, "Submitted for endorsement"),
                            (7, "Ready for SME review"),
                            (2, "Scheduled for CAB"),
                            (3, "Ready for implementation"),
                            (4, "Complete"),
                            (5, "Rolled back"),
                            (6, "Cancelled"),
                        ],
                        db_index=True,
                        default=0,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="A brief description of what the change is for and why it is being undertaken",
                        null=True,
                    ),
                ),
                (
                    "incident_url",
                    models.URLField(
                        blank=True,
                        help_text="If the change is to address an incident, URL to the incident details",
                        max_length=2048,
                        null=True,
                        verbose_name="Incident URL",
                    ),
                ),
                (
                    "test_date",
                    models.DateField(
                        blank=True,
                        help_text="Date on which the change was tested",
                        null=True,
                    ),
                ),
                (
                    "test_result_docs",
                    models.FileField(
                        blank=True,
                        help_text="Test results record (attachment)",
                        null=True,
                        upload_to="uploads/%Y/%m/%d",
                    ),
                ),
                (
                    "planned_start",
                    models.DateTimeField(
                        blank=True,
                        help_text="Time that the change is planned to begin",
                        null=True,
                    ),
                ),
                (
                    "planned_end",
                    models.DateTimeField(
                        blank=True,
                        help_text="Time that the change is planned to end",
                        null=True,
                    ),
                ),
                (
                    "completed",
                    models.DateTimeField(
                        blank=True,
                        help_text="Time that the change was completed",
                        null=True,
                    ),
                ),
                (
                    "implementation",
                    models.TextField(
                        blank=True,
                        help_text="Implementation/deployment instructions",
                        null=True,
                    ),
                ),
                (
                    "implementation_docs",
                    models.FileField(
                        blank=True,
                        help_text="Implementation/deployment instructions (attachment)",
                        null=True,
                        upload_to="uploads/%Y/%m/%d",
                    ),
                ),
                (
                    "outage",
                    models.DurationField(
                        blank=True,
                        help_text="Duration of outage required to complete the change (hh:mm:ss).",
                        null=True,
                    ),
                ),
                (
                    "communication",
                    models.TextField(
                        blank=True,
                        help_text="Description of all communications to be undertaken",
                        null=True,
                    ),
                ),
                (
                    "broadcast",
                    models.FileField(
                        blank=True,
                        help_text="The broadcast text to be emailed to users regarding this change",
                        null=True,
                        upload_to="uploads/%Y/%m/%d",
                    ),
                ),
                (
                    "unexpected_issues",
                    models.BooleanField(
                        default=False,
                        help_text="Unexpected/unplanned issues were encountered during the change",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Details of any unexpected issues, observations, etc.",
                        null=True,
                    ),
                ),
                (
                    "reference_url",
                    models.URLField(
                        blank=True,
                        help_text="URL to external reference (discusssion, records, etc.)",
                        max_length=2048,
                        null=True,
                        verbose_name="reference URL",
                    ),
                ),
                (
                    "post_complete_email_date",
                    models.DateField(
                        blank=True,
                        help_text="Date on which the implementer was emailed about completion",
                        null=True,
                    ),
                ),
                (
                    "initiative_name",
                    models.CharField(
                        blank=True,
                        help_text="Tactical roadmap initiative name",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "initiative_no",
                    models.CharField(
                        blank=True,
                        help_text="Tactical roadmap initiative number",
                        max_length=255,
                        null=True,
                        verbose_name="initiative no.",
                    ),
                ),
                (
                    "project_no",
                    models.CharField(
                        blank=True,
                        help_text="Project number (if applicable)",
                        max_length=255,
                        null=True,
                        verbose_name="project no.",
                    ),
                ),
                (
                    "endorser",
                    models.ForeignKey(
                        blank=True,
                        help_text="The person who will endorse this change prior to CAB",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="endorser",
                        to="organisation.departmentuser",
                    ),
                ),
                (
                    "implementer",
                    models.ForeignKey(
                        blank=True,
                        help_text="The person who will implement this change",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="implementer",
                        to="organisation.departmentuser",
                    ),
                ),
                (
                    "it_systems",
                    models.ManyToManyField(
                        blank=True,
                        help_text="IT System(s) affected by the change",
                        to="registers.itsystem",
                        verbose_name="IT Systems",
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        blank=True,
                        help_text="The person who is requesting this change",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requester",
                        to="organisation.departmentuser",
                    ),
                ),
                (
                    "sme",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional subject matter expert for this change",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sme",
                        to="organisation.departmentuser",
                        verbose_name="subject matter expert",
                    ),
                ),
                (
                    "standard_change",
                    models.ForeignKey(
                        blank=True,
                        help_text="Standard change reference (if applicable)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="registers.standardchange",
                    ),
                ),
            ],
            options={
                "ordering": ("-planned_start",),
            },
        ),
        migrations.CreateModel(
            name="ChangeLog",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("log", models.TextField()),
                (
                    "change_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="registers.changerequest",
                    ),
                ),
            ],
            options={
                "ordering": ("created",),
            },
        ),
    ]
