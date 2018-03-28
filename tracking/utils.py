import csv
from django.conf import settings
import logging
import os
import subprocess


def logger_setup(name):
    # Ensure that the logs dir is present.
    subprocess.check_call(['mkdir', '-p', 'logs'])
    # Set up logging in a standardised way.
    logger = logging.getLogger(name)
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:  # Log at a higher level when not in debug mode.
        logger.setLevel(logging.INFO)
    if not len(logger.handlers):  # Avoid creating duplicate handlers.
        fh = logging.handlers.RotatingFileHandler(
            'logs/{}.log'.format(name), maxBytes=5 * 1024 * 1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def sourcefile_setup(sourcefile):
    """Read source CSV data (from source_files dir), return a csvreader object
    and a count of the rows. Assumes that data has a header.
    """
    source = os.path.join(settings.BASE_DIR, 'source_files', sourcefile)
    csvfile = open(source, 'r')
    csvcounter = csv.reader(csvfile)
    row_count = sum(1 for row in csvcounter) - 1  # Read the file to count rows
    csvfile.close()
    # Reopen the CSV.
    csvfile = open(source, 'r')
    csvreader = csv.reader(csvfile)
    csvreader.next()  # Skip the headers row.
    return csvreader, row_count


def csv_sync_prop_register_data(src='it_assets.csv'):
    """Utility function to import local property register data from a CSV file
    (called it_assets.csv by default) saved in the source_files dir.

    Matches on serial number, should be non-destructive of existing data.
    """
    from .models import Computer
    data, count = sourcefile_setup(src)

    for i in data:
        serial = i[0].strip().upper()  # We save uppercase serials in the db.
        if serial:  # Non-blanks
            comps = Computer.objects.filter(serial_number=serial)
        else:
            comps = None
        if comps:
            # Cope with having duplicate serial numbers in Incredibus.
            for c in comps:
                if i[1]:  # Cost centre no.
                    c.cost_centre_no = int(i[1])
                c.save()
                print('Updated {}'.format(c))

    print('Done')
