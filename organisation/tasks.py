import datetime
from django.conf import settings
import logging
from openpyxl import load_workbook
import psycopg2
import pytz


PERTH = pytz.timezone('Australia/Perth')
LOGGER = logging.getLogger('sync_tasks')


def alesco_data_import(fileobj):
    """Import task expects to be passed a file object (an uploaded .xlsx).
    """
    from .models import DepartmentUser
    LOGGER.info('Alesco data for DepartmentUsers is being updated')
    wb = load_workbook(fileobj, read_only=True)
    ws = wb.worksheets[0]
    keys = []
    values = []
    non_matched = 0
    multi_matched = 0
    updates = 0
    # Iterate over each row in the worksheet.
    for k, row in enumerate(ws.iter_rows()):
        values = []
        for cell in row:
            # First row: generate keys.
            if k == 0:
                keys.append(cell.value)
            # Otherwise make a list of values.
            else:
                # Serialise datetime objects.
                if isinstance(cell.value, datetime.datetime):
                    values.append(cell.value.isoformat())
                else:
                    values.append(cell.value)
        if k > 0:
            # Construct a dictionary of row values.
            record = dict(zip(keys, values))
            # Try to find a matching DepartmentUser by employee id.
            d = DepartmentUser.objects.filter(employee_id=record['EMPLOYEE_NO'])
            if d.count() > 1:
                multi_matched += 1
            elif d.count() == 1:
                d = d[0]
                d.alesco_data = record
                d.save()
                updates += 1
            else:
                non_matched += 0
    if updates > 0:
        LOGGER.info('Alesco data for {} DepartmentUsers was updated'.format(updates))
    if non_matched > 0:
        LOGGER.warning('Employee ID was not matched for {} rows'.format(non_matched))
    if multi_matched > 0:
        LOGGER.error('Employee ID was matched for >1 DepartmentUsers for {} rows'.format(multi_matched))
    return True


ALESCO_DB_FIELDS = (
    'employee_id', 'surname', 'initials', 'first_name', 'second_name', 'gender',
    'date_of_birth', 'occup_type', 'current_commence', 'job_term_date',
    'occup_commence_date', 'occup_term_date', 'position_id', 'occup_pos_title',
    'clevel1_id', 'clevel1_desc', 'clevel5_id', 'clevel5_desc', 'award',
    'classification', 'step_id', 'emp_status', 'emp_stat_desc',
    'location', 'location_desc', 'paypoint', 'paypoint_desc', 'manager_emp_no',
)
ALESCO_DATE_MAX = datetime.date(2049, 12, 31)


def alesco_db_fetch():
    """Returns an iterator which fields rows from a database query until completed.
    """
    conn = psycopg2.connect(
        host=settings.ALESCO_DB_HOST,
        database=settings.ALESCO_DB_NAME,
        user=settings.ALESCO_DB_USERNAME,
        password=settings.ALESCO_DB_PASSWORD
    )
    cur = conn.cursor()

    query = "SELECT {} FROM {};".format(', '.join(ALESCO_DB_FIELDS), settings.ALESCO_DB_TABLE)
    cur.execute(query)
    while True:
        row = cur.fetchone()
        if row is None:
            break
        yield row


def alesco_db_import():
    from .models import DepartmentUser

    date_fields = ['date_of_birth', 'current_commence', 'job_term_date', 'occup_commence_date', 'occup_term_date']

    status_ranking = [
        'PFAS', 'PFA', 'PFT', 'CFA', 'CFT', 'NPAYF',
        'PPA', 'PPT', 'CPA', 'CPT', 'NPAYP',
        'CCFA', 'CAS', 'SEAS', 'TRAIN', 'NOPAY', 'NON',
    ]

    classification_ranking = [
        'CEO', 'CL3', 'CL2', 'CL1',
        'L9', 'L8', 'L7',
        'SCL6', 'L6',
        'SCL5', 'L5',
        'SCL4', 'S4', 'L4',
        'SCL3', 'S3', 'L3',
        'SCL2', 'R2', 'L2',
        'SCL1', 'R1', 'L12', 'L1',
    ]

    date_to_dt = lambda d: PERTH.localize(datetime.datetime(d.year, d.month, d.day, 0, 0)) + datetime.timedelta(days=1)
    records = {}
    alesco_iter = alesco_db_fetch()

    for row in alesco_iter:

        record = dict(zip(ALESCO_DB_FIELDS, row))
        eid = record['employee_id']

        if eid not in records:
            records[eid] = []
        records[eid].append(record)

    users = []

    for key, record in records.items():
        record.sort(key=lambda x: classification_ranking.index(x['classification']) if x['classification'] in classification_ranking else 100)
        record.sort(key=lambda x: status_ranking.index(x['emp_status']) if x['emp_status'] in status_ranking else 100)
        record.sort(key=lambda x: x['job_term_date'], reverse=True)
        term_date = record[0]['job_term_date']
        term_date = date_to_dt(term_date) if term_date != ALESCO_DATE_MAX else None

        for rec in record:
            for field in date_fields:
                rec[field] = rec[field].isoformat() if rec[field] and rec[field] != ALESCO_DATE_MAX else None

        user = DepartmentUser.objects.filter(employee_id=key).first()

        if not user:
            continue

        user.alesco_data = record

        if term_date:
            expiry_date = PERTH.normalize(user.expiry_date) if user.expiry_date else None
            if term_date != expiry_date:
                print('Updating expiry for {} from {} to {}'.format(user.email, expiry_date, term_date))

        user.save()
        users.append(user)

    return users
