from datetime import date, datetime, timedelta
import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
import logging
from collections import OrderedDict
import psycopg2
import pytz
import titlecase

TZ = pytz.timezone(settings.TIME_ZONE)
logger = logging.getLogger(__name__)

ALESCO_DATE_MAX = date(2049, 12, 31)

FOREIGN_TABLE_FIELDS = (
    ('employee_no','employee_id'),'job_no', 'surname', 'first_name', 'second_name', 'gender',
    ('date_of_birth',lambda record,val: val.isoformat() if val else None), 
    'clevel1_id','clevel1_desc','clevel2_desc','clevel3_desc','clevel4_desc','clevel5_desc',
    'position_no','occup_pos_title','award','award_desc','emp_status','emp_stat_desc',
    'location',('loc_desc','location_desc'),'paypoint',
    'paypoint_desc','geo_location_desc',
    'occup_type',
    ('job_start_date',lambda record,val:val.strftime("%Y-%m-%d") if val and val != ALESCO_DATE_MAX else None),
    ('occup_term_date','job_term_date',lambda record,val: val.strftime("%Y-%m-%d") if val and val != ALESCO_DATE_MAX else None),
    'term_reason',('manager_emp_no','manager_employee_no')
)

FOREIGN_DB_QUERY_SQL = "SELECT {} FROM \"{}\".\"{}\" ORDER BY employee_no;".format(
    ', '.join(f[0] if isinstance(f,(list,tuple)) else f for f in FOREIGN_TABLE_FIELDS if (f[0] if isinstance(f,(list,tuple)) else f)),
    settings.FOREIGN_SCHEMA,
    settings.FOREIGN_TABLE)

FOREIGN_TABLE_SQL="""
CREATE FOREIGN TABLE "{foreign_schema}"."{foreign_table}" (
 employee_no  VARCHAR(8),
 job_no 	  VARCHAR(2),
 surname      VARCHAR(50),
 first_name   VARCHAR(50),
 second_name  VARCHAR(16),
 date_of_birth DATE,
 gender        VARCHAR(1),
 clevel1_id    VARCHAR(50),
 clevel1_desc  VARCHAR(50),
 clevel2_desc  VARCHAR(50),
 clevel3_desc  VARCHAR(50),
 clevel4_desc  VARCHAR(50),
 clevel5_desc  VARCHAR(50),
 position_no   VARCHAR(10),
 occup_pos_title VARCHAR(100),
 award  VARCHAR(5),
 award_desc  VARCHAR(50),
 emp_status  VARCHAR(5),
 emp_stat_desc VARCHAR(50),
 location VARCHAR(5),
 loc_desc  VARCHAR(50),
 paypoint  VARCHAR(5),
 paypoint_desc  VARCHAR(50),
 geo_location_desc VARCHAR(50),
 occup_type   VARCHAR(5),
 job_start_date DATE,
 manager_emp_no VARCHAR(8),
 occup_term_date  DATE,
 term_reason VARCHAR(5)
) SERVER {foreign_server} OPTIONS (schema '{alesco_db_schema}', table '{alesco_db_table}');
"""

status_ranking = [
    'PFAS', 'PFA', 'PFT', 'CFA', 'CFT', 'NPAYF',
    'PPA', 'PPT', 'CPA', 'CPT', 'NPAYP',
    'CCFA', 'CAS', 'SEAS', 'TRAIN', 'NOPAY', 'NON',
]
def alesco_job_sort_key(record):
    """
    Sort the job based the score
    1.the initial score is based on the job's terminate date
        if the job is terminated, the initial score is populated from the job's terminate date
      if the job is not terminated , the initial score is populated from tommorrow, that means all not terminated jobs have the same initial score 
    2.secondary score is based on emp_status
    """
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    #initial score from occup_term_date
    score = (int(record["job_term_date"].replace("-","")) * 10000) if record["job_term_date"] and record["job_term_date"] <= today.strftime("%Y-%m-%d") else int(tomorrow.strftime("%Y%m%d0000"))
    #second score based emp_status
    score += ((status_ranking.index(record['emp_status']) + 1) if (record['emp_status'] in status_ranking) else 0) * 100
    return score

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

