from datetime import date, datetime, timedelta
from django.conf import settings
import logging
from collections import OrderedDict
import psycopg2
import pytz
import titlecase

TZ = pytz.timezone(settings.TIME_ZONE)
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


def alesco_scrub_title(title):
    # remove extra spaces
    title_raw = ' '.join(title.upper().split())

    # ranger job titles have too much junk attached, jettison!
    if title_raw.startswith('RANGER'):
        return 'Ranger'
    if title_raw.startswith('SENIOR RANGER'):
        return 'Senior Ranger'

    def replace(word, **kwargs):
        result = None
        prefix = ''
        suffix = ''
        if word.startswith('('):
            prefix = '('
            word = word[1:]
        if word.endswith(')'):
            suffix = ')'
            word = word[:-1]
        if word.upper() in ('RIA', 'DBCA', 'BGPA', 'ZPA', 'PVS', 'IT', 'ICT', 'AV', 'HR', 'GIS', 'FMDP', 'SFM', 'OIM', 'HAAMC', 'TEC', 'MATES', 'AWU', 'FOI', 'KABC', 'VOG', 'WSS', 'EDRMS', 'LUP', 'WA', 'KSCS', 'OT'):
            result = word.upper()
        else:
            expand = {
                '&': 'and',
                'BG': 'Botanic Garden',
                'DEPT': 'Department',
                'CONS': 'Conservation',
                'CONSER': 'Conservation',
                'CONSERV': 'Conservation',
                'COORD': 'Coordinator',
                'CO-ORDINATOR': 'Coordinator',
                'COORDIN': 'Coordinator',
                'CUST': 'Customer',
                'MGMT': 'Management',
                'NP': 'National Park',
                'OCC': 'Occupational',
                'SAF': 'Safety',
                'SRV': 'Service',
                'SNR': 'Senior',
                'SERVIC': 'Services',
                'SCIENT': 'Scientist',
                'SCIENT.': 'Scientist',
                'ODG': 'Office of the Director General',
                'CHAIRPERSON,': 'Chairperson -',
                'OFFICER,': 'Officer -',
                'DIRECTOR,': 'Director -',
                'LEADER,': 'Leader -',
                'MANAGER,': 'Manager -',
                'COORDINATOR,': 'Coordinator -',
            }
            if word.upper() in expand:
                result = expand[word.upper()]
        if result:
            return prefix + result + suffix

    title_fixed = titlecase.titlecase(title_raw, callback=replace)
    return title_fixed


def alesco_date_to_dt(dt, hour=0, minute=0, second=0):
    """Take in a date object and return it as a timezone-aware datetime.
    """
    d = TZ.localize(datetime(dt.year, dt.month, dt.day, 0, 0))
    return d + timedelta(hours=hour, minutes=minute, seconds=second)


def update_user_from_alesco(user):
    """Update a DepartmentUser object's field values from the data in the alesco_data field.
    """
    from .models import DepartmentUser
    term_date = None
    manager = None
    title = None
    changes = False

    if user.alesco_data:
        term_dates = [datetime.strptime(x['job_term_date'], '%Y-%m-%d') for x in user.alesco_data if x['job_term_date']]
        if term_dates:
            term_date = max(term_dates)
            # Convert the Alesco date to a timezone-aware datetime (use end of business hours).
            if term_date and term_date != ALESCO_DATE_MAX:
                term_date = alesco_date_to_dt(term_date, 17, 30)
            else:
                term_date = None
        managers = [x['manager_emp_no'] for x in user.alesco_data if x['manager_emp_no']]
        managers = OrderedDict.fromkeys(managers).keys()
        managers = [DepartmentUser.objects.filter(employee_id=x).first() for x in managers]
        managers = [x for x in managers if x and (user.pk != x.pk)]
        if managers:
            manager = managers[0]
        title = next((x['occup_pos_title'] for x in user.alesco_data if 'occup_pos_title' in x and x['occup_pos_title']), None)
        if title:
            title = alesco_scrub_title(title)

    if term_date:
        stored_term_date = TZ.normalize(user.date_hr_term) if user.date_hr_term else None
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

    if title:
        if title != user.title:
            LOGGER.info('Updating title for {} from {} to {}'.format(user.email, user.title, title))
            user.title = title
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


def alesco_db_import(update_dept_user=False):
    """A task to update DepartmentUser field values from Alesco database information.
    By default, it saves Alesco data in the alesco_data JSON field.
    If update_dept_user == True, the function will also update several other field values.
    """
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

    LOGGER.info('Querying Alesco database for employee information')
    for row in alesco_iter:
        record = dict(zip(ALESCO_DB_FIELDS, row))
        eid = record['employee_id']

        if eid not in records:
            records[eid] = []
        records[eid].append(record)

    LOGGER.info('Updating local DepartmentUser information from Alesco data')
    for key, record in records.items():
        if not DepartmentUser.objects.filter(employee_id=key).exists():
            continue

        # Perform some sorting to place the employee's Alesco record(s) in order from
        # most applicable to least applicable.
        record.sort(key=lambda x: classification_ranking.index(x['classification']) if x['classification'] in classification_ranking else 100)
        record.sort(key=lambda x: status_ranking.index(x['emp_status']) if x['emp_status'] in status_ranking else 100)
        record.sort(key=lambda x: x['job_term_date'], reverse=True)

        for r in record:
            for field in date_fields:
                r[field] = r[field].isoformat() if r[field] and r[field] != ALESCO_DATE_MAX else None

        user = DepartmentUser.objects.get(employee_id=key)
        user.alesco_data = record
        user.save()

        if update_dept_user:
            update_user_from_alesco(user)
