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


def department_user_ascender_discrepancies(fileobj, users):
    """For the passed in queryset of DepartmentUser objects, return an Excel spreadsheet
    that contains discrepancies between the user data and their associated Ascender HR data.
    """
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        users_sheet = workbook.add_worksheet('Discrepancies')
        users_sheet.write_row('A1', (
            'NAME', 'IT ASSETS FIELD', 'IT ASSETS VALUE', 'ASCENDER VALUE',
        ))
        row = 1

        for i in users:
            # Employee number is missing:
            if not i.employee_id:
                users_sheet.write_row(row, 0, [
                    i.get_full_name(),
                    'employee_id',
                    '',
                    '',
                ])
                row += 1
                continue  # Skip further checking on this user.

            # If we haven't cached Ascender data for the user yet, skip them.
            if not i.alesco_data:
                continue

            # First name.
            if 'first_name' in i.alesco_data and i.alesco_data['first_name'].upper() != i.given_name.upper():
                users_sheet.write_row(row, 0, [
                    i.get_full_name(),
                    'given_name',
                    i.given_name,
                    i.alesco_data['first_name'],
                ])
                row += 1

            # Surname.
            if 'surname' in i.alesco_data and i.alesco_data['surname'].upper() != i.surname.upper():
                users_sheet.write_row(row, 0, [
                    i.get_full_name(),
                    'surname',
                    i.surname,
                    i.alesco_data['surname'],
                ])
                row += 1

            # Phone number.
            if 'work_phone_no' in i.alesco_data and i.alesco_data['work_phone_no'] != i.telephone:
                users_sheet.write_row(row, 0, [
                    i.get_full_name(),
                    'telephone',
                    i.telephone,
                    i.alesco_data['work_phone_no'],
                ])
                row += 1

            # Cost centre
            if 'paypoint' in i.alesco_data:
                cc = False
                if i.alesco_data['paypoint'].startswith('R') and i.alesco_data['paypoint'].replace('R', '') != i.cost_centre.code.replace('RIA-', ''):
                    cc = True
                elif i.alesco_data['paypoint'].startswith('Z') and i.alesco_data['paypoint'].replace('Z', '') != i.cost_centre.code.replace('ZPA-', ''):
                    cc = True
                elif i.cost_centre.code.startswith('DBCA') and i.alesco_data['paypoint'] != i.cost_centre.code.replace('DBCA-', ''):
                    cc = True
                if cc:
                    users_sheet.write_row(row, 0, [
                        i.get_full_name(),
                        'cost_centre',
                        i.cost_centre.code,
                        i.alesco_data['paypoint'],
                    ])
                    row += 1

            # Title
            if 'occup_pos_title' in i.alesco_data and i.alesco_data['occup_pos_title'].upper() != i.title.upper():
                users_sheet.write_row(row, 0, [
                    i.get_full_name(),
                    'title',
                    i.title,
                    i.alesco_data['occup_pos_title'],
                ])
                row += 1

    return fileobj