def get_column_from_alesco(jobs,column):
    if not jobs:
        return None

    if not jobs[0][column]:
        return None
    return jobs[0].get(column,None)

def get_employeeid_from_alesco(jobs):
    return get_column_from_alesco(jobs,'employee_id')


def get_manager_from_alesco(user,jobs):
    from ..models import DepartmentUser
    if not jobs:
        return None

    today = datetime.now().date().strftime("%Y-%m-%d")
    for job in jobs:
        if job["job_term_date"] and job["job_term_date"] < today:
            continue
        manager_employee_no = job.get("manager_employee_no")
        if manager_employee_no:
            try:
                manager = DepartmentUser.objects.get(employee_id=manager_employee_no)
                if user and manager.pk == user.pk:
                    logger.debug("The manager of the user({0}.{1}) is himself/herself".format(get_firstname_from_alesco(jobs),get_surname_from_alesco(jobs)))
                else:
                    return manager
            except ObjectDoesNotExist as ex:
                logger.error("The manager({2}) of the user({0}.{1}) doesn't exist".format(get_firstname_from_alesco(jobs),get_surname_from_alesco(jobs),manager_employee_no))
                

    return None

def get_term_datetime_from_alesco(jobs):
    term_date = get_column_from_alesco(jobs,'job_term_date')
    term_date = TZ.localize(datetime.strptime(term_date,"%Y-%m-%d")) if term_date else None

def get_occup_pos_title_from_alesco(jobs):
    title = get_column_from_alesco(jobs,'occup_pos_title')
    return alesco_scrub_title(title) if title else None

def get_location_from_alesco(jobs):
    from ..models import Location
    location = get_column_from_alesco(jobs,'location')
    if location:
         loc = Location.objects.filter(ascender_code=location).first()
         if loc:
             return loc
         else:
            logger.error("The location({2}) of the user({0}.{1}) doesn't exist".format(get_firstname_from_alesco(jobs),get_surname_from_alesco(jobs),location))
            return None
    else:
        return None

def get_location_desc_from_alesco(jobs):
    return get_column_from_alesco(jobs,'location_desc')

def get_surname_from_alesco(jobs):
    return get_column_from_alesco(jobs,'surname')

def get_firstname_from_alesco(jobs):
    return get_column_from_alesco(jobs,'first_name')

def get_paypoint_from_alesco(jobs):
    return get_column_from_alesco(jobs,'paypoint')

def get_gender_from_alesco(jobs):
    return get_column_from_alesco(jobs,'gender')

def update_manager_from_alesco(user,update_fields=[],commit=True):
    manager = get_manager_from_alesco(user,user.alesco_data)

    if manager:
        if manager != user.parent:
            if manager in user.get_descendants():
                logger.info('Removing manager relationship from {}, should be fixed next cycle'.format(manager.email))
                manager.parent = None
                manager.save(update_fields=["parent"])

            logger.info('Updating manager for {} from {} to {}'.format(user.email, user.parent.email if user.parent else None, manager.email if manager else None))
            user.parent = manager
            update_fields.append("parent")
    if update_fields and commit:
        user.save(update_fields=update_fields)

def update_term_date_from_alesco(user,update_fields=[],commit=True):
    term_date = get_term_datetime_from_alesco(user.alesco_data)

    if term_date:
        stored_term_date = TZ.normalize(user.date_hr_term) if user.date_hr_term else None
        if term_date != stored_term_date:
            if user.hr_auto_expiry:
                logger.info('Updating expiry for {} from {} to {}'.format(user.email, stored_term_date, term_date))
                user.expiry_date = term_date
                update_fields.append("expiry_date")
            user.date_hr_term = term_date
            update_fields.append("date_hr_term")
    if update_fields and commit:
        user.save(update_fields=update_fields)


def update_user_data_from_alesco(user,property_name,f_get_data,update_fields=[],commit=True):
    data = f_get_data(user.alesco_data)

    if data:
        if data != getattr(user,property_name):
            logger.info('Updating {1} for {0} from {2} to {3}'.format(user.email,property_name, getattr(user,property_name), data))
            setattr(user,property_name,data)
            update_fields.append(property_name)
            if commit:
                user.save(update_fields=update_fields)
    if update_fields and commit:
        user.save(update_fields=update_fields)

