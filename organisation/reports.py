from datetime import datetime
import xlsxwriter

from .utils import parse_windows_ts


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
            'NAME', 'EMAIL', 'TITLE', 'ACCOUNT TYPE', 'EMPLOYMENT STATUS', 'COST CENTRE', 'CC MANAGER', 'CC MANAGER EMAIL', 'CC BMANAGER', 'CC BMANAGER EMAIL',
            'ACTIVE', 'O365 LICENCE', 'TELEPHONE', 'MOBILE PHONE', 'LOCATION', 'ORGANISATION UNIT', 'GROUP UNIT',
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.get_full_name(),
                i.email,
                i.title,
                i.get_account_type_display(),
                i.get_employment_status(),
                i.cost_centre.code if i.cost_centre else '',
                i.cost_centre.manager.get_full_name() if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.manager.email if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.business_manager.get_full_name() if i.cost_centre and i.cost_centre.business_manager else '',
                i.cost_centre.business_manager.email if i.cost_centre and i.cost_centre.business_manager else '',
                i.active,
                i.get_licence(),
                i.telephone,
                i.mobile_phone,
                i.location.name if i.location else '',
                i.org_unit.name if i.org_unit else '',
                i.group_unit.name if i.group_unit else '',
            ])
            row += 1
        users_sheet.set_column('A:A', 35)
        users_sheet.set_column('B:E', 45)
        users_sheet.set_column('F:F', 13)
        users_sheet.set_column('G:G', 35)
        users_sheet.set_column('H:H', 45)
        users_sheet.set_column('I:I', 35)
        users_sheet.set_column('J:J', 45)
        users_sheet.set_column('K:L', 13)
        users_sheet.set_column('M:N', 20)
        users_sheet.set_column('O:Q', 60)

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
    that contains discrepancies between the user data and their associated Ascender data.
    """
    from .models import DepartmentUser
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        # Worksheet 1: department users having no Ascender employee ID.
        no_empid_sheet = workbook.add_worksheet('Users without employee ID')
        no_empid_sheet.write_row('A1', (
            'NAME', 'COST CENTRE', 'ACCOUNT TYPE', 'MICROSOFT LICENCES',
        ))
        row = 1
        # Exclude the obvious "non-user" accounts, plus volunteers and alumni.
        excludes = DepartmentUser.ACCOUNT_TYPE_EXCLUDE
        excludes.extend([7, 1])
        qs = users.filter(
            active=True,
            email__icontains='@dbca.wa.gov.au',
            employee_id__isnull=True,
            azure_guid__isnull=False,
            assigned_licences__contains=['MICROSOFT 365 E5'],
        ).exclude(
            account_type__in=excludes,
        ).order_by(
            'given_name',
            'surname',
        )
        for user in qs:
            no_empid_sheet.write_row(row, 0, [
                user.get_full_name(),
                user.cost_centre.code if user.cost_centre else '',
                user.get_account_type_display(),
                ', '.join(user.assigned_licences),
            ])
            row += 1

        no_empid_sheet.set_column('A:A', 30)
        no_empid_sheet.set_column('B:B', 14)
        no_empid_sheet.set_column('C:C', 44)
        no_empid_sheet.set_column('D:D', 56)

        # Worksheet 2: discrepancies between department user on-prem AD data and Ascender.
        users_sheet = workbook.add_worksheet('Discrepancies')
        users_sheet.write_row('A1', (
            'NAME', 'ACCOUNT TYPE', 'ATTRIBUTE', 'ACTIVE DIRECTORY VALUE', 'ASCENDER VALUE',
        ))
        row = 1

        qs = DepartmentUser.objects.filter(
            active=True,
            email__contains='@dbca.wa.gov.au',
            employee_id__isnull=False,
            ascender_data__isnull=False,
            ad_guid__isnull=False,
            ad_data__isnull=False,
            azure_guid__isnull=False,
            assigned_licences__contains=['MICROSOFT 365 E5'],
        ).exclude(
            account_type__in=excludes,
        ).order_by(
            'given_name',
            'surname',
        )
        for user in qs:
            # Expiry date
            if 'job_term_date' in user.ascender_data and user.ascender_data['job_term_date'] and 'AccountExpirationDate' in user.ad_data and user.ad_data['AccountExpirationDate']:
                ascender_date = datetime.strptime(user.ascender_data['job_term_date'], '%Y-%m-%d').date()
                onprem_date = parse_windows_ts(user.ad_data['AccountExpirationDate']).date()
                delta = ascender_date - onprem_date
                if delta.days > 1 or delta.days < -1:  # Allow one day difference, maximum.
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'Expiry date',
                        onprem_date.strftime("%d/%b/%Y"),
                        ascender_date.strftime("%d/%b/%Y"),
                    ])
                    row += 1

            # Cost centre
            if 'paypoint' in user.ascender_data and user.ascender_data['paypoint']:
                cc_diff = False
                if user.cost_centre:  # Case: user has CC set.
                    if user.ascender_data['paypoint'].startswith('R') and user.ascender_data['paypoint'].replace('R', '') != user.cost_centre.code.replace('RIA-', ''):
                        cc_diff = True
                    elif user.ascender_data['paypoint'].startswith('Z') and user.ascender_data['paypoint'].replace('Z', '') != user.cost_centre.code.replace('ZPA-', ''):
                        cc_diff = True
                    elif user.ascender_data['paypoint'][0] in '1234567890' and user.ascender_data['paypoint'] != user.cost_centre.code.replace('DBCA-', ''):
                        cc_diff = True
                else:  # Case: user has no CC set, but they should.
                    if user.ascender_data['paypoint'].startswith('R'):
                        cc_diff = True
                    elif user.ascender_data['paypoint'].startswith('Z'):
                        cc_diff = True
                    elif user.ascender_data['paypoint'][0] in '1234567890':
                        cc_diff = True
                if cc_diff:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'Cost centre',
                        user.cost_centre.code if user.cost_centre else '',
                        user.ascender_data['paypoint'],
                    ])
                    row += 1

            # Title
            title = user.title.upper() if user.title else ''
            if 'occup_pos_title' in user.ascender_data and user.ascender_data['occup_pos_title'].upper() != title:
                users_sheet.write_row(row, 0, [
                    user.get_full_name(),
                    user.get_account_type_display(),
                    'Title',
                    user.title,
                    user.ascender_data['occup_pos_title'],
                ])
                row += 1

            # First name.
            first_name = user.given_name.upper() if user.given_name else ''
            if 'first_name' in user.ascender_data and user.ascender_data['first_name'].upper() != first_name:
                users_sheet.write_row(row, 0, [
                    user.get_full_name(),
                    user.get_account_type_display(),
                    'First name',
                    user.given_name,
                    user.ascender_data['first_name'],
                ])
                row += 1

            # Surname.
            surname = user.surname.upper() if user.surname else ''
            if 'surname' in user.ascender_data and user.ascender_data['surname'].upper() != surname:
                users_sheet.write_row(row, 0, [
                    user.get_full_name(),
                    user.get_account_type_display(),
                    'Surname',
                    user.surname,
                    user.ascender_data['surname'],
                ])
                row += 1

            # Telephone number.
            if 'work_phone_no' in user.ascender_data and (user.ascender_data['work_phone_no'] or user.telephone):
                # Remove spaces, brackets and any 08 prefix from comparison values.
                if user.ascender_data['work_phone_no']:
                    t1 = user.ascender_data['work_phone_no'].replace('(', '').replace(')', '').replace(' ', '')
                    if t1.startswith('08'):
                        t1 = t1[2:]
                else:
                    t1 = ''
                if user.telephone:
                    t2 = user.telephone.replace('(', '').replace(')', '').replace(' ', '')
                    if t2.startswith('08'):
                        t2 = t2[2:]
                else:
                    t2 = ''
                if t1 != t2:
                    users_sheet.write_row(row, 0, [
                        user.get_full_name(),
                        user.get_account_type_display(),
                        'Telephone',
                        user.telephone,
                        user.ascender_data['work_phone_no'],
                    ])
                    row += 1

        users_sheet.set_column('A:A', 30)
        users_sheet.set_column('B:B', 44)
        users_sheet.set_column('C:C', 25)
        users_sheet.set_column('D:E', 50)

    return fileobj
