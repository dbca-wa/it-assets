from django.conf import settings
from pytz import timezone
import xlsxwriter


TZ = timezone(settings.TIME_ZONE)


def change_request_export(fileobj, rfcs):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        changes = workbook.add_worksheet('Change requests')
        changes.write_row('A1', (
            'Change ref.', 'Title', 'Change type', 'Requester', 'Endorser', 'Implementer', 'Status',
            'Test date', 'Planned start', 'Planned end', 'Completed', 'Outage duration',
            'System(s) affected', 'Incident URL', 'Unexpected issues', 'Created timestamp',
        ))
        row = 1
        for i in rfcs:
            changes.write_row(row, 0, [
                i.pk, i.title, i.get_change_type_display(),
                i.requester.name if i.requester else '',
                i.endorser.name if i.endorser else '',
                i.implementer.name if i.implementer else '',
                i.get_status_display(), i.test_date,
                i.planned_start.astimezone(TZ) if i.planned_start else '',
                i.planned_end.astimezone(TZ) if i.planned_end else '',
                i.completed.astimezone(TZ) if i.completed else '',
                str(i.outage) if i.outage else '', i.systems_affected, i.incident_url,
                i.unexpected_issues, i.created.astimezone(TZ),
            ])
            row += 1
        changes.set_column('A:A', 11)
        changes.set_column('B:B', 44)
        changes.set_column('C:C', 12)
        changes.set_column('D:F', 18)
        changes.set_column('G:G', 26)
        changes.set_column('H:K', 18)
        changes.set_column('L:L', 15)
        changes.set_column('M:N', 30)
        changes.set_column('O:P', 18)

    return fileobj


def riskassessment_export(fileobj, it_systems):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        sheet = workbook.add_worksheet('Risk assessments - IT systems')
        sheet.write_row('A1', (
            'IT system ID', 'IT system name', 'IT system status', 'Division',
            'Platform', 'Critical function', 'Traffic', 'Access', 'Backups',
            'Support', 'Operating System', 'Vulnerability', 'Contingency plan',
        ))
        row = 1
        for i in it_systems:
            sheet.write_row(row, 0, [
                i.system_id,
                i.name,
                i.get_status_display(),
                i.division_name,
                i.platform.name if i.platform else '',
            ])

            risks = i.get_risk_category_maxes()
            sheet.write_row(row, 5, [r.rating_desc.capitalize() if r else '' for r in risks.values()])
            row += 1
        sheet.set_column('B:B', 50)
        sheet.set_column('C:C', 18)
        sheet.set_column('D:D', 40)
        sheet.set_column('E:M', 19)

    return fileobj
