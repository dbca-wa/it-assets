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
