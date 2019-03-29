import xlsxwriter


def itsr_staff_discrepancies(filename, it_systems):
    """This function will return a list of IT Systems where owner & custodian details have issues.
    """
    discrepancies = {}

    for sys in it_systems:
        if sys.owner and not sys.owner.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Owner {} is inactive'.format(sys.owner)))
        if sys.technology_custodian and not sys.technology_custodian.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Technology custodian {} is inactive'.format(sys.technology_custodian)))
        if sys.information_custodian and not sys.information_custodian.active:
            if sys.system_id not in discrepancies:
                discrepancies[sys.system_id] = []
            discrepancies[sys.system_id].append((sys.name, 'Information custodian {} is inactive'.format(sys.information_custodian)))
        # TODO: same as above, but staff belong to the wrong CC.

    with xlsxwriter.Workbook(
        filename,
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

    return filename
