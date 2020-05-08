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
                'CON': 'Conservation',
                'CONS': 'Conservation',
                'CONSER': 'Conservation',
                'CONSERV': 'Conservation',
                'COORD': 'Coordinator',
                'CO-ORDINATOR': 'Coordinator',
                'COORDIN': 'Coordinator',
                'CUST': 'Customer',
                'MGMT': 'Management',
                'IS': 'Island',
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


def update_manager_from_alesco(user):
    from .models import DepartmentUser
    manager = None

    if user.alesco_data:
        managers = [x['manager_emp_no'] for x in user.alesco_data if x['manager_emp_no']]
        managers = OrderedDict.fromkeys(managers).keys()
        managers = [DepartmentUser.objects.filter(employee_id=x).first() for x in managers]
        managers = [x for x in managers if x and (user.pk != x.pk)]
        if managers:
            manager = managers[0]

    if manager:
        if manager != user.parent:
            if manager in user.get_descendants():
                LOGGER.info('Removing manager relationship from {}, should be fixed next cycle'.format(manager.email))
                manager.parent = None
                manager.save()

            LOGGER.info('Updating manager for {} from {} to {}'.format(user.email, user.parent.email if user.parent else None, manager.email if manager else None))
            user.parent = manager
            user.save()


def update_term_date_from_alesco(user):
    term_date = None

    if user.alesco_data:
        term_dates = [date.fromisoformat(x['job_term_date']) for x in user.alesco_data if x['job_term_date']]
        if term_dates:
            term_date = max(term_dates)
            term_date = alesco_date_to_dt(term_date) if term_date and term_date != ALESCO_DATE_MAX else None

    if term_date:
        stored_term_date = TZ.normalize(user.date_hr_term) if user.date_hr_term else None
        if term_date != stored_term_date:

            if user.hr_auto_expiry:
                LOGGER.info('Updating expiry for {} from {} to {}'.format(user.email, stored_term_date, term_date))
                user.expiry_date = term_date
            user.date_hr_term = term_date
            user.save()


def update_title_from_alesco(user):
    title = None

    if user.alesco_data:
        title = next((x['occup_pos_title'] for x in user.alesco_data if 'occup_pos_title' in x and x['occup_pos_title']), None)
        if title:
            title = alesco_scrub_title(title)

    if title:
        if title != user.title:
            LOGGER.info('Updating title for {} from {} to {}'.format(user.email, user.title, title))
            user.title = title
            user.save()


def update_location_from_alesco(user):
    from .models import Location
    location = None

    if user.alesco_data:
        location = next((x['location'] for x in user.alesco_data if 'location' in x and x['location']), None)
        location = Location.objects.filter(ascender_code=location).first()

    if location:
        if location != user.location:
            LOGGER.info('Updating location for {} from {} to {}'.format(user.email, user.location, location))
            user.location = location
            user.save()


def update_user_from_alesco(user):
    update_manager_from_alesco(user)
    update_term_date_from_alesco(user)
    update_title_from_alesco(user)
    update_location_from_alesco(user)


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
    today = date.today()

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
        # start off by current jobs sorted by rank, follow up by chronological list of expired jobs
        current = [x for x in record if x['job_term_date'] is None or x['job_term_date'] >= today]
        expired = [x for x in record if x['job_term_date'] and x['job_term_date'] < today]
        expired.sort(key=lambda x: x['job_term_date'], reverse=True)
        record = current + expired

        for rec in record:
            for field in date_fields:
                rec[field] = rec[field].isoformat() if rec[field] and rec[field] != ALESCO_DATE_MAX else None

        user = DepartmentUser.objects.get(employee_id=key)
#        order = lambda obj: tuple([x['position_id'] for x in obj])
#        if order(user.alesco_data) != order(record):
#            print('Changing {}'.format(user.email))
#            print([(x['classification'], x['emp_stat_desc'], x['occup_pos_title'], x['job_term_date']) for x in user.alesco_data])
#            print([(x['classification'], x['emp_stat_desc'], x['occup_pos_title'], x['job_term_date']) for x in record])

        user.alesco_data = record
        user.save()

        if update_dept_user:
            update_user_from_alesco(user)

def departmentuser_alesco_descrepancy(users):
    """This function is used to find the data differences between the
    Alesco database and the IT Assets database.
    """
    discrepancies = {}
    alesco_records = {}
    alesco_iter = alesco_db_fetch()

    # Get Alesco data.
    for row in alesco_iter:
        record = dict(zip(ALESCO_DB_FIELDS, row))
        eid = record['employee_id']

        if eid not in alesco_records:
            alesco_records[eid] = []
        alesco_records[eid].append(record)

    for key, record in alesco_records.items():
        if not users.filter(employee_id=key).exists():
            continue
        else:
            user = users.get(employee_id=key)
            alesco_record = record[0]  # GROSS ASSUMPTION: the first Alesco record in the list is the newest/most current.

        # Commenting out the check of first name to exclude the many false positives (e.g. Tom != Thomas)
        #if user.given_name:
        #    if alesco_record['first_name'].lower() != user.given_name.lower():
        #        if key not in discrepancies:
        #            discrepancies[key] = []
        #        discrepancies[key].append(
        #            (
        #                user.get_full_name(),
        #                'Given name mismatch',
        #                alesco_record['first_name'],
        #                user.given_name
        #            )
        #        )

        if user.surname:
            if alesco_record['surname'].lower() != user.surname.lower():
                if key not in discrepancies:
                    discrepancies[key] = []
                discrepancies[key].append(
                    (
                        user.get_full_name(),
                        'Surname mismatch',
                        alesco_record['surname'],
                        user.surname
                    )
                )

        if user.title:
            if alesco_record['occup_pos_title'].lower() != user.title.lower():
                if key not in discrepancies:
                    discrepancies[key] = []
                discrepancies[key].append(
                    (
                        user.get_full_name(),
                        'Title mismatch',
                        alesco_record['occup_pos_title'],
                        user.title
                    )
                )

        if user.expiry_date:
            if alesco_record['job_term_date'] != user.expiry_date.date():
                if key not in discrepancies:
                    discrepancies[key] = []
                discrepancies[key].append(
                    (
                        user.get_full_name(),
                        'Expiry date mismatch',
                        alesco_record['job_term_date'].strftime('%d/%b/%Y'),
                        user.expiry_date.strftime('%d/%b/%Y')
                    )
                )

        # NOTE: skip every Alesco CC starting with K (they all differ).
        if user.cost_centre and alesco_record['paypoint'] and alesco_record['paypoint'][0] != 'K':
            # If the CC in Alesco start with R or Z, remove that starting letter before comparing.
            if alesco_record['paypoint'][0] in ['R', 'Z']:
                alesco_cc = alesco_record['paypoint'][1:]
            else:
                alesco_cc = alesco_record['paypoint']
            if alesco_cc not in user.cost_centre.code:
                if key not in discrepancies:
                    discrepancies[key] = []
                discrepancies[key].append(
                    (
                        user.get_full_name(),
                        'Cost centre mismatch',
                        alesco_record['paypoint'],
                        user.cost_centre.code
                    )
                )

        if user.location and alesco_record['location_desc']:
            if alesco_record['location_desc'].lower() not in user.location.name.lower():
                if key not in discrepancies:
                    discrepancies[key] = []
                discrepancies[key].append(
                    (
                        user.get_full_name(),
                        'Location mismatch',
                        alesco_record['location_desc'],
                        user.location.name
                    )
                )
        # TODO: Manager

    return discrepancies


