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