def update_title_from_alesco(user,update_fields=[],commit=True):
    update_user_data_from_alesco(user,"title",get_occup_pos_title_from_alesco,update_fields=update_fields,commit=commit)

def update_location_from_alesco(user,update_fields=[],commit=True):
    update_user_data_from_alesco(user,"location",get_location_from_alesco,update_fields=update_fields,commit=commit)

def update_surname_from_alesco(user,update_fields=[],commit=True):
    update_user_data_from_alesco(user,"surname",get_surname_from_alesco,update_fields=update_fields,commit=commit)

def update_firstname_from_alesco(user,update_fields=[],commit=True):
    update_user_data_from_alesco(user,"given_name",get_firstname_from_alesco,update_fields=update_fields,commit=commit)

def update_user_from_alesco(user,update_fields=[]):
    #if user.employee_id == '003072':
    #    import ipdb;ipdb.set_trace()
    update_manager_from_alesco(user,update_fields=update_fields,commit=False)
    update_term_date_from_alesco(user,update_fields=update_fields,commit=False)
    update_title_from_alesco(user,update_fields=update_fields,commit=False)

    #update_surname_from_alesco(user,update_fields=update_fields,commit=False)
    #update_firstname_from_alesco(user,update_fields=update_fields,commit=False)

    update_location_from_alesco(user,update_fields=update_fields,commit=True)

def alesco_db_connection():
    return psycopg2.connect(
        host=settings.FOREIGN_DB_HOST,
        port=settings.FOREIGN_DB_PORT,
        database=settings.FOREIGN_DB_NAME,
        user=settings.FOREIGN_DB_USERNAME,
        password=settings.FOREIGN_DB_PASSWORD
    )


def alesco_db_fetch():
    """
    Returns an iterator which fields rows from a database query until completed.
    """
    conn = alesco_db_connection()
    cur = None
    try:
        cur = conn.cursor()
    
        cur.execute(FOREIGN_DB_QUERY_SQL)
        record = None
        fields =  len(FOREIGN_TABLE_FIELDS)
        while True:
            row = cur.fetchone()
            if row is None:
                break
            index = 0
            record = {}
            while index < fields:
                column = FOREIGN_TABLE_FIELDS[index]
                if isinstance(column,(list,tuple)):
                    if callable(column[-1]):
                        if len(column) == 2:
                            record[column[0]] = column[-1](record,row[index])
                        else:
                            record[column[1]] = column[-1](record,row[index])
                    else:
                        record[column[1]] = row[index]
                else:
                    record[column] = row[index]
    
                index += 1
            yield record
    except:
        if cur:
            try:
                cur.close()
            except:
                logger.error(traceback.format_exc())

        if conn:
            try:
                conn.close()
            except:
                logger.error(traceback.format_exc())

def alesco_employee_fetch():
    """
    Returns an iterator to navigate (employee_id,sorted employee jobs)
    """
    alesco_iter = alesco_db_fetch()
    employee_id = None
    records = None
    for record in alesco_iter:
        if employee_id is None:
            employee_id = record["employee_id"]
            records = [record]
        elif employee_id == record["employee_id"]:
            records.append(record)
        else:
            if len(records) > 1:
                records.sort(key=alesco_job_sort_key,reverse=True)
            yield (employee_id,records)
            employee_id = record["employee_id"]
            records = [record]
    if employee_id and records:
        if len(records) > 1:
            records.sort(key=alesco_job_sort_key,reverse=True)
        yield (employee_id,records)


def alesco_db_import(update_dept_user=False):
    """A task to update DepartmentUser field values from Alesco database information.
    By default, it saves Alesco data in the alesco_data JSON field.
    If update_dept_user == True, the function will also update several other field values.
    """
    from ..models import DepartmentUser

    records = {}
    employee_iter = alesco_employee_fetch()
    today = date.today()

    logger.info('Querying Alesco database for employee information')
    for eid,jobs in employee_iter:
        try:
            user = DepartmentUser.objects.get(employee_id=eid)
            user.alesco_data = jobs
            update_fields = ["alesco_data"]
            if update_dept_user:
                update_user_from_alesco(user,update_fields=update_fields)
            else:
                user.save(update_fields=update_fields)
        except ObjectDoesNotExist as ex:
            continue

