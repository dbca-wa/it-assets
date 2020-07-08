from datetime import date, datetime, timedelta
from django.conf import settings
from django.conf.urls import url
from django.contrib.admin import register, ModelAdmin
from django.http import HttpResponse
import pytz
import xlsxwriter

from .models import Computer, Mobile, EC2Instance, FreshdeskTicket, LicensingRule

@register(LicensingRule)
class LicensingRule(ModelAdmin):
    list_display = ('product_name', 'publisher_name', 'regex', 'license')
    ordering = ('publisher_name', 'product_name') 

@register(Computer)
class ComputerAdmin(ModelAdmin):
    fieldsets = (
        (
            "Details",
            {
                "fields": (
                    "hostname",
                    "sam_account_name",
                    "domain_bound",
                    "ad_guid",
                    "ad_dn",
                    "os_name",
                    "os_version",
                    "os_service_pack",
                    "os_arch",
                    "ec2_instance",
                    "manufacturer",
                    "model",
                    "chassis",
                    "serial_number",
                )
            },
        ),
        ("Management", {"fields": ("probable_owner", "last_login", "last_ad_login_username", "managed_by", "location", "cost_centre")}),
        ("Scan data", {"fields": ("date_pdq_updated", "date_pdq_last_seen", "date_ad_created", "date_ad_updated")}),
    )
    list_display = [
        "hostname",
        "managed_by",
        "probable_owner",
        "os_name",
        "ec2_instance",
    ]
    raw_id_fields = (
        "org_unit",
        "cost_centre",
        "probable_owner",
        "managed_by",
        "location",
    )
    readonly_fields = ("date_pdq_updated", "date_ad_updated", "date_ad_created", "date_pdq_last_seen", "last_ad_login_username")
    search_fields = ["sam_account_name", "hostname"]


@register(Mobile)
class MobileAdmin(ModelAdmin):
    list_display = ("identity", "model", "imei", "serial_number", "registered_to")
    search_fields = ("identity", "model", "imei", "serial_number")




@register(EC2Instance)
class EC2InstanceAdmin(ModelAdmin):
    list_display = (
        "name",
        "ec2id",
        "launch_time",
        "running",
        "next_state",
        "agent_version",
        "aws_tag_values",
    )
    search_fields = ("name", "ec2id", "launch_time")
    readonly_fields = ["extra_data_pretty", "extra_data", "agent_version"]

    def aws_tag_values(self, obj):
        return obj.aws_tag_values()

    aws_tag_values.short_description = "AWS tag values"


