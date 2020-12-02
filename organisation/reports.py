from fuzzywuzzy import fuzz
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
                '',
                i.cost_centre.code if i.cost_centre else '',
                i.cost_centre.manager.get_full_name() if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.manager.email if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.business_manager.get_full_name() if i.cost_centre and i.cost_centre.business_manager else '',
                i.cost_centre.business_manager.email if i.cost_centre and i.cost_centre.business_manager else '',
                i.active,
                i.get_office_licence(),
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
            'NAME', 'ACCOUNT TYPE', 'IT ASSETS FIELD', 'IT ASSETS VALUE', 'ASCENDER VALUE',
        ))
        row = 1

        for user in users:
            # Employee number is missing:
            if not user.employee_id and user.account_type not in [3, 6, 7, 1]:
                users_sheet.write_row(row, 0, [
                    user.get_full_name(),
                    user.get_account_type_display(),
                    'employee_id',
                    '',
                    '',
                ])
                row += 1
                continue  # Skip further checking on this user.

            # If we haven't cached Ascender data for the user yet, skip them.
            if not user.alesco_data:
                continue

            # First name.
            if 'first_name' in user.alesco_data:
                r = fuzz.ratio(user.alesco_data['first_name'].upper(), user.given_name.upper())
                if r < 90:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'given_name',
                        user.given_name,
                        user.alesco_data['first_name'],
                    ])
                    row += 1

            # Surname.
            if 'surname' in user.alesco_data:
                r = fuzz.ratio(user.alesco_data['surname'].upper(), user.surname.upper())
                if r < 90:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'surname',
                        user.surname,
                        user.alesco_data['surname'],
                    ])
                    row += 1

            # Phone number.
            if 'work_phone_no' in user.alesco_data and user.alesco_data['work_phone_no'] and user.telephone:
                # Remove spaces, brackets and 08 prefix from comparison values.
                t1 = user.alesco_data['work_phone_no'].replace('(', '').replace(')', '').replace(' ', '')
                if t1.startswith('08'):
                    t1 = t1[2:]
                t2 = user.telephone.replace('(', '').replace(')', '').replace(' ', '')
                if t2.startswith('08'):
                    t2 = t2[2:]
                ratio = fuzz.ratio(t1, t2)
                if ratio <= 90:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'telephone',
                        user.telephone,
                        user.alesco_data['work_phone_no'],
                    ])
                    row += 1

            # Cost centre
            if 'paypoint' in user.alesco_data:
                cc = False
                if user.alesco_data['paypoint'].startswith('R') and user.alesco_data['paypoint'].replace('R', '') != user.cost_centre.code.replace('RIA-', ''):
                    cc = True
                elif user.alesco_data['paypoint'].startswith('Z') and user.alesco_data['paypoint'].replace('Z', '') != user.cost_centre.code.replace('ZPA-', ''):
                    cc = True
                elif user.cost_centre.code.startswith('DBCA') and user.alesco_data['paypoint'] != user.cost_centre.code.replace('DBCA-', ''):
                    cc = True
                if cc:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'cost_centre',
                        user.cost_centre.code,
                        user.alesco_data['paypoint'],
                    ])
                    row += 1

            # Title - use fuzzy string matching to find mismatches that are reasonably different.
            if 'occup_pos_title' in user.alesco_data:
                ratio = fuzz.ratio(user.alesco_data['occup_pos_title'].upper(), user.title.upper())
                if ratio <= 90:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'title',
                        user.title,
                        user.alesco_data['occup_pos_title'],
                    ])
                    row += 1

    return fileobj
