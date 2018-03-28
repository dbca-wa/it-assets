from django.conf.urls import url
from django.contrib.admin import register, ModelAdmin
from django.http import HttpResponse
from six import BytesIO
import unicodecsv

from .models import Computer, Mobile, EC2Instance, FreshdeskTicket


@register(Computer)
class ComputerAdmin(ModelAdmin):
    fieldsets = (
        ('Details', {
            'fields': (
                'hostname', 'sam_account_name', 'domain_bound', 'ad_guid', 'ad_dn', 'os_name',
                'os_version', 'os_service_pack', 'os_arch', 'ec2_instance')
        }),
        ('Management', {
            'fields': (
                'probable_owner', 'managed_by', 'location')
        }),
        ('Scan data', {
            'fields': ('date_pdq_updated', 'date_ad_updated')
        })
    )
    list_display = ['hostname', 'managed_by', 'probable_owner', 'os_name', 'ec2_instance']
    raw_id_fields = (
        'org_unit', 'cost_centre', 'probable_owner', 'managed_by', 'location')
    readonly_fields = ('date_pdq_updated', 'date_ad_updated')
    search_fields = ['sam_account_name', 'hostname']


@register(Mobile)
class MobileAdmin(ModelAdmin):
    list_display = ('identity', 'model', 'imei', 'serial_number', 'registered_to')
    search_fields = ('identity', 'model', 'imei', 'serial_number')


@register(EC2Instance)
class EC2InstanceAdmin(ModelAdmin):
    list_display = ('name', 'ec2id', 'launch_time', 'running', 'next_state', 'agent_version', 'aws_tag_values')
    search_fields = ('name', 'ec2id', 'launch_time')
    readonly_fields = ['extra_data_pretty', 'extra_data', 'agent_version']

    def aws_tag_values(self, obj):
        return obj.aws_tag_values()
    aws_tag_values.short_description = 'AWS tag values'


@register(FreshdeskTicket)
class FreshdeskTicketAdmin(ModelAdmin):
    date_hierarchy = 'created_at'
    list_display = (
        'ticket_id', 'created_at', 'freshdesk_requester', 'subject',
        'source_display', 'status_display', 'priority_display', 'type')
    fields = (
        'ticket_id', 'created_at', 'freshdesk_requester', 'subject',
        'source_display', 'status_display', 'priority_display', 'type',
        'due_by', 'description_text')
    readonly_fields = (
        'attachments', 'cc_emails', 'created_at', 'custom_fields',
        'deleted', 'description', 'description_text', 'due_by',
        'email', 'fr_due_by', 'fr_escalated', 'fwd_emails',
        'group_id', 'is_escalated', 'name', 'phone', 'priority',
        'reply_cc_emails', 'requester_id', 'responder_id', 'source',
        'spam', 'status', 'subject', 'tags', 'ticket_id', 'to_emails',
        'type', 'updated_at', 'freshdesk_requester',
        'freshdesk_responder', 'du_requester', 'du_responder',
        # Callables below.
        'source_display', 'status_display', 'priority_display')
    search_fields = (
        'subject', 'description_text', 'freshdesk_requester__name', 'freshdesk_requester__email',)

    def source_display(self, obj):
        return obj.get_source_display()
    source_display.short_description = 'Source'

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = 'Status'

    def priority_display(self, obj):
        return obj.get_priority_display()
    priority_display.short_description = 'Priority'

    def get_urls(self):
        urls = super(FreshdeskTicketAdmin, self).get_urls()
        urls = [
            url(r'^export-summary/$',
                self.admin_site.admin_view(self.export_summary),
                name='freshdeskticket_export_summary'),
        ] + urls
        return urls

    def export_summary(self, request):
        """Exports Freshdesk ticket summary data to a CSV.
        """
        from datetime import date
        from dateutil.relativedelta import relativedelta
        base = date.today()
        date_list = [base - relativedelta(months=x) for x in range(0, 12)]

        # Define fields to output.
        fields = ['month', 'category', 'subcategory', 'ticket_count']

        # Write data for FreshdeskTicket objects to the CSV.
        stream = BytesIO()
        wr = unicodecsv.writer(stream, encoding='utf-8')
        wr.writerow(fields)  # CSV header row.

        # Write month count of each category & subcategory
        for d in date_list:
            tickets = FreshdeskTicket.objects.filter(created_at__year=d.year, created_at__month=d.month)
            # Find the categories and subcategories for this queryset.
            cat = set()
            for t in tickets:  # Add tuples: (category, subcategory)
                cat.add((t.custom_fields['support_category'], t.custom_fields['support_subcategory']))
            cat = sorted(cat)
            # For each (category, subcategory), obtain a count of tickets.
            # TODO: save the category and subcategory onto each model so we
            # can just get Aggregate queries.
            for c in cat:
                count = 0
                for t in tickets:
                    if t.custom_fields['support_category'] == c[0] and t.custom_fields['support_subcategory'] == c[1]:
                        count += 1
                wr.writerow([d.strftime('%b-%Y'), c[0], c[1], count])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=freshdesktick_summary.csv'
        return response
