from decimal import Decimal
from datetime import datetime
from dateutil.parser import parse
import re
from io import BytesIO
import unicodecsv as csv

from organisation.models import DepartmentUser, Location, CostCentre
from .models import HardwareAsset, Vendor, HardwareModel


def validate_csv(fileobj):
    """Performs validation on a CSV file of asset data.
    Returns a tuple (number of assets, errors, warnings, notes).
    ``fileobj`` should be a bytes-encodes file-like object.
    """
    try:
        c = csv.DictReader(fileobj)
    except Exception:
        errors = ["""The file you uploaded could not be interpreted. Check that
            you uploaded the correct file (in a .csv format) and try again."""]
        return (0, errors, [], [])

    critical_fields = ('ASSET TAG', 'SERIAL', 'DATE PURCHASED')
    all_fields = critical_fields + (
        'FINANCE ASSET TAG', 'VENDOR', 'MODEL TYPE', 'HARDWARE MODEL', 'LOCATION',
        'STATUS', 'COST CENTRE', 'PURCHASED VALUE', 'ASSIGNED USER', 'NOTES',
        'WARRANTY END')
    errors = []
    warnings = []
    notes = []
    asset_tag_list = []

    # Inspect the header row.
    for field in critical_fields:
        if field not in c.fieldnames:
            errors.append(
                'The mandatory column {} is missing from the spreadsheet.'.format(field))

    if 'STATUS' not in c.fieldnames:
        warnings.append('''Your spreadsheet does not contain a column called
            'STATUS' - the status field of every new asset will be set to
            'In storage'.''')

    for field in c.fieldnames:
        if field not in all_fields:
            warnings.append('''Your spreadsheet contains an unknown column '{}'.
                This column will be ignored during the import process.'''.format(field))

    # Inspect each row and do field-specific validation.
    for row in c:
        # Check asset tag.
        asset_tag_re = re.compile("^IT\d{5}$")
        if 'ASSET TAG' in row and row['ASSET TAG']:
            if HardwareAsset.objects.filter(asset_tag__iexact=row['ASSET TAG']).exists():
                errors.append(
                    '''Row {}: The asset tag '{}' already exists in the database. '''
                    '''Asset tags must be unique.'''.format(c.line_num, row['ASSET TAG']))
            if not asset_tag_re.match(row['ASSET TAG'].upper()):
                errors.append(
                    '''Row {}: The value '{}' in the asset tag column is '''
                    '''invalid. Asset tags should be in the format '''
                    '''ITXXXXX.'''.format(c.line_num, row['asset tag']))
            if row['ASSET TAG'].upper() in asset_tag_list:
                errors.append(
                    '''Row {}: The asset tag '{}' exists in several rows in '''
                    '''the spreadsheet. Asset tags are unique - remove the '''
                    '''duplicate values to continue.'''.format(c.line_num, row['ASSET TAG']))
            asset_tag_list.append(row['ASSET TAG'].upper())
        else:
            errors.append(
                '''Row {}: A value for the asset tag column is missing. '''
                '''Enter a value to continue.'''.format(c.line_num))

        # Check serial.
        if 'SERIAL' in row and not row['SERIAL']:
            errors.append(
                '''Row {}: The mandatory field 'SERIAL' is blank. If the '''
                '''hardware does not have a serial, enter 'Unknown'.'''.format(c.line_num))

        # Check date purchased.
        if 'DATE PURCHASED' in row and row['DATE PURCHASED']:
            try:
                parse(row['DATE PURCHASED'])
            except ValueError:
                errors.append(
                    '''Row {}: The value '{}' in the 'DATE PURCHASED' column '''
                    '''is invalid. Dates must be in the format '''
                    '''dd/mm/yyyy.'''.format(c.line_num, row['DATE PURCHASED']))
        else:
            errors.append(
                '''Row {}: The mandatory field 'DATE PURCHASED' is blank.'''.format(c.line_num))

        # Check finance asset tag.
        if 'FINANCE ASSET TAG' in row and row['FINANCE ASSET TAG']:
            finance_asset_tag_re = re.compile("^\d+$")
            if not finance_asset_tag_re.match(row['FINANCE ASSET TAG']):
                warnings.append(
                    '''Row {}: The finance asset tag '{}' contains numbers '''
                    '''and other characters - these tags usually only contain '''
                    '''numbers. Check the tag is correct before '''
                    '''proceeding.'''.format(c.line_num, row['FINANCE ASSET TAG']))

        # Check vendor.
        if 'VENDOR' in row and row['VENDOR']:
            if not Vendor.objects.filter(name__iexact=row['VENDOR']).exists():
                notes.append(
                    '''Row {}: Vendor '{}' is unknown - a new vendor '''
                    '''will be created.'''.format(c.line_num, row['VENDOR']))

        # Check model type.
        if 'MODEL TYPE' in row and row['MODEL TYPE']:
            if row['MODEL TYPE'] not in [i[0] for i in HardwareModel.TYPE_CHOICES]:
                errors.append(
                    '''Row {}: The value '{}' in the MODEL TYPE column is not recognised. '''
                    '''The value will be ignored.'''.format(c.line_num, row['MODEL TYPE']))

        # Check hardware model.
        if 'HARDWARE MODEL' in row and row['HARDWARE MODEL']:
            if not HardwareModel.objects.filter(model_no__iexact=row['HARDWARE MODEL']).exists():
                notes.append(
                    '''Row {}: Model '{}' is unknown - a new model will '''
                    '''be created.'''.format(c.line_num, row['HARDWARE MODEL']))

        # Check status.
        if 'STATUS' in row and row['STATUS']:
            if row['STATUS'] not in ['In storage', 'Deployed', 'Disposed']:
                errors.append(
                    '''Row {}: The value '{}' in the STATUS column is invalid. '''
                    '''The asset status must be one of 'In storage', '''
                    ''''Deployed' or 'Disposed'.'''.format(c.line_num, row['STATUS']))

        # Check cost centre.
        if 'COST CENTRE' in row and row['COST CENTRE']:
            if CostCentre.objects.filter(code=row['COST CENTRE']).count() < 1:
                errors.append(
                    '''Row {}: There is no cost centre code that matches {}. '''
                    '''Cost centre must exactly match existing codes.'''.format(c.line_num, row['COST CENTRE']))
        # Check location.
        if 'LOCATION' in row and row['LOCATION']:
            if Location.objects.filter(name__istartswith=row['LOCATION']).count() > 1:
                errors.append(
                    '''Row {}: {} matches more than one location name. '''
                    '''Locations must <a href="{}">match existing names</a>.'''.format(c.line_num, row['LOCATION'], '/api/options/?list=location'))
            elif Location.objects.filter(name__istartswith=row['LOCATION']).count() < 1:
                errors.append(
                    '''Row {}: There is no location matching name {}. '''
                    '''Locations must match existing names.'''.format(c.line_num, row['LOCATION']))

        # Check warranty end.
        if 'WARRANTY END' in row and row['WARRANTY END']:
            try:
                parse(row['WARRANTY END'])
            except ValueError:
                errors.append(
                    '''Row {}: The value '{}' in the 'WARRANTY END' column '''
                    '''is invalid. Dates must be in the format '''
                    '''dd/mm/yyyy.'''.format(c.line_num, row['WARRANY END']))

    # Reset fileobj now that we're finished with it.
    fileobj.seek(0)
    return (len(asset_tag_list), errors, warnings, notes)