@register(FreshdeskTicket)
class FreshdeskTicketAdmin(ModelAdmin):
    date_hierarchy = "created_at"
    list_display = (
        "ticket_id",
        "created_at",
        "freshdesk_requester",
        "subject",
        "source_display",
        "status_display",
        "priority_display",
        "type",
    )
    fields = (
        "ticket_id",
        "created_at",
        "freshdesk_requester",
        "subject",
        "source_display",
        "status_display",
        "priority_display",
        "type",
        "due_by",
        "description_text",
    )
    readonly_fields = (
        "attachments",
        "cc_emails",
        "created_at",
        "custom_fields",
        "deleted",
        "description",
        "description_text",
        "due_by",
        "email",
        "fr_due_by",
        "fr_escalated",
        "fwd_emails",
        "group_id",
        "is_escalated",
        "name",
        "phone",
        "priority",
        "reply_cc_emails",
        "requester_id",
        "responder_id",
        "source",
        "spam",
        "status",
        "subject",
        "tags",
        "ticket_id",
        "to_emails",
        "type",
        "updated_at",
        "freshdesk_requester",
        "freshdesk_responder",
        "du_requester",
        "du_responder",
        # Callables below.
        "source_display",
        "status_display",
        "priority_display",
    )
    search_fields = (
        "ticket_id",
        "subject",
        "description_text",
        "freshdesk_requester__name",
        "freshdesk_requester__email",
    )
    # Override the default reversion/change_list.html template:
    change_list_template = "admin/tracking/freshdeskticket/change_list.html"

    def source_display(self, obj):
        return obj.get_source_display()

    source_display.short_description = "Source"

    def status_display(self, obj):
        return obj.get_status_display()

    status_display.short_description = "Status"

    def priority_display(self, obj):
        return obj.get_priority_display()

    priority_display.short_description = "Priority"

    def get_urls(self):
        urls = super(FreshdeskTicketAdmin, self).get_urls()
        extra_urls = [
            url(
                r"^report/$",
                self.admin_site.admin_view(self.report),
                name="freshdeskticket_export_stale",
            )
        ]
        return extra_urls + urls

    def report(self, request):
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response[
            "Content-Disposition"
        ] = "attachment; filename=freshdesk_tickets_stale_{}.xlsx".format(
            date.today().isoformat()
        )
        now = pytz.timezone(settings.TIME_ZONE).localize(datetime.now())
        month_ago = now - timedelta(days=30)
        week_ago = now - timedelta(days=7)
        tickets = FreshdeskTicket.objects.filter(
            created_at__gte=month_ago,
            status__in=[2, 3],
            deleted=False,
        )

        with xlsxwriter.Workbook(
            response,
            {
                "in_memory": True,
                "default_date_format": "dd-mmm-yyyy",
                "remove_timezone": True,
            },
        ) as workbook:
            # Stale tickets worksheet
            stale_tickets = tickets.filter(updated_at__lte=week_ago).order_by("freshdesk_responder", "created_at")
            stale = workbook.add_worksheet("Stale tickets")
            stale.write_row(
                "A1",
                (
                    "Ticket ID",
                    "URL",
                    "Subject",
                    "Created at",
                    "Last updated",
                    "Days since last update",
                    "Agent",
                    "Status",
                    "Note count",
                ),
            )
            row = 1
            for i in stale_tickets:
                since = pytz.timezone(settings.TIME_ZONE).localize(datetime.now()) - i.updated_at
                stale.write_row(
                    row,
                    0,
                    [
                        i.ticket_id,
                        "https://dpaw.freshdesk.com/helpdesk/tickets/{}".format(
                            i.ticket_id
                        ),
                        i.subject.strip(),
                        i.created_at,
                        i.updated_at,
                        since.days,
                        str(i.freshdesk_responder or ""),
                        i.get_status_display(),
                        i.freshdeskconversation_set.count(),
                    ],
                )
                row += 1
            stale.set_column("A:A", 8)
            stale.set_column("B:B", 49)
            stale.set_column("C:C", 100)
            stale.set_column("D:F", 13)
            stale.set_column("G:G", 46)

            # Contentious tickets worksheet
            cont_tickets = []
            for i in tickets:
                if i.freshdeskconversation_set.count() >= 6:
                    cont_tickets.append(i)
            contentious = workbook.add_worksheet("Contentious tickets")
            contentious.write_row(
                "A1",
                (
                    "Ticket ID",
                    "URL",
                    "Subject",
                    "Created at",
                    "Last updated",
                    "Days since last update",
                    "Agent",
                    "Status",
                    "Note count",
                ),
            )
            row = 1
            for i in cont_tickets:
                since = pytz.timezone(settings.TIME_ZONE).localize(datetime.now()) - i.updated_at
                contentious.write_row(
                    row,
                    0,
                    [
                        i.ticket_id,
                        "https://dpaw.freshdesk.com/helpdesk/tickets/{}".format(
                            i.ticket_id
                        ),
                        i.subject.strip(),
                        i.created_at,
                        i.updated_at,
                        since.days,
                        str(i.freshdesk_responder or ""),
                        i.get_status_display(),
                        i.freshdeskconversation_set.count(),
                    ],
                )
                row += 1
            contentious.set_column("A:A", 8)
            contentious.set_column("B:B", 49)
            contentious.set_column("C:C", 100)
            contentious.set_column("D:F", 13)
            contentious.set_column("G:G", 46)

        return response
