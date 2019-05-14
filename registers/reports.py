from django.conf import settings
from pytz import timezone
import xlsxwriter


TZ = timezone(settings.TIME_ZONE)


def itsr_staff_discrepancies(fileobj, it_systems):
    """This function will return an Excel workbook of IT Systems where owner & custodian details have issues.
    Pass in a file-like object to write into, plus a queryset of IT Systems.
    """
    discrepancies = {}

    for sys in it_systems:
        if sys.owner and not sys.owner.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Owner {} is inactive'.format(sys.owner)))
        '''
        # The check below is commented out as it is returning too many false positives at present.
        if sys.owner and sys.owner.cost_centre != sys.cost_centre:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Owner {} cost centre ({}) differs from {} cost centre ({})'.format(sys.owner, sys.owner.cost_centre, sys.name, sys.cost_centre)))
        '''
        if sys.technology_custodian and not sys.technology_custodian.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Technology custodian {} is inactive'.format(sys.technology_custodian)))
        if sys.information_custodian and not sys.information_custodian.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Information custodian {} is inactive'.format(sys.information_custodian)))
        if sys.cost_centre and not sys.cost_centre.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Cost centre {} is inactive'.format(sys.cost_centre)))
        # Support fields:
        if not sys.bh_support:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'No business hours support contact'))
        # For support fields, check if they are NOT shared accounts OR they are inactive.
        # Shared account types are set as inactive by default.
        if sys.bh_support and sys.bh_support.account_type != 5:
            if not sys.bh_support.active:
                if sys.system_id not in discrepancies:
                    discrepancies[sys.system_id] = []
                discrepancies[sys.system_id].append((sys.name, 'Business hours support contact {} is inactive'.format(sys.bh_support)))
        if sys.ah_support and sys.ah_support.account_type != 5:
            if not sys.ah_support.active:
                if sys.system_id not in discrepancies:
                    discrepancies[sys.system_id] = []
                discrepancies[sys.system_id].append((sys.name, 'After hours support contact {} is inactive'.format(sys.ah_support)))

    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        sheet = workbook.add_worksheet('Discrepancies')
        sheet.write_row('A1', ('System ID', 'System name', 'Discrepancy'))
        row = 1
        for k, v in discrepancies.items():
            for issue in v:
                sheet.write_row(row, 0, [k, issue[0], issue[1]])
                row += 1
        sheet.set_column('A:A', 10)
        sheet.set_column('B:B', 40)
        sheet.set_column('C:C', 100)

    return fileobj


def it_system_export(fileobj, it_systems):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        systems = workbook.add_worksheet('IT Systems')
        systems.write_row('A1', (
            'System ID', 'Name', 'Description', 'Status', 'Recovery category', 'Seasonality',
            'Availability', 'User groups', 'System type', 'Cost centre', 'Division', 'Owner',
            'Technology custodian', 'Information custodian', 'Link', 'Technical documentation',
            'Application server(s)', 'Database server(s)', 'Network storage', 'Backups',
            'BH support', 'AH support', 'User notification', 'Retention reference no.',
            'Decommission date', 'Retention/disposal action',
        ))
        row = 1
        for i in it_systems:
            systems.write_row(row, 0, [
                i.system_id,
                i.name,
                i.description,
                i.get_status_display(),
                i.get_recovery_category_display() if i.recovery_category else '',
                i.get_seasonality_display() if i.seasonality else '',
                i.get_availability_display() if i.availability else '',
                ', '.join([str(j) for j in i.user_groups.all()]),
                i.get_system_type_display() if i.system_type else '',
                i.cost_centre.code if i.cost_centre else '',
                i.cost_centre.division.name if (i.cost_centre and i.cost_centre.division) else '',
                i.owner.get_full_name() if i.owner else '',
                i.technology_custodian.get_full_name() if i.technology_custodian else '',
                i.information_custodian.get_full_name() if i.information_custodian else '',
                i.link,
                i.technical_documentation if i.technical_documentation else '',
                i.application_server,
                i.database_server,
                i.network_storage,
                i.get_backups_display() if i.backups else '',
                i.bh_support.email if i.bh_support else '',
                i.ah_support.email if i.ah_support else '',
                i.user_notification,
                '{:.2f}'.format(i.retention_reference_no) if i.retention_reference_no else '',
                i.decommission_date,
                i.get_retention_disposal_action_display(),
            ])
            row += 1
        systems.set_column('A:A', 9)
        systems.set_column('B:B', 45)
        systems.set_column('C:D', 18)
        systems.set_column('E:E', 27)
        systems.set_column('F:G', 19)
        systems.set_column('H:H', 50)
        systems.set_column('I:I', 30)
        systems.set_column('J:J', 13)
        systems.set_column('K:K', 41)
        systems.set_column('L:N', 21)
        systems.set_column('O:W', 50)
        systems.set_column('X:X', 22)
        systems.set_column('Y:Y', 18)
        systems.set_column('Z:Z', 50)

    return fileobj


