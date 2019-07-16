
import xlsxwriter

def host_status_export(fileobj, host_status):
    
    with xlsxwriter.Workbook(
        fileobj,
        {
            'in_memory': True,
            'default_date_format': 'dd-mmm-yyyy HH:MM',
            'remove_timezone': True,
        }
    ) as workbook:
        sheet = workbook.add_worksheet('Host statuses')
        date_summary = ', '.join((x.isoformat() for x in host_status.values_list('date', flat=True).order_by('date').distinct()))
        bold = workbook.add_format({'bold': True})

        sheet.write_row(0, 0, ('Host status report for {}'.format(date_summary),), bold)
        sheet.write_row(2, 0, ('Host name', 'Scan range', 'Category', 'Status', 'Plugin', 'Output'), bold)
        row = 3
        for status in host_status:
            host = status.host.name
            scan_range = status.ping_scan_range.name if status.ping_scan_range else ''

            for cat in ('monitor', 'vulnerability', 'backup', 'patching'):
                stat = getattr(status, 'get_{}_status_display'.format(cat))()
                plug = getattr(status, '{}_plugin'.format(cat))
                plug_name = plug.name if plug else ''
                output = getattr(status, '{}_output'.format(cat))
                url = getattr(status, '{}_url'.format(cat))
                sheet.write_row(row, 0, (host, scan_range, cat, stat, plug_name, output))
                if url:
                    sheet.write_url(row, 3, url, string=stat)
                row += 1

            ip_list = ','.join(status.host.host_ips.values_list('ip', flat=True))
            sheet.write_row(row, 0, (host, scan_range, 'ipv4', '-', '-', ip_list))
            row += 1

            os = status.vulnerability_info['os'] if status.vulnerability_info and 'os' in status.vulnerability_info else 'Unknown'
            sheet.write_row(row, 0, (host, scan_range, 'os', '-', '-', os))
            row += 1

            num_critical = status.vulnerability_info['num_critical'] if status.vulnerability_info and 'num_critical' in status.vulnerability_info else 'Unknown'
            sheet.write_row(row, 0, (host, scan_range, 'num_critical', '-', '-', num_critical))
            row += 1

            num_high = status.vulnerability_info['num_high'] if status.vulnerability_info and 'num_high' in status.vulnerability_info else 'Unknown'
            sheet.write_row(row, 0, (host, scan_range, 'num_high', '-', '-', num_high))
            row += 1

        sheet.set_column('A:A', 40)
        sheet.set_column('B:B', 25)
        sheet.set_column('C:C', 12)
        sheet.set_column('D:D', 12)
        sheet.set_column('E:E', 20)
        sheet.set_column('F:F', 60)
        sheet.autofilter(2, 0, row-1, 5)

    return fileobj
