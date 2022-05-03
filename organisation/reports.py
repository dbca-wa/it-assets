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
            'NAME', 'EMAIL', 'TITLE', 'ACCOUNT TYPE', 'EMPLOYEE ID', 'EMPLOYMENT STATUS', 'COST CENTRE',
            'CC MANAGER', 'CC MANAGER EMAIL', 'CC BMANAGER', 'CC BMANAGER EMAIL', 'ACTIVE', 'M365 LICENCE',
            'TELEPHONE', 'MOBILE PHONE', 'LOCATION', 'ORGANISATION UNIT', 'GROUP UNIT',
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
                i.cost_centre.business_manager.name if i.cost_centre and i.cost_centre.business_manager else '',
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
        users_sheet.set_column('B:D', 45)
        users_sheet.set_column('E:E', 12)
        users_sheet.set_column('F:F', 45)
        users_sheet.set_column('G:G', 13)
        users_sheet.set_column('H:H', 35)
        users_sheet.set_column('I:I', 45)
        users_sheet.set_column('J:J', 35)
        users_sheet.set_column('K:K', 45)
        users_sheet.set_column('L:M', 13)
        users_sheet.set_column('N:O', 20)
        users_sheet.set_column('P:R', 60)

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
            'NAME', 'COST CENTRE', 'MICROSOFT 365 LICENCE', 'ACCOUNT ACTIVE?', 'SHARED/ROLE-BASED ACCOUNT?'
        ))
        row = 1
        for i in users:
            users_sheet.write_row(row, 0, [
                i.name,
                i.cost_centre.code if i.cost_centre else '',
                i.get_licence(),
                i.active,
                i.shared_account,
            ])
            row += 1
        users_sheet.set_column('A:A', 30)
        users_sheet.set_column('B:B', 15)
        users_sheet.set_column('C:C', 22)
        users_sheet.set_column('D:D', 17)
        users_sheet.set_column('E:E', 29)

    return fileobj