def departmentuser_alesco_descrepancy(users):
    """This function is used to find the data differences between the
    Alesco database and the IT Assets database.
    """
    discrepancies = {}
    alesco_records = {}
    employee_iter = alesco_employee_fetch()

    def _is_diff(name,data_from_alesco,data_from_user):
        if not data_from_alesco:
            #no data in alesco, skip
            return False
        elif name == "cost_centre":
            if data_from_alesco[0] == 'K':
                # NOTE: skip every Alesco CC starting with K (they all differ).
                return False

            if not data_from_user :
                return True

            # If the CC in Alesco start with R or Z, remove that starting letter before comparing.
            if data_from_alesco[0] in ['R', 'Z']:
                data = data_from_alesco[1:]
            else:
                data = data_from_alesco

            return data not in (data_from_user.code or [])

        elif not data_from_user:
            return False
        elif name == "location.name":
            return data_from_alesco.lower() not in data_from_user.lower()
        elif name in ("date_hr_term","expiry_date"):
            return data_from_alesco.date() != data_from_user.date
        elif isinstance(data_from_alesco,str):
            return data_from_alesco.lower() != data_from_user.lower()
        else:
            return data_from_alesco != data_from_user

    def _get_user_data(user,property_name):
        if "." in property_name:
            property_name = property_name.split(".")
            data = user
            for key in property_name:
                if not data:
                    return None
                data = getattr(data,key)

            return data

        else:
            return getattr(user,property_name)

    for eid, jobs in employee_iter:
        user = None
        try:
            user = users.get(employee_id=eid)
        except ObjectDoesNotExist as ex:
            continue

        for property_name,f_get_data in [
            ("surname",get_surname_from_alesco),
            ("given_name",get_firstname_from_alesco),
            ("title",get_occup_pos_title_from_alesco),
            ("expiry_date",get_term_datetime_from_alesco) if user.hr_auto_expiry else (None,None),
            ("date_hr_term",get_term_datetime_from_alesco),
            ("cost_centre",get_paypoint_from_alesco) ,
            ("location",get_location_from_alesco),
            ("location.name",get_location_desc_from_alesco)

        ]:
            if not property_name:
                continue
            data = f_get_data(jobs)
            if data:
                property_data = _get_user_data(user,property_name)
                if _is_diff(property_name,data,property_data):
                    if eid not in discrepancies:
                        discrepancies[eid] = []
                    discrepancies[eid].append(
                        (
                            user.get_full_name(),
                            'Column({}) mismatch'.format(property_name),
                            str(data),
                            str(property_data)
                        )
                    )

    return discrepancies


def print_records(file_name=None,f_filter=None):
    from ..models import DepartmentUser
    employee_iter = alesco_employee_fetch()

    f = None
    if file_name:
        f = open(file_name,'w')
        writer = f.write
        def _writer(s):
            f.write(s)
            f.write(os.linesep)
    else:
        _writer = print
    try:   
        for eid, jobs in employee_iter:
            if f_filter and not f_filter(eid,jobs):
                continue

            user=None
            try:
                user = DepartmentUser.objects.get(employee_id=eid)
            except ObjectDoesNotExist as ex:
                continue

            manager = get_manager_from_alesco(user,jobs)
            _writer("employee_id={}, manager employee id={},paypoint={},location={},location desc={},job term date={}".format(
                eid,
                manager.employee_id if manager else None,
                get_paypoint_from_alesco(jobs),
                get_location_from_alesco(jobs),
                get_location_desc_from_alesco(jobs),
                get_term_datetime_from_alesco(jobs)
            ))
            for job in jobs:
                _writer("    score={} job_term_date={}, emp_status={}, surname={}, given_name={}, title={}, gender={}, paypoint={},location={}, location_desc={}, manager emplyee no={}".format(
                    alesco_job_sort_key(job),
                    job["job_term_date"],
                    job["emp_status"],
                    job["surname"],
                    job["first_name"],
                    job["occup_pos_title"],
                    job["gender"],
                    job["paypoint"],
                    job["location"],
                    job["location_desc"],
                    job["manager_employee_no"]
                ))
            _writer("")
    finally:
        if f:
            f.close()