def import_csv(fileobj):
    """Undertakes an import of the passed-in CSV file.
    Returns a list of objects created.
    """
    c = csv.DictReader(fileobj)
    unknown_vendor = Vendor.objects.get_or_create(name='Unknown Vendor')[0]
    unknown_model = HardwareModel.objects.get_or_create(
        model_type='Other', vendor=unknown_vendor, model_no='Unknown model')[0]
    unknown_location = Location.objects.get_or_create(
        name='Unknown', address='Unknown')[0]
    assets_created = []

    for row in c:
        asset = HardwareAsset(
            asset_tag=row['ASSET TAG'].upper(), serial=row['SERIAL'],
            date_purchased=parse(row['DATE PURCHASED'])
        )
        if 'FINANCE ASSET TAG' in row and row['FINANCE ASSET TAG']:
            asset.finance_asset_tag = row['FINANCE ASSET TAG']
        if 'VENDOR' in row and row['VENDOR']:
            if not Vendor.objects.filter(name__iexact=row['VENDOR']).exists():
                vendor = Vendor.objects.get_or_create(name=row['VENDOR'])[0]
                asset.vendor = vendor
            else:
                vendor = Vendor.objects.get(name__iexact=row['VENDOR'])
                asset.vendor = vendor
        else:
            # No vendor specified.
            asset.vendor = unknown_vendor

        if 'MODEL TYPE' in row and row['MODEL TYPE']:
            if row['MODEL TYPE'] in [i[0] for i in HardwareModel.TYPE_CHOICES]:
                asset.model_type = row['MODEL TYPE']

        if 'HARDWARE MODEL' in row and row['HARDWARE MODEL']:
            if not HardwareModel.objects.filter(model_no__iexact=row['HARDWARE MODEL']).exists():
                # Create a new hardware model (use the vendor as manufacturer).
                asset.hardware_model = HardwareModel.objects.get_or_create(
                    vendor=asset.vendor, model_no=row['HARDWARE MODEL'], model_type='Other')[0]
            else:
                # Use the existing hardware model.
                asset.hardware_model = HardwareModel.objects.get(model_no__iexact=row['HARDWARE MODEL'])
        else:
            # No hardware model specified.
            asset.hardware_model = unknown_model

        if 'LOCATION' in row and row['LOCATION']:
            if Location.objects.filter(name__istartswith=row['LOCATION']).count() == 1:
                asset.location = Location.objects.get(name__istartswith=row['LOCATION'])
            else:
                asset.location = unknown_location
        if 'STATUS' in row and row['STATUS']:
            if row['STATUS'] in ['In storage', 'Deployed', 'Disposed']:
                asset.status = row['STATUS']
        if 'COST CENTRE' in row and row['COST CENTRE']:
            try:
                asset.cost_centre = CostCentre.objects.get(code=row['COST CENTRE'])
            except:
                asset.cost_centre = None
        if 'PURCHASED VALUE' in row and row['PURCHASED VALUE']:
            try:
                asset.purchased_value = Decimal(row['PURCHASED VALUE'])
            except:
                asset.purchased_value = None
        if 'ASSIGNED USER' in row and row['ASSIGNED USER']:
            if DepartmentUser.objects.filter(username__iexact=row['ASSIGNED USER']).exists():
                asset.assigned_user = DepartmentUser.objects.get(
                    username__iexact=row['ASSIGNED USER'])
        if 'NOTES' in row and row['NOTES']:
            asset.notes = row['NOTES']
        if 'WARRANTY END' in row and row['WARRANTY END']:
            asset.warranty_end = parse(row['WARRANTY END'])
        asset.save()
        assets_created.append(asset)

    return assets_created


