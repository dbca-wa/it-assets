import re
import xlsxwriter
from .models import DepartmentUser, Location
from .utils import title_except


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
            'NAME', 'EMAIL', 'TITLE', 'ACCOUNT TYPE', 'EMPLOYEE ID', 'EMPLOYMENT STATUS', 'COST CENTRE',
            'CC MANAGER', 'CC MANAGER EMAIL', 'ACTIVE', 'M365 LICENCE',
            'TELEPHONE', 'MOBILE PHONE', 'LOCATION', 'DIVISION', 'UNIT',
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.name,
                i.email,
                i.title,
                i.get_account_type_display(),
                i.employee_id,
                i.get_employment_status(),
                i.cost_centre.code if i.cost_centre else '',
                i.cost_centre.manager.name if i.cost_centre and i.cost_centre.manager else '',
                i.cost_centre.manager.email if i.cost_centre and i.cost_centre.manager else '',
                i.active,
                i.get_licence(),
                i.telephone,
                i.mobile_phone,
                i.location.name if i.location else '',
                i.cost_centre.get_division_name_display() if i.cost_centre else '',
                title_except(i.get_ascender_org_path()[-1]) if i.get_ascender_org_path() else '',
            ])
            row += 1
        users_sheet.set_column('A:A', 35)
        users_sheet.set_column('B:D', 45)
        users_sheet.set_column('E:E', 12)
        users_sheet.set_column('F:F', 45)
        users_sheet.set_column('G:G', 13)
        users_sheet.set_column('H:H', 35)
        users_sheet.set_column('I:I', 45)
        users_sheet.set_column('J:K', 13)
        users_sheet.set_column('L:M', 20)
        users_sheet.set_column('N:P', 60)

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
            'NAME', 'COST CENTRE', 'MICROSOFT 365 LICENCE', 'AD ACCOUNT ACTIVE?',
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.name,
                i.cost_centre.code if i.cost_centre else '',
                i.get_licence(),
                i.active,
            ])
            row += 1
        users_sheet.set_column('A:A', 30)
        users_sheet.set_column('B:B', 15)
        users_sheet.set_column('C:C', 22)
        users_sheet.set_column('D:D', 20)

    return fileobj


def user_changes_export(fileobj, action_logs):
    """Takes in a passed-in queryset of AscenderActionLog objects and a file-like object, and writes
    an Excel spreadsheet to the file which contains a specified set of changes for each department
    user. This is a somewhat clunky hack for this record type, but it works.
    """
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        },
    ) as workbook:
        changes_sheet = workbook.add_worksheet('Department user changes')
        changes_sheet.write_row('A1', (
            'DATE',
            'NAME',
            'EMAIL',
            'OLD TITLE',
            'NEW TITLE',
            'OLD MANAGER',
            'NEW MANAGER',
            'OLD CC',
            'NEW CC',
            'OLD LOCATION',
            'NEW LOCATION',
        ))
        row = 1

        for log in action_logs:
            # Split the log text content on spaces.
            log_parts = log.log.split(' ')
            if log_parts[0] == 'Created':
                continue

            email = log_parts[0]
            field = log_parts[1]
            try:
                du = DepartmentUser.objects.get(email=email)
            except:
                # DepartmentUser object no longer present; skip it.
                continue

            row_data = [
                log.created.strftime('%d/%b/%Y'),
                du.name,
                du.email,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ]

            # Title
            if field == 'title':
                pattern = r'title (.+) differs'
                old_title = re.findall(pattern, log.log)[0]
                new_title = title_except(log.ascender_data['occup_pos_title'])
                row_data[3] = old_title
                row_data[4] = new_title
                changes_sheet.write_row(row, 0, row_data)
                row += 1
            # Manager
            elif field == 'manager':
                try:
                    old_manager = DepartmentUser.objects.get(email=log_parts[2])
                    new_manager = DepartmentUser.objects.get(email=log_parts[-1])
                    row_data[5] = old_manager.name
                    row_data[6] = new_manager.name
                    changes_sheet.write_row(row, 0, row_data)
                    row += 1
                except:
                    # DepartmentUser object no longer present; skip it.
                    pass
            # Cost centre
            elif field == 'cost':
                pattern = r'centre (.+) differs'
                old_cc = re.findall(pattern, log.log)[0]
                pattern = r'paypoint (.+), updating'
                new_cc = re.findall(pattern, log.log)[0]
                row_data[7] = old_cc
                row_data[8] = new_cc
                changes_sheet.write_row(row, 0, row_data)
                row += 1
            # Location
            elif field == 'location':
                pattern = r'location (.+) differs'
                old_location = re.findall(pattern, log.log)[0]
                new_location = Location.objects.get(ascender_desc=log.ascender_data['geo_location_desc'])
                row_data[9] = old_location
                row_data[10] = new_location.name
                changes_sheet.write_row(row, 0, row_data)
                row += 1

        changes_sheet.set_column('A:A', 12)
        changes_sheet.set_column('B:B', 24)
        changes_sheet.set_column('C:K', 40)

    return fileobj
