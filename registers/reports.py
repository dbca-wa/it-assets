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
            'System ID', 'Name', 'Description', 'Status', 'Seasonality',
            'Availability', 'User groups', 'System type', 'Cost centre', 'Division', 'Owner',
            'Technology custodian', 'Information custodian', 'Link', 'Technical documentation',
            'Application server(s)', 'Database server(s)', 'Network storage', 'Backups',
            'BH support', 'AH support', 'User notification', 'Defunct date',
            'Retention reference no.', 'Retention/disposal action', 'Custody', 'Retention/disposal notes',
        ))
        row = 1
        for i in it_systems:
            systems.write_row(row, 0, [
                i.system_id,
                i.name,
                i.description,
                i.get_status_display(),
                i.get_seasonality_display() if i.seasonality else '',
                i.get_availability_display() if i.availability else '',
                ', '.join([str(j) for j in i.user_groups.all()]),
                i.get_system_type_display() if i.system_type else '',
                i.cost_centre.code if i.cost_centre else '',
                i.division_name,
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
                i.defunct_date,
                i.retention_reference_no,
                i.get_disposal_action_display(),
                i.get_custody_verbose(),
                i.retention_comments,
            ])
            row += 1

        systems.set_column('A:A', 9)
        systems.set_column('B:B', 45)
        systems.set_column('C:D', 18)
        systems.set_column('E:F', 19)
        systems.set_column('G:G', 50)
        systems.set_column('H:H', 30)
        systems.set_column('I:I', 13)
        systems.set_column('J:J', 41)
        systems.set_column('K:M', 21)
        systems.set_column('N:V', 50)
        systems.set_column('W:X', 18)
        systems.set_column('Y:AA', 50)

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


def it_system_platform_export(fileobj, it_systems, platforms):
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        systems = workbook.add_worksheet('IT Systems Register')
        systems.write_row('A1', (
            'System ID', 'Name', 'Status', 'Division', 'Business Service Owner',
            'System Owner', 'Technical Custodian', 'Information Custodian',
            'Seasonality', 'Availability', 'Link', 'Description',
            'Platform', 'Contingency Plan', 'Supportability',
            'General Purpose', 'Maintenance Lifecycle', 'Information Classification',
        ))
        row = 1
        for i in it_systems:
            systems.write_row(row, 0, [
                i.system_id,
                i.name,
                i.get_status_display(),
                i.division_name,
                i.cost_centre.division.manager.get_full_name() if i.division_name else '',
                i.owner.get_full_name() if i.owner else '',
                i.technology_custodian.get_full_name() if i.technology_custodian else '',
                i.information_custodian.get_full_name() if i.information_custodian else '',
                i.get_seasonality_display() if i.seasonality else '',
                i.get_availability_display() if i.availability else '',
                i.link,
                i.description,
                i.platform.name if i.platform else '',
                '',
                '',
                i.get_system_type_display() if i.system_type else '',
                '', '',
            ])
            row += 1

        systems.set_column('A:A', 9)
        systems.set_column('B:B', 45)
        systems.set_column('C:C', 18)
        systems.set_column('D:D', 37)
        systems.set_column('E:J', 20)
        systems.set_column('K:L', 65)
        systems.set_column('M:R', 37)

        p_sheet = workbook.add_worksheet('Platforms')
        p_sheet.write_row('A1', (
            'Platform', 'Patching cycle', 'Health', 'Tier', 'Annual cost',
        ))
        row = 1
        for i in platforms:
            p_sheet.write_row(row, 0, [
                i.name,
                '',
                i.health,
                i.tier,
                '',
            ])
            row += 1

        p_sheet.set_column('A:E', 18)

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


def dependency_export(fileobj, it_systems):
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
            'Compute dependencies',
        ))
        row = 1
        for i in it_systems:
            sheet.write_row(row, 0, [
                i.system_id,
                i.name,
                i.get_status_display(),
                i.division_name,
                ', '.join([str(dep) for dep in i.get_compute_dependencies()]),
            ])
            row += 1

        sheet.set_column('B:B', 50)
        sheet.set_column('C:C', 18)
        sheet.set_column('D:D', 40)
        sheet.set_column('E:E', 90)

    return fileobj
