from datetime import date, datetime, timedelta
from django.conf import settings
from fuzzywuzzy import fuzz
import psycopg2
import pytz
from organisation.models import DepartmentUser

TZ = pytz.timezone(settings.TIME_ZONE)
DATE_MAX = date(2049, 12, 31)
# The list below defines which columns to SELECT from the Ascender view, what to name the object
# dict key after querying, plus how to parse the returned value of each column (if required).
FOREIGN_TABLE_FIELDS = (
    ("employee_no", "employee_id"),
    "job_no",
    "surname",
    "first_name",
    "second_name",
    "preferred_name",
    "clevel1_id",
    "clevel1_desc",
    "clevel2_desc",
    "clevel3_desc",
    "clevel4_desc",
    "clevel5_desc",
    "position_no",
    "occup_pos_title",
    "award",
    "award_desc",
    "emp_status",
    "emp_stat_desc",
    ("loc_desc", "location_desc"),
    "paypoint",
    "paypoint_desc",
    "geo_location_desc",
    "occup_type",
    ("job_start_date", lambda record, val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None),
    ("occup_term_date", "job_term_date", lambda record, val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None),
    "term_reason",
    "work_phone_no",
    "work_mobile_phone_no",
)
FOREIGN_DB_QUERY_SQL = 'SELECT {} FROM "{}"."{}" ORDER BY employee_no;'.format(
    ", ".join(
        f[0] if isinstance(f, (list, tuple)) else f for f in FOREIGN_TABLE_FIELDS if (f[0] if isinstance(f, (list, tuple)) else f)
    ),
    settings.FOREIGN_SCHEMA,
    settings.FOREIGN_TABLE,
)
STATUS_RANKING = [
    "PFAS",
    "PFA",
    "PFT",
    "CFA",
    "CFT",
    "NPAYF",
    "PPA",
    "PPT",
    "CPA",
    "CPT",
    "NPAYP",
    "CCFA",
    "CAS",
    "SEAS",
    "TRAIN",
    "NOPAY",
    "NON",
]


def ascender_db_fetch():
    """
    Returns an iterator which yields rows from a database query until completed.
    """
    conn = psycopg2.connect(
        host=settings.FOREIGN_DB_HOST,
        port=settings.FOREIGN_DB_PORT,
        database=settings.FOREIGN_DB_NAME,
        user=settings.FOREIGN_DB_USERNAME,
        password=settings.FOREIGN_DB_PASSWORD,
    )
    cur = None

    cur = conn.cursor()
    cur.execute(FOREIGN_DB_QUERY_SQL)
    record = None
    fields = len(FOREIGN_TABLE_FIELDS)

    while True:
        row = cur.fetchone()
        if row is None:
            break
        index = 0
        record = {}
        while index < fields:
            column = FOREIGN_TABLE_FIELDS[index]
            if isinstance(column, (list, tuple)):
                if callable(column[-1]):
                    if len(column) == 2:
                        record[column[0]] = column[-1](record, row[index])
                    else:
                        record[column[1]] = column[-1](record, row[index])
                else:
                    record[column[1]] = row[index]
            else:
                record[column] = row[index]

            index += 1
        yield record


def ascender_job_sort_key(record):
    """
    Sort the job based the score
    1.the initial score is based on the job's terminate date
      if the job is terminated, the initial score is populated from the job's terminate date
      if the job is not terminated , the initial score is populated from tommorrow, that means all not terminated jobs have the same initial score
    2.secondary score is based on emp_status
    """
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    # Initial score from occup_term_date
    score = (
        (int(record["job_term_date"].replace("-", "")) * 10000)
        if record["job_term_date"]
        and record["job_term_date"] <= today.strftime("%Y-%m-%d")
        else int(tomorrow.strftime("%Y%m%d0000"))
    )
    # Second score based emp_status
    score += (
        (STATUS_RANKING.index(record["emp_status"]) + 1)
        if (record["emp_status"] in STATUS_RANKING) else 0
    ) * 100
    return score


def ascender_employee_fetch():
    """Returns an iterator to navigate (employee_id,sorted employee jobs)
    """
    ascender_iter = ascender_db_fetch()
    employee_id = None
    records = None
    for record in ascender_iter:
        if employee_id is None:
            employee_id = record["employee_id"]
            records = [record]
        elif employee_id == record["employee_id"]:
            records.append(record)
        else:
            if len(records) > 1:
                records.sort(key=ascender_job_sort_key, reverse=True)
            yield (employee_id, records)
            employee_id = record["employee_id"]
            records = [record]
    if employee_id and records:
        if len(records) > 1:
            records.sort(key=ascender_job_sort_key, reverse=True)
        yield (employee_id, records)


def ascender_db_import():
    """A task to update DepartmentUser field values from Ascender database information.
    By default, it saves Ascender data in the ascender_data JSON field.
    If update_dept_user == True, the function will also update several other field values.
    """
    employee_iter = ascender_employee_fetch()

    for eid, jobs in employee_iter:
        # ASSUMPTION: the "first" object in the list of Alesco jobs for each user is the current one.
        job = jobs[0]
        if DepartmentUser.objects.filter(employee_id=eid).exists():
            user = DepartmentUser.objects.get(employee_id=eid)
            # Don't just replace the ascender_data dict; we also use it for audit purposes.
            for key, val in job.items():
                user.ascender_data[key] = val
            user.ascender_data_updated = TZ.localize(datetime.now())
            user.save()


def get_ascender_matches():
    """For users with no employee ID, return a list of lists of possible Ascender matches in the format:
    [IT ASSETS PK, IT ASSETS NAME, ASCENDER NAME, EMPLOYEE ID]
    """
    dept_users = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER, employee_id__isnull=True)
    ascender_data = ascender_employee_fetch()
    possible_matches = []
    ascender_jobs = []

    for eid, jobs in ascender_data:
        ascender_jobs.append(jobs[0])

    for user in dept_users:
        for data in ascender_jobs:
            if data['first_name'] and data['surname']:
                sn_ratio = fuzz.ratio(user.surname.upper(), data['surname'].upper())
                fn_ratio = fuzz.ratio(user.given_name.upper(), data['first_name'].upper())
                if sn_ratio > 70 and fn_ratio > 50:
                    possible_matches.append([
                        user.pk,
                        user.get_full_name(),
                        '{} {}'.format(data['first_name'], data['surname']),
                        data['employee_id'],
                    ])

    return possible_matches