def it_system_hardware_export(fileobj, hardware):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        hw_sheet = workbook.add_worksheet('IT system hardware')
        hw_sheet.write_row('A1', (
            'Hostname', 'Host', 'OS', 'Role', 'Production?', 'EC2 ID', 'Patch group',
            'IT system ID', 'IT system name', 'IT system CC', 'IT system availability',
            'IT system custodian', 'IT system owner', 'IT system info custodian'
        ))
        row = 1
        for i in hardware:
            if i.itsystem_set.all().exclude(status=3).exists():
                # Write a row for each linked, non-decommissioned ITSystem.
                for it in i.itsystem_set.all().exclude(status=3):
                    hw_sheet.write_row(row, 0, [
                        i.computer.hostname, i.host, i.computer.os_name, i.get_role_display(),
                        i.production, i.computer.ec2_instance.ec2id if i.computer.ec2_instance else '',
                        str(i.patch_group), it.system_id, it.name, str(it.cost_centre),
                        it.get_availability_display(),
                        it.technology_custodian.get_full_name() if it.technology_custodian else '',
                        it.owner.get_full_name() if it.owner else '',
                        it.information_custodian.get_full_name() if it.information_custodian else ''
                    ])
            else:
                # No IT Systems - just record the hardware details.
                hw_sheet.write_row(row, 0, [
                    i.computer.hostname, i.host, i.computer.os_name, i.get_role_display(),
                    i.production, i.computer.ec2_instance.ec2id if i.computer.ec2_instance else '',
                    str(i.patch_group)
                ])
            row += 1
        hw_sheet.set_column('A:A', 36)

    return fileobj


def incident_export(fileobj, incidents):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        # Incident Register worksheet
        register = workbook.add_worksheet('Incident register')
        register.write_row('A1', (
            'Incident no.', 'Status', 'Description', 'Priority', 'Category', 'Start time',
            'Resolution time', 'Duration', 'RTO met', 'System(s) affected', 'Location(s) affected',
            'Incident manager', 'Incident owner', 'Detection method', 'Workaround action(s)',
            'Root cause', 'Remediation action(s)', 'Division(s) affected'
        ))
        row = 1
        for i in incidents:
            register.write_row(row, 0, [
                i.pk, i.status.capitalize(), i.description, i.get_priority_display(),
                i.get_category_display(), i.start.astimezone(TZ),
                i.resolution.astimezone(TZ) if i.resolution else '',
                str(i.duration) if i.duration else '', i.rto_met(),
                i.systems_affected, i.locations_affected,
                i.manager.get_full_name() if i.manager else '',
                i.owner.get_full_name() if i.owner else '',
                i.get_detection_display(), i.workaround, i.root_cause, i.remediation,
                i.divisions_affected if i.divisions_affected else ''
            ])
            row += 1
        register.set_column('A:A', 11)
        register.set_column('C:C', 72)
        register.set_column('D:D', 13)
        register.set_column('E:E', 18)
        register.set_column('F:G', 16)
        register.set_column('H:H', 13)
        register.set_column('I:I', 8)
        register.set_column('J:K', 28)
        register.set_column('L:M', 16)
        register.set_column('N:N', 20)
        register.set_column('O:R', 24)

        return fileobj


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
            'System(s) affected', 'Incident URL', 'Unexpected issues',
        ))
        row = 1
        for i in rfcs:
            changes.write_row(row, 0, [
                i.pk, i.title, i.get_change_type_display(),
                i.requester.get_full_name() if i.requester else '',
                i.endorser.get_full_name() if i.endorser else '',
                i.implementer.get_full_name() if i.implementer else '',
                i.get_status_display(), i.test_date,
                i.planned_start.astimezone(TZ) if i.planned_start else '',
                i.planned_end.astimezone(TZ) if i.planned_end else '',
                i.completed.astimezone(TZ) if i.completed else '',
                str(i.outage) if i.outage else '', i.systems_affected, i.incident_url,
                i.unexpected_issues,
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
        changes.set_column('O:O', 17)

    return fileobj
