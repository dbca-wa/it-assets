from datetime import date, datetime, timedelta
from django.conf import settings
import logging
from collections import OrderedDict
import psycopg2
import pytz

PERTH = pytz.timezone('Australia/Perth')
LOGGER = logging.getLogger('sync_tasks')
ALESCO_DB_FIELDS = (
    'employee_id', 'surname', 'initials', 'first_name', 'second_name', 'gender',
    'date_of_birth', 'occup_type', 'current_commence', 'job_term_date',
    'occup_commence_date', 'occup_term_date', 'position_id', 'occup_pos_title',
    'clevel1_id', 'clevel1_desc', 'clevel5_id', 'clevel5_desc', 'award',
    'classification', 'step_id', 'emp_status', 'emp_stat_desc',
    'location', 'location_desc', 'paypoint', 'paypoint_desc', 'manager_emp_no',
)
ALESCO_DATE_MAX = date(2049, 12, 31)


def alesco_date_to_dt(dt, hour=0, minute=0, second=0):
    """Take in a date object and return it as a localised datetime.
    Reason: Alesco date has no timestamp, so we convert a date to datetime at end of business hours.
    """
    d = PERTH.localize(datetime(dt.year, dt.month, dt.day, 0, 0))
    return d + timedelta(hours=hour, minutes=minute, seconds=second)


def update_user_from_alesco(user):
    from .models import DepartmentUser
    term_date = None
    manager = None
    changes = False

    if user.alesco_data:
        term_dates = [datetime.strptime(x['job_term_date'], '%Y-%m-%d') for x in user.alesco_data if x['job_term_date']]
        if term_dates:
            term_date = max(term_dates)
            term_date = alesco_date_to_dt(term_date, 17, 30) if term_date and term_date != ALESCO_DATE_MAX else None
        managers = [x['manager_emp_no'] for x in user.alesco_data if x['manager_emp_no']]
        managers = OrderedDict.fromkeys(managers).keys()
        managers = [DepartmentUser.objects.filter(employee_id=x).first() for x in managers]
        managers = [x for x in managers if x and (user.pk != x.pk)]
        if managers:
            manager = managers[0]

    if term_date:
        stored_term_date = PERTH.normalize(user.date_hr_term) if user.date_hr_term else None
        if term_date != stored_term_date:

            if user.hr_auto_expiry:
                LOGGER.info('Updating expiry for {} from {} to {}'.format(user.email, stored_term_date, term_date))
                user.expiry_date = term_date
            user.date_hr_term = term_date
            changes = True

    if manager:
        if manager != user.parent:
            LOGGER.info('Updating manager for {} from {} to {}'.format(user.email, user.parent.email if user.parent else None, manager.email if manager else None))
            user.parent = manager
            changes = True

    if changes:
        user.save()


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
        if not DepartmentUser.objects.filter(employee_id=key).exists():
            continue

        record.sort(key=lambda x: classification_ranking.index(x['classification']) if x['classification'] in classification_ranking else 100)
        record.sort(key=lambda x: status_ranking.index(x['emp_status']) if x['emp_status'] in status_ranking else 100)
        record.sort(key=lambda x: x['job_term_date'], reverse=True)

        for rec in record:
            for field in date_fields:
                rec[field] = rec[field].isoformat() if rec[field] and rec[field] != ALESCO_DATE_MAX else None

        user = DepartmentUser.objects.get(employee_id=key)
        user.alesco_data = record
        user.save()
        update_user_from_alesco(user)
        users.append(user)

    return users