def humanise_age(d):
    """Passed in a timedelta objects, this funciton returns a nice age like "25 days" or
    "3 months", with appropriate resolution.
    """
    if d.days >= 730:
        years = d.days / 365
        months = (d.days - years * 365) / 30
        if months > 0:
            return "%d years, %d months" % (years, months)
        else:
            return "%d years" % (years)
    elif d.days >= 365:
        months = (d.days - 365) / 30
        if months > 0:
            return "1 year, %d months" % (months)
        else:
            return "1 year"
    elif d.days >= 60:
        return "%d months" % (d.days / 30)
    elif d.days >= 30:
        return "1 month"
    elif d.days >= 2:
        return "%d days" % (d.days)
    elif d.days == 1:
        return "1 day"
    elif d.seconds >= 7200:
        return "%d hours" % (d.seconds / 3600)
    elif d.seconds >= 3600:
        return "1 hour"
    elif d.seconds >= 120:
        return "%d minutes" % (d.seconds / 60)
    elif d.seconds >= 60:
        return "1 minute"
    elif d.seconds >= 2:
        return "%s seconds" % (d.seconds)
    elif d.seconds == 0:
        # Things exactly the same are probably date objects, so max. 1-day
        # resolution
        return "1 day"
    else:
        return "1 second"


def get_csv(qs):
    """Using a passed-in queryset of HardwareAsset objects, return a CSV.
    """
    f = BytesIO()
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, encoding='utf-8')
    writer.writerow([
        'ASSET TAG', 'FINANCE ASSET TAG', 'SERIAL', 'VENDOR', 'MODEL TYPE', 'HARDWARE MODEL',
        'STATUS', 'COST CENTRE', 'LOCATION', 'ASSIGNED USER', 'DATE PURCHASED',
        'PURCHASED VALUE', 'SERVICE REQUEST URL', 'LOCAL PROPERTY', 'IS ASSET',
        'WARRANTY END'])
    for i in qs:
        writer.writerow([
            i.asset_tag, i.finance_asset_tag, i.serial, i.vendor,
            i.hardware_model.get_model_type_display(), i.hardware_model, i.get_status_display(),
            i.cost_centre.code if i.cost_centre else '', i.location if i.location else '',
            i.assigned_user if i.assigned_user else '',
            datetime.strftime(i.date_purchased, '%d/%b/%Y') if i.date_purchased else '',
            i.purchased_value, i.service_request_url, i.local_property, i.is_asset,
            datetime.strftime(i.warranty_end, '%d/%b/%Y') if i.warranty_end else ''])
    return f
