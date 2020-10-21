from six import BytesIO
import unicodecsv
import xlsxwriter


def department_user_export(fileobj, users):
    """Writes a passed-in queryset of DepartmentUser objects to a file-like object as an
    Excel spreadsheet.
    """
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        users_sheet = workbook.add_worksheet('Department users')
        users_sheet.write_row('A1', (
            'NAME', 'EMAIL', 'TITLE', 'ACCOUNT TYPE', 'POSITION TYPE', 'EXPIRY DATE', 'COST CENTRE', 'CC MANAGER', 'CC MANAGER EMAIL', 'CC BMANAGER', 'CC BMANAGER EMAIL', 'ACTIVE', 'O365 LICENCE',
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.get_full_name(),
                i.email,
                i.title,
                i.get_account_type_display(),
                i.get_position_type_display(),
                i.expiry_date if i.expiry_date else '',
                i.cost_centre.code if i.cost_centre else '',
                i.cost_centre.manager.get_full_name() if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.manager.email if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.business_manager.get_full_name() if i.cost_centre and i.cost_centre.business_manager else '',
                i.cost_centre.business_manager.email if i.cost_centre and i.cost_centre.business_manager else '',
                i.active,
                i.o365_licence,
            ])
            row += 1
        users_sheet.set_column('A:A', 35)
        users_sheet.set_column('B:D', 45)
        users_sheet.set_column('E:E', 15)
        users_sheet.set_column('F:F', 18)
        users_sheet.set_column('G:G', 13)
        users_sheet.set_column('H:H', 35)
        users_sheet.set_column('I:I', 45)
        users_sheet.set_column('J:J', 35)
        users_sheet.set_column('K:K', 45)
        users_sheet.set_column('L:M', 13)

    return fileobj


def departmentuser_csv_report():
    """Output data from all DepartmentUser objects to a CSV, unpacking the
    various JSONField values.
    Returns a BytesIO object that can be written to a response or file.
    """
    from .models import DepartmentUser
    FIELDS = [
        'email', 'username', 'given_name', 'surname', 'name', 'preferred_name', 'title',
        'name_update_reference', 'employee_id', 'active', 'telephone', 'home_phone',
        'mobile_phone', 'other_phone', 'extension', 'expiry_date', 'org_unit',
        'cost_centre', 'manager', 'executive', 'vip', 'security_clearance',
        'contractor', 'o365_licence', 'shared_account',
        'notes', 'working_hours', 'org_data', 'alesco_data',
        'extra_data', 'date_created', 'date_updated', 'ad_guid',
    ]

    # Get any DepartmentUser with non-null alesco_data field.
    # alesco_data structure should be consistent to all (or null).
    du = DepartmentUser.objects.filter(alesco_data__isnull=False)[0]
    alesco_fields = du.alesco_data.keys()
    org_fields = {
        'department': ('units', 0, 'name'),
        'tier_2': ('units', 1, 'name'),
        'tier_3': ('units', 2, 'name'),
        'tier_4': ('units', 3, 'name'),
        'tier_5': ('units', 4, 'name')
    }

    header = [f for f in FIELDS]
    # These fields appended manually:
    header.append('account_type')
    header.append('position_type')
    header += org_fields.keys()
    header += alesco_fields

    # Get any DepartmentUser with non-null org_data field for the keys.
    if DepartmentUser.objects.filter(org_data__isnull=False).exists():
        du = DepartmentUser.objects.filter(org_data__isnull=False)[0]
        cc_keys = du.org_data['cost_centre'].keys()
        header += ['cost_centre_{}'.format(k) for k in cc_keys]
        location_keys = du.org_data['location'].keys()
        header += ['location_{}'.format(k) for k in location_keys]
        header.append('secondary_location')

    # Write data for all DepartmentUser objects to the CSV
    stream = BytesIO()
    wr = unicodecsv.writer(stream, encoding='utf-8')
    wr.writerow(header)
    for u in DepartmentUser.objects.all():
        record = []
        for f in FIELDS:
            record.append(getattr(u, f))
        try:  # Append account_type display value.
            record.append(u.get_account_type_display())
        except:
            record.append('')
        try:  # Append position_type display value.
            record.append(u.get_position_type_display())
        except:
            record.append('')
        for o in org_fields:
            try:
                src = u.org_data
                for x in org_fields[o]:
                    src = src[x]
                record.append(src)
            except:
                record.append('')

        for a in alesco_fields:
            try:
                record.append(u.alesco_data[a])
            except:
                record.append('')
        for i in cc_keys:
            try:
                record.append(u.org_data['cost_centre'][i])
            except:
                record.append('')
        for i in location_keys:
            try:
                record.append(u.org_data['location'][i])
            except:
                record.append('')
        if u.org_data and 'secondary_location' in u.org_data:
            record.append(u.org_data['secondary_location'])
        else:
            record.append('')

        # Write the row to the CSV stream.
        wr.writerow(record)

    return stream.getvalue()


def user_account_export(fileobj, users):
    """Writes a passed-in queryset of DepartmentUser objects to a file-like object as an
    Excel spreadsheet.
    """
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        users_sheet = workbook.add_worksheet('Department users')
        users_sheet.write_row('A1', (
            'ACCOUNT NAME', 'COST CENTRE', 'CONTACT NUMBER', 'OFFICE LOCATION', 'SHARED/ROLE-BASED ACCOUNT?', 'ACCOUNT ACTIVE?'
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.get_full_name(),
                i.cost_centre.code if i.cost_centre else '',
                i.telephone,
                i.location.name if i.location else '',
                i.shared_account,
                i.active,
            ])
            row += 1
        users_sheet.set_column('A:A', 30)
        users_sheet.set_column('B:B', 15)
        users_sheet.set_column('C:C', 22)
        users_sheet.set_column('D:D', 50)
        users_sheet.set_column('E:E', 29)
        users_sheet.set_column('F:F', 17)

    return fileobj
