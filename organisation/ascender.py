import logging
import secrets
from datetime import date, datetime

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from psycopg import connect, sql

from itassets.utils import ms_graph_client_token
from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import AscenderActionLog, CostCentre, DepartmentUser, DepartmentUserLog, Location
from organisation.utils import ms_graph_subscribed_sku, ms_graph_validate_password, title_except

LOGGER = logging.getLogger("organisation")
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
    "loc_desc",
    "paypoint",
    "paypoint_desc",
    "geo_location_desc",
    "occup_type",
    (
        "job_start_date",
        lambda val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None,
    ),
    (
        "job_end_date",
        lambda val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None,
    ),
    "term_reason",
    "work_phone_no",
    "work_mobile_phone_no",
    "email_address",
    "extended_lv",
    (
        "ext_lv_end_date",
        lambda val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None,
    ),
    "licence_type",
    "manager_emp_no",
    "manager_name",
)
STATUS_RANKING = [
    "NOPAY",
    "NON",
    "NPAYF",
    "NPAYP",
    "CCFA",
    "PFAS",
    "PFA",
    "PFT",
    "CFA",
    "CFT",
    "PPA",
    "PPT",
    "CPA",
    "CPT",
    "CAS",
    "SEAS",
    "TRAIN",
]
# A map of codes in the `emp_status` field to descriptive text.
EMP_STATUS_MAP = {
    "ADV": "ADVERTISED VACANCY",
    "BD": "Board",
    "CAS": "CASUAL EMPLOYEES",
    "CCFA": "COMMITTEE-BOARD MEMBERS FIXED TERM CONTRACT  AUTO",
    "CD": "CADET",
    "CEP": "COMMONWEALTH EMPLOYMENT PROGRAM",
    "CFA": "FIXED TERM CONTRACT FULL-TIME AUTO",
    "CFAS": "CONTRACT F-TIME AUTO SENIOR EXECUTIVE SERVICE",
    "CFT": "FIXED TERM CONTRACT FULL-TIME TSHEET",
    "CJA": "FIXED TERM CONTRACT JOB SHARE AUTO",
    "CJT": "FIXED TERM CONTRACT JOBSHARE TSHEET",
    "CO": "COMMITTEE (DO NOT USE- USE CCFA)",
    "CON": "EXTERNAL CONTRACTOR",
    "CPA": "FIXED TERM CONTRACT PART-TIME AUTO",
    "CPAS": "CONTRACT P-TIME AUTO SENIOR EXECUTIVE SERVICE",
    "CPT": "FIXED TERM CONTRACT PART-TIME TSHEET",
    "ECAS": "EXTERNAL FUND CASUAL",
    "ECFA": "FIXED TERM CONTRACT EXT. FUND F/TIME AUTO",
    "ECFT": "FIXED TERM CONTRACT EXT. FUND F/TIME TSHEET",
    "ECJA": "FIXED TERM CONTRACT EXT. FUND JOBSHARE AUTO",
    "ECJT": "FIXED TERM CONTRACT EXT. FUND JOBSHARE TSHEET",
    "ECPA": "FIXED TERM CONTRACT EXT. FUND P/TIME AUTO",
    "ECPT": "FIXED TERM CONTRACT EXT. FUND P/TIME TSHEET",
    "EPFA": "EXTERNAL FUND PERMANENT FULL-TIME AUTO",
    "EPFT": "EXTERNAL FUND FULL-TIME TSHEET",
    "EPJA": "EXTERNAL FUND PERMANENT JOBSHARE AUTO",
    "EPJT": "EXTERNAL FUND PERMANENT JOBSHARE TSHEEET",
    "EPPA": "EXTERNAL FUND PERMANENT PART-TIME AUTO",
    "EPPT": "EXTERNAL FUND PERMANENT PART-TIME TSHEET",
    "EXT": "EXTERNAL PERSON (NON EMPLOYEE)",
    "GRCA": "GRADUATE RECRUIT FIXED TERM CONTRACT AUTO",
    "JOB": "JOBSKILLS",
    "NON": "NON EMPLOYEE",
    "NOPAY": "NO PAY ALLOWED",
    "NPAYC": "CASUAL NO PAY ALLOWED",
    "NPAYF": "FULLTIME NO PAY ALLOWED",
    "NPAYP": "PARTTIME NO PAY ALLOWED",
    "NPAYT": "CONTRACT NO PAY ALLOWED (SEAS,CONT)",
    "PFA": "PERMANENT FULL-TIME AUTO",
    "PFAE": "PERMANENT FULL-TIME AUTO EXECUTIVE COUNCIL APPOINT",
    "PFAS": "PERMANENT FULL-TIME AUTO SENIOR EXECUTIVE SERVICE",
    "PFT": "PERMANENT FULL-TIME TSHEET",
    "PJA": "PERMANENT JOB SHARE AUTO",
    "PJT": "PERMANENT JOBSHARE TSHEET",
    "PPA": "PERMANENT PART-TIME AUTO",
    "PPAS": "PERMANENT PART-TIME AUTO SENIOR EXECUTIVE SERVICE",
    "PPRTA": "PERMANENT P-TIME AUTO (RELINQUISH ROR to FT)",
    "PPT": "PERMANENT PART-TIME TSHEET",
    "SCFA": "SECONDMENT FULL-TIME AUTO",
    "SEAP": "SEASONAL EMPLOYMENT (PERMANENT)",
    "SEAS": "SEASONAL EMPLOYMENT",
    "SES": "Senior Executive Service",
    "SFTC": "SPONSORED FIXED TERM CONTRACT AUTO",
    "SFTT": "SECONDMENT FULL-TIME TSHEET",
    "SN": "SUPERNUMERY",
    "SPFA": "PERMANENT FT SPECIAL CONDITIO AUTO",
    "SPFT": "PERMANENT FT SPECIAL CONDITIONS  TS",
    "SPTA": "SECONDMENT PART-TIME AUTO",
    "SPTT": "SECONDMENT PART-TIME TSHEET",
    "TEMP": "TEMPORARY EMPLOYMENT",
    "TERM": "TERMINATED",
    "TRAIN": "TRAINEE",
    "V": "VOLUNTEER",
    "WWR": "WEEKEND WEATHER READER",
    "Z": "Non-Resident",
}


def get_ascender_connection():
    """Returns a database connection to the Ascender database."""
    return connect(
        host=settings.FOREIGN_DB_HOST,
        port=settings.FOREIGN_DB_PORT,
        dbname=settings.FOREIGN_DB_NAME,
        user=settings.FOREIGN_DB_USERNAME,
        password=settings.FOREIGN_DB_PASSWORD,
    )


def row_to_python(row):
    """A convenience function to convert a row from the Ascender database to a
    Python dict, applying optional transforms to each column.
    Transforms can be to convert strings to datetime, or to rename column in
    the returned dict.
    """
    record = {}

    for k, field in enumerate(FOREIGN_TABLE_FIELDS):
        # If the field in a list or tuple, use the first element as the record key
        # and the second element (a callable function) as a transformer.
        if isinstance(field, (list, tuple)):
            if callable(field[1]):
                record[field[0]] = field[1](row[k])
            else:
                record[field[1]] = row[k]
        else:
            record[field] = row[k]

    return record


def ascender_db_fetch(employee_id=None):
    """Returns an iterator which yields all rows from the Ascender database query.
    Optionally pass employee_id to filter on a single employee.
    """
    if employee_id:
        # Validate `employee_id`: this value needs be castable as an integer, even though we use it as a string.
        try:
            int(employee_id)
        except ValueError:
            raise ValueError("Invalid employee ID value")

    conn = get_ascender_connection()
    cur = conn.cursor()
    columns = sql.SQL(",").join(
        sql.Identifier(f[0]) if isinstance(f, (list, tuple)) else sql.Identifier(f) for f in FOREIGN_TABLE_FIELDS
    )
    schema = sql.Identifier(settings.FOREIGN_SCHEMA)
    table = sql.Identifier(settings.FOREIGN_TABLE)
    employee_no = sql.Identifier("employee_no")

    if employee_id:
        # query = f"SELECT {columns} FROM {schema}.{table} WHERE employee_no = '{employee_id}'"
        query = sql.SQL("SELECT {columns} FROM {schema}.{table} WHERE {employee_no} = %s").format(
            columns=columns, schema=schema, table=table, employee_no=employee_no
        )
        cur.execute(query, (employee_id,))
    else:
        query = sql.SQL("SELECT {columns} FROM {schema}.{table}").format(columns=columns, schema=schema, table=table)
        cur.execute(query)

    while True:
        row = cur.fetchone()
        if row is None:
            break
        record = row_to_python(row)
        yield record


def ascender_job_sort_key(record):
    """
    Returns an integer value to "sort" a job, based on job end date.
    Jobs with an end date in the future will be preferenced over jobs with no end date, which will be
    preferenced over jobs that have already ended.

    The score is based on the job's end date:
    - If the job has ended, the initial score is calculated using the job's end date.
    - If the job is not ended, the initial score is calculated using the end date times 100.
    - If the job has no end date recorded, the initial score is calculated using the DATE_MAX value times 10.
    """
    today = datetime.now().date()

    # Initial score from job_end_date.
    if record["job_end_date"] and record["job_end_date"] < today.strftime("%Y-%m-%d"):
        score = int(record["job_end_date"].replace("-", ""))
    elif record["job_end_date"] and record["job_end_date"] >= today.strftime("%Y-%m-%d"):
        score = int(record["job_end_date"].replace("-", "")) * 100
    else:  # No job end date.
        score = int(DATE_MAX.strftime("%Y%m%d")) * 10

    return score


def ascender_employee_fetch(employee_id):
    """Returns a tuple: (employee_id, [sorted employee jobs])"""
    ascender_records = ascender_db_fetch(employee_id)
    jobs = []

    for row in ascender_records:
        jobs.append(row)

    # Sort the list of jobs in descending order of "score" from ascender_job_sort_key.
    jobs.sort(key=ascender_job_sort_key, reverse=True)
    return (employee_id, jobs)


def ascender_employees_fetch_all():
    """Returns a dict: {'<employee_id>': [sorted employee jobs], ...}"""
    ascender_records = ascender_db_fetch()
    records = {}

    for row in ascender_records:
        employee_id = row["employee_id"]
        if employee_id in records:
            # Append the next job to the list of jobs, sort and replace the dict value.
            jobs = records[employee_id]
            jobs.append(row)
            jobs.sort(key=ascender_job_sort_key, reverse=True)
            records[employee_id] = jobs
        else:
            records[employee_id] = [row]

    return records


def check_ascender_user_account_rules(job, ignore_job_start_date=False, manager_override_email=None, logging=False):
    """Given a passed-in Ascender record and any qualifiers, determine
    whether a new Azure AD account can be provisioned for that user.
    The 'job start date' rule can be optionally bypassed.
    Returns either a tuple of values required to provision the new account, or False.
    """
    ascender_record = f"{job['employee_id']}, {job['first_name']} {job['surname']}"
    if logging:
        LOGGER.info(f"Checking Ascender record {ascender_record}")

    # Only process non-FPC users.
    if job["clevel1_id"] == "FPC":
        if logging:
            LOGGER.warning("FPC Ascender record, aborting")
        return False

    # If a matching DepartmentUser already exists, skip.
    if DepartmentUser.objects.filter(employee_id=job["employee_id"]).exists():
        if logging:
            LOGGER.warning("Matching DepartmentUser object already exists, aborting")
        return False

    # Parse job end date (if present). Ascender records "null" job end date using a date value
    # far into the future (DATE_MAX) rather than leaving the value empty.
    job_end_date = None
    if job["job_end_date"] and datetime.strptime(job["job_end_date"], "%Y-%m-%d").date() != DATE_MAX:
        job_end_date = datetime.strptime(job["job_end_date"], "%Y-%m-%d").date()
        # Short circuit: if job_end_date is in the past, skip account creation.
        if job_end_date < date.today():
            if logging:
                LOGGER.warning(f"Job end date {job_end_date.strftime('%d/%b/%Y')} is in the past, aborting")
            return False

    # Start parsing required information for new account creation.
    licence_type = None
    cc = None
    job_start_date = None
    manager = None
    location = None

    # Rule: user must have a valid M365 licence type recorded.
    # The valid licence type values stored in Ascender are ONPUL and CLDUL.
    # Short circuit: if there is no value for licence_type, skip account creation.
    if not job["licence_type"] or job["licence_type"] == "NULL":
        if logging:
            LOGGER.warning("No M365 licence type recorded in Ascender, aborting")
        return False
    elif job["licence_type"] and job["licence_type"] in ["ONPUL", "CLDUL"]:
        if job["licence_type"] == "ONPUL":
            licence_type = "On-premise"
        elif job["licence_type"] == "CLDUL":
            licence_type = "Cloud"

    # Rule: user must have a manager recorded, and that manager must exist in our database.
    # Partial exception: if the email is specified, we can override the manager in Ascender.
    # That specifed manager must still exist in our database to proceed.
    if manager_override_email and DepartmentUser.objects.filter(email=manager_override_email).exists():
        manager = DepartmentUser.objects.get(email=manager_override_email)
    elif manager_override_email and not DepartmentUser.objects.filter(email=manager_override_email).exists():
        if logging:
            LOGGER.warning(f"Manager with email {manager_override_email} not present in IT Assets, aborting")
        return False
    elif job["manager_emp_no"] and DepartmentUser.objects.filter(employee_id=job["manager_emp_no"]).exists():
        manager = DepartmentUser.objects.get(employee_id=job["manager_emp_no"])
    elif job["manager_emp_no"] and not DepartmentUser.objects.filter(employee_id=job["manager_emp_no"]).exists():
        if logging:
            LOGGER.warning(f"Manager employee ID {job['manager_emp_no']} not present in IT Assets, aborting")
        return False
    elif not job["manager_emp_no"]:  # Short circuit: if there is no manager recorded, skip account creation.
        if logging:
            LOGGER.warning("No manager employee ID recorded in Ascender, aborting")
        return False

    # Rule: user must have a Cost Centre recorded (paypoint in Ascender).
    if job["paypoint"] and CostCentre.objects.filter(ascender_code=job["paypoint"]).exists():
        cc = CostCentre.objects.get(ascender_code=job["paypoint"])
    elif job["paypoint"] and not CostCentre.objects.filter(ascender_code=job["paypoint"]).exists():
        # Attempt to automatically create a new CC from Ascender data.
        try:
            cc = CostCentre.objects.create(
                code=job["paypoint"],
                ascender_code=job["paypoint"],
            )
            log = f"New Azure AD account process generated new cost centre, code {job['paypoint']}"
            AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
            LOGGER.info(log)
        except:
            # In the event of an error (probably due to a duplicate code), fail gracefully and log the error.
            log = (
                f"Exception during creation of new cost centre in new Azure AD account process, code {job['paypoint']}"
            )
            LOGGER.exception(log)
            return False

    # Rule: user must have a job start date recorded.
    if job["job_start_date"]:
        job_start_date = datetime.strptime(job["job_start_date"], "%Y-%m-%d").date()
    else:  # Short circuit.
        if logging:
            LOGGER.warning("No job start date recorded, aborting")
        return False

    # Skippable rule: if job_start_date is in the past, skip account creation.
    today = date.today()
    if ignore_job_start_date and logging:
        LOGGER.info(f"Skipped check for job start date {job_start_date.strftime('%d/%b/%Y')} being in the past")
    else:
        if job_start_date < today:
            if logging:
                LOGGER.warning(f"Job start date {job_start_date.strftime('%d/%b/%Y')} is in the past, aborting")
            return False

    # Rule: we set a limit for the number of days ahead of their starting date which we
    # allow to create an Azure AD account. If this value is not set (False/None), assume that there is
    # no limit.
    if (
        job_start_date
        and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS
        and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS > 0
    ):
        diff = job_start_date - today
        if diff.days > 0 and diff.days > settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS:
            # Start start exceeds our limit, abort creating an AD account yet.
            log = f"Job future start date {job_start_date.strftime('%d/%b/%Y')} exceeds limit of {settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS} days, aborting"
            if logging:
                LOGGER.warning(log)
            return False

    # Rule: user must have a physical location recorded, and that location must exist in our database.
    if job["geo_location_desc"] and Location.objects.filter(ascender_desc=job["geo_location_desc"]).exists():
        location = Location.objects.get(ascender_desc=job["geo_location_desc"])
    else:
        LOGGER.warning(f"Job physical location {job['geo_location_desc']} does not exist in IT Assets, aborting")
        return False

    # If all rules have passed, return a tuple containing required values.
    if cc and job_start_date and licence_type and manager and location:
        return (job, cc, job_start_date, licence_type, manager, location)


def ascender_user_import_all():
    """A utility function to cache data from Ascender to matching DepartmentUser objects.
    On no match, create a new Azure AD account and DepartmentUser based on Ascender data,
    assuming it meets all the business rules for new account provisioning.
    """
    LOGGER.info("Querying Ascender database for employee information")
    token = ms_graph_client_token()
    employee_records = ascender_employees_fetch_all()

    for employee_id, jobs in employee_records.items():
        if not jobs:
            continue
        # BUSINESS RULE: the "first" object in the list of Ascender jobs for each user is the current one.
        # Jobs are sorted via the `ascender_job_sort_key` function.
        job = jobs[0]
        # Only look at non-FPC users.
        if job["clevel1_id"] == "FPC":
            continue

        # Physical locations: if the Ascender physical location doesn't exist in our database, create it.
        # This is out of band to checks whether the user is new or otherwise, because sometimes new locations
        # are added to existing users.
        if (
            job["geo_location_desc"] and not Location.objects.filter(ascender_desc=job["geo_location_desc"]).exists()
        ):  # geo_location_desc must have a value.
            # Attempt to manually create a new location description from Ascender data.
            try:
                Location.objects.create(
                    name=job["geo_location_desc"],
                    ascender_desc=job["geo_location_desc"],
                    address=job["geo_location_desc"],
                )
                log = f"Creation of new Azure AD account process generated new location, description {job['geo_location_desc']}"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
                LOGGER.info(log)
            except:
                # In the event of an error (probably due to a duplicate name), fail gracefully and log the error.
                log = f"ASCENDER SYNC: exception during creation of new location in new Azure AD account process, description {job['geo_location_desc']}"
                LOGGER.error(log)

        if DepartmentUser.objects.filter(employee_id=employee_id).exists():
            # Ascender record does exist in our database; cache the current job record on the
            # DepartmentUser instance.
            user = DepartmentUser.objects.get(employee_id=employee_id)

            # Check if the user already has Ascender data cached. If so, check if the position_no
            # value has changed. In that situation, create a DepartmentUserLog object.
            if (
                user.ascender_data
                and "position_no" in user.ascender_data
                and user.ascender_data["position_no"] != job["position_no"]
            ):
                DepartmentUserLog.objects.create(
                    department_user=user,
                    log={
                        "ascender_field": "position_no",
                        "old_value": user.ascender_data["position_no"],
                        "new_value": job["position_no"],
                        "description": "Update position_no value from Ascender",
                    },
                )

            # Cache the job record.
            user.ascender_data = job
            user.ascender_data_updated = timezone.localtime()
            user.update_from_ascender_data()  # This method calls save()
            LOGGER.info(f"Updated existing user {user}")
        elif not DepartmentUser.objects.filter(employee_id=employee_id).exists():
            # Ascender record does not exist in our database; conditionally create a new
            # Azure AD account and DepartmentUser instance for them.
            # In this bulk check/create function, we do not ignore any account creation rules.
            rules_passed = check_ascender_user_account_rules(job, logging=False)

            if not rules_passed:
                continue

            # Unpack the required values.
            job, cc, job_start_date, licence_type, manager, location = rules_passed

            if cc and job_start_date and licence_type and manager and location:
                LOGGER.info(
                    f"Ascender employee ID {employee_id} does not exist and passed all rules; provisioning new account"
                )
                create_ad_user_account(job, cc, job_start_date, licence_type, manager, location, token)


def ascender_user_import(employee_id, ignore_job_start_date=False, manager_override_email=None):
    """A convenience function to import a single Ascender employee and create an AD account for them.
    This is to allow easier manual intervention where a record goes in after the start date, or an
    old employee returns to work and needs a new account created.
    Returns a DepartmentUser instance, or None.
    """
    LOGGER.info("Querying Ascender database for employee information")
    employee_id, jobs = ascender_employee_fetch(employee_id)
    if not jobs:
        LOGGER.warning(f"Ascender employee ID {employee_id} import did not return jobs data")
        return None
    job = jobs[0]

    rules_passed = check_ascender_user_account_rules(job, ignore_job_start_date, manager_override_email, logging=True)
    if not rules_passed:
        LOGGER.warning(f"Ascender employee ID {employee_id} import did not pass all rules")
        return None

    # Unpack the required values.
    job, cc, job_start_date, licence_type, manager, location = rules_passed
    token = ms_graph_client_token()
    user = create_ad_user_account(job, cc, job_start_date, licence_type, manager, location, token)

    return user


def create_ad_user_account(job, cc, job_start_date, licence_type, manager, location, token=None):
    """Function to create new Azure/onprem AD user accounts, based on passed-in user info.
    Returns the associated DepartmentUser object, or None.

    This function is safe to run if settings.ASCENDER_CREATE_AZURE_AD == False or settings.DEBUG == True.
    """
    if not token:
        token = ms_graph_client_token()

    ascender_record = f"{job['employee_id']}, {job['first_name']} {job['surname']}"
    job_end_date = None
    if job["job_end_date"] and datetime.strptime(job["job_end_date"], "%Y-%m-%d").date() != DATE_MAX:
        job_end_date = datetime.strptime(job["job_end_date"], "%Y-%m-%d").date()
    email = None
    mail_nickname = None

    if job["first_name"]:
        first_name = "".join([i.lower() for i in job["first_name"] if i.isalnum()])
    else:
        first_name = None
    if job["preferred_name"]:
        preferred_name = "".join([i.lower() for i in job["preferred_name"] if i.isalnum()])
    else:
        preferred_name = None
    if job["surname"]:
        surname = "".join([i.lower() for i in job["surname"] if i.isalnum()])
    else:
        surname = None
    if job["second_name"]:
        second_name = "".join([i.lower() for i in job["second_name"] if i.isalnum()])
    else:
        second_name = None

    # New email address generation.
    # Make no assumption about names (presence or absence). Remove any spaces/special characters within name text.
    if preferred_name and surname:
        email_patterns = [
            f"{preferred_name}.{surname}@dbca.wa.gov.au",
            f"{preferred_name}{second_name}.{surname}@dbca.wa.gov.au",
        ]
        for pattern in email_patterns:
            if not DepartmentUser.objects.filter(email=pattern).exists():
                email = pattern
                mail_nickname = pattern.split("@")[0]
                break
    elif first_name and surname:
        email_patterns = [
            f"{first_name}.{surname}@dbca.wa.gov.au",
            f"{first_name}{second_name}.{surname}@dbca.wa.gov.au",
        ]
        for pattern in email_patterns:
            if not DepartmentUser.objects.filter(email=pattern).exists():
                email = pattern
                mail_nickname = pattern.split("@")[0]
                break
    else:  # No preferred/first name recorded.
        log = f"Creation of new Azure AD account aborted, first/preferred name absent ({ascender_record})"
        AscenderActionLog.objects.create(level="WARNING", log=log, ascender_data=job)
        LOGGER.warning(log)
        return

    if not email and mail_nickname:
        # We can't generate a unique email with the supplied information; abort.
        log = f"Creation of new Azure AD account aborted at email step, unable to generate unique email ({ascender_record})"
        AscenderActionLog.objects.create(level="WARNING", log=log, ascender_data=job)
        LOGGER.warning(log)
        return

    # Display name generation. Set names to title case and strip trailing space.
    if job["preferred_name"] and job["surname"]:
        display_name = f"{job['preferred_name'].title().strip()} {job['surname'].title().strip()}"
    elif job["first_name"] and job["surname"]:
        display_name = f"{job['first_name'].title().strip()} {job['surname'].title().strip()}"
    else:  # No preferred/first name recorded.
        log = f"Creation of new Azure AD account aborted, first/preferred name absent ({ascender_record})"
        AscenderActionLog.objects.create(level="WARNING", log=log, ascender_data=job)
        LOGGER.warning(log)
        return
    title = title_except(job["occup_pos_title"])

    # M365 license availability is obtained from the subscribedSku resource type.
    # Total license number is returned in the prepaidUnits object (enabled + warning + suspended + lockedOut).
    # License consumption is returned in the value for consumedUnits, but this includes suspended
    # and locked-out licenses.
    # License availabilty (to assign to a user) is not especially intuitive; only licenses having
    # status `enabled` or `warning` are available to be assigned. Therefore if the value of consumedUnits
    # is greater than the value of prepaidUnits (enabled + warning), no licenses are currently
    # available to be assigned.
    # References:
    # - https://learn.microsoft.com/en-us/graph/api/resources/subscribedsku?view=graph-rest-1.0
    # - https://learn.microsoft.com/en-us/graph/api/resources/licenseunitsdetail?view=graph-rest-1.0
    # - https://github.com/microsoftgraph/microsoft-graph-docs-contrib/issues/2337

    e5_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 E5"], token)
    e5_consumed = e5_sku["consumedUnits"]
    e5_assignable = e5_sku["prepaidUnits"]["enabled"] + e5_sku["prepaidUnits"]["warning"]
    f3_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 F3"], token)
    f3_consumed = f3_sku["consumedUnits"]
    f3_assignable = f3_sku["prepaidUnits"]["enabled"] + f3_sku["prepaidUnits"]["warning"]
    eo_sku = ms_graph_subscribed_sku(MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"], token)
    eo_consumed = eo_sku["consumedUnits"]
    eo_assignable = eo_sku["prepaidUnits"]["enabled"] + eo_sku["prepaidUnits"]["warning"]
    sec_sku = ms_graph_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 F5 SECURITY + COMPLIANCE ADD-ON"], token)
    sec_consumed = sec_sku["consumedUnits"]
    sec_assignable = sec_sku["prepaidUnits"]["enabled"] + sec_sku["prepaidUnits"]["warning"]

    if job["licence_type"] == "ONPUL":
        licence_type = "On-premise"
        # Short circuit: no available licences, abort.
        if e5_assignable - e5_consumed <= 0:
            LOGGER.warning(f"Creation of new Azure AD account aborted, no E5 licences available ({ascender_record})")
            return
    elif job["licence_type"] == "CLDUL":
        licence_type = "Cloud"
        # Short circuit: no available licences, abort.
        if f3_assignable - f3_consumed <= 0:
            LOGGER.warning(
                f"Creation of new Azure AD account aborted, no Cloud F3 licences available ({ascender_record})"
            )
            return
        if eo_assignable - eo_consumed <= 0:
            LOGGER.warning(
                f"Creation of new Azure AD account aborted, no Cloud Exchange Online licences available ({ascender_record})"
            )
            return
        if sec_assignable - sec_consumed <= 0:
            LOGGER.warning(
                f"Creation of new Azure AD account aborted, no Cloud Security & Compliance for FLW licences available ({ascender_record})"
            )
            return

    LOGGER.info(f"Creating new Azure AD account: {display_name}, {email}, {licence_type} account")

    # Generate an account password and validate its complexity.
    # Reference: https://docs.python.org/3/library/secrets.html#secrets.token_urlsafe
    password = None
    while password is None:
        password = secrets.token_urlsafe(20)
        resp = ms_graph_validate_password(password)
        if not resp.json()["isValid"]:
            password = None

    # Configuration setting to explicitly allow creation of new AD users.
    if not settings.ASCENDER_CREATE_AZURE_AD:
        LOGGER.info(f"Skipping creation of new Azure AD account: {ascender_record} (ASCENDER_CREATE_AZURE_AD == False)")
        return

    # Final short-circuit: skip creation of new AD accounts while in Debug mode (mainly to avoid blunders during dev/testing).
    # After this point, we begin making changes to Azure AD.
    if settings.DEBUG:
        LOGGER.info(f"Skipping creation of new Azure AD account for emp ID {ascender_record} (DEBUG)")
        return

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "Content-Type": "application/json",
    }

    # Initially create the Azure AD user with the MS Graph API.
    try:
        url = "https://graph.microsoft.com/v1.0/users"
        data = {
            "accountEnabled": False,
            "displayName": display_name,
            "userPrincipalName": email,
            "mailNickname": mail_nickname,
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": password,
            },
        }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        resp_json = resp.json()
        guid = resp_json["id"]
    except:
        log = f"Create new Azure AD user failed at account creation step for {email}, most likely duplicate email account exists ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        text_content = f"""Ascender record:\n
        {job}\n
        Request URL: {url}\n
        Request body:\n
        {data}\n
        Response code: {resp.status_code}\n
        Response content:\n
        {resp.content}\n"""
        msg = EmailMultiAlternatives(
            subject=log,
            body=text_content,
            from_email=settings.NOREPLY_EMAIL,
            to=settings.ADMIN_EMAILS,
        )
        msg.send(fail_silently=True)
        return

    # Next, update the user details with additional information.
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{guid}"
        data = {
            "mail": email,
            "employeeId": job["employee_id"],
            "givenName": job["preferred_name"].title().strip()
            if job["preferred_name"]
            else job["first_name"].title().strip(),
            "surname": job["surname"].title(),
            "jobTitle": title,
            "companyName": cc.code,
            "department": cc.get_division_name_display(),
            "officeLocation": location.name,
            "streetAddress": location.address,
            "state": "Western Australia",
            "country": "Australia",
            "usageLocation": "AU",
        }
        resp = requests.patch(url, headers=headers, json=data)
        resp.raise_for_status()
    except:
        log = f"Create new Azure AD user failed at account update step for {email}, ask administrator to investigate ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        text_content = f"""Ascender record:\n
        {job}\n
        Request URL: {url}\n
        Request body:\n
        {data}\n
        Response code: {resp.status_code}\n
        Response content:\n
        {resp.content}\n"""
        msg = EmailMultiAlternatives(
            subject=log,
            body=text_content,
            from_email=settings.NOREPLY_EMAIL,
            to=settings.ADMIN_EMAILS,
        )
        msg.send(fail_silently=True)
        return

    # Next, set the user manager.
    try:
        manager_url = f"https://graph.microsoft.com/v1.0/users/{guid}/manager/$ref"
        data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{manager.azure_guid}"}
        resp = requests.put(manager_url, headers=headers, json=data)
        resp.raise_for_status()
    except:
        log = f"Create new Azure AD user failed at assign manager update step for {email}, manager may not have AD account ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        text_content = f"""Ascender record:\n
        {job}\n
        Request URL: {url}\n
        Request body:\n
        {data}\n
        Response code: {resp.status_code}\n
        Response content:\n
        {resp.content}\n"""
        msg = EmailMultiAlternatives(
            subject=log,
            body=text_content,
            from_email=settings.NOREPLY_EMAIL,
            to=settings.ADMIN_EMAILS,
        )
        msg.send(fail_silently=True)
        return

    # Next, add the required licenses to the user.
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{guid}/assignLicense"
        if licence_type == "On-premise":
            data = {
                "addLicenses": [
                    {"skuId": MS_PRODUCTS["MICROSOFT 365 E5"], "disabledPlans": []},
                ],
                "removeLicenses": [],
            }
        elif licence_type == "Cloud":
            data = {
                "addLicenses": [
                    {
                        "skuId": MS_PRODUCTS["MICROSOFT 365 F3"],
                        "disabledPlans": [
                            MS_PRODUCTS["EXCHANGE ONLINE KIOSK"],
                        ],
                    },
                    {
                        "skuId": MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"],
                        "disabledPlans": [],
                    },
                    {
                        "skuId": MS_PRODUCTS["MICROSOFT 365 F5 SECURITY + COMPLIANCE ADD-ON"],
                        "disabledPlans": [
                            MS_PRODUCTS["EXCHANGE ONLINE ARCHIVING"],
                        ],
                    },
                ],
                "removeLicenses": [],
            }
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
    except:
        log = f"Create new Azure AD user failed at assign license step for {email}, ask administrator to investigate ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        text_content = f"""Ascender record:\n
        {job}\n
        Request URL: {url}\n
        Request body:\n
        {data}\n
        Response code: {resp.status_code}\n
        Response content:\n
        {resp.content}\n"""
        msg = EmailMultiAlternatives(
            subject=log,
            body=text_content,
            from_email=settings.NOREPLY_EMAIL,
            to=settings.ADMIN_EMAILS,
        )
        msg.send(fail_silently=True)
        return

    LOGGER.info(f"New Azure AD account created from Ascender data ({email})")

    # Next, create a new DepartmentUser that is linked to the Ascender record and the Azure AD account.
    new_user = DepartmentUser.objects.create(
        azure_guid=guid,
        active=False,
        email=email,
        name=display_name,
        given_name=job["preferred_name"].title().strip()
        if job["preferred_name"]
        else job["first_name"].title().strip(),
        surname=job["surname"].title(),
        preferred_name=job["preferred_name"].title().strip() if job["preferred_name"] else None,
        title=title,
        employee_id=job["employee_id"],
        cost_centre=cc,
        location=location,
        manager=manager,
        ascender_data=job,
        ascender_data_updated=timezone.localtime(),
    )
    log = f"Created new department user {new_user} ({ascender_record})"
    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
    LOGGER.info(log)

    # Email the new account's manager the checklist to finish account provision.
    new_user_creation_email(new_user, licence_type, job_start_date, job_end_date)
    LOGGER.info(f"ASCENDER SYNC: Emailed {new_user.manager.email} about new user account creation")

    return new_user


def employee_ids_audit(employee_ids=None):
    """A utility function to check the set of current Ascender employee ID values and prune/remove
    any outdated ones.
    """
    LOGGER.info("Querying Ascender database for employee information")
    if not employee_ids:
        employee_ids = []
        ascender_iter = ascender_db_fetch()
        for record in ascender_iter:
            employee_ids.append(record["employee_id"])

    LOGGER.info(f"Auditing {len(employee_ids)} employee ID values recorded on department users")
    for user in DepartmentUser.objects.filter(employee_id__isnull=False):
        if user.employee_id not in employee_ids:
            LOGGER.info(f"{user.employee_id} not found in current Ascender employee IDs, clearing it from {user}")
            user.employee_id = None
            user.ascender_data = {}
            user.ascender_data_updated = None
            user.save()


def new_user_creation_email(new_user, licence_type, job_start_date, job_end_date=None):
    """This email function is split from the 'create' step so that it can be called again in the event of failure.
    Note that we can't call new_user.get_licence_type() because we probably haven't synced M365 licences to the department user yet.
    We also require the user's job start and end dates (end date may be None).
    """
    org_path = new_user.get_ascender_org_path()
    if org_path and len(org_path) > 1:
        unit = org_path[1]
    else:
        unit = ""
    subject = f"New user account creation details - {new_user.name}"
    text_content = f"""Hi {new_user.manager.given_name},\n\n
This is an automated email to confirm that a new user account has been created, using the information that was provided in Ascender. The details are:\n\n
Name: {new_user.name}\n
Employee ID: {new_user.employee_id}\n
Email: {new_user.email}\n
Title: {new_user.title}\n
Position number: {new_user.ascender_data['position_no']}\n
Cost centre: {new_user.cost_centre}\n
Division: {new_user.cost_centre.get_division_name_display()}\n
Organisational unit: {unit}\n
Employment status: {new_user.ascender_data['emp_stat_desc']}\n
M365 licence: {licence_type}\n
Manager: {new_user.manager.name}\n
Location: {new_user.location}\n
Job start date: {job_start_date.strftime('%d/%b/%Y')}\n\n
Job end date: {job_end_date.strftime('%d/%b/%Y') if job_end_date else ''}\n\n
Cost centre manager: {new_user.cost_centre.manager.name if new_user.cost_centre.manager else ''}\n\n
OIM Service Desk will now complete the new account and provide you with confirmation and instructions for the new user.\n\n
Regards,\n\n
OIM Service Desk\n"""
    html_content = f"""<p>Hi {new_user.manager.given_name},</p>
<p>This is an automated email to confirm that a new user account has been created, using the information that was provided in Ascender. The details are:</p>
<ul>
<li>Name: {new_user.name}</li>
<li>Employee ID: {new_user.employee_id}</li>
<li>Email: {new_user.email}</li>
<li>Title: {new_user.title}</li>
<li>Position number: {new_user.ascender_data['position_no']}</li>
<li>Cost centre: {new_user.cost_centre}</li>
<li>Division: {new_user.cost_centre.get_division_name_display()}</li>
<li>Organisational unit: {unit}</li>
<li>Employment status: {new_user.ascender_data['emp_stat_desc']}</li>
<li>M365 licence: {licence_type}</li>
<li>Manager: {new_user.manager.name}</li>
<li>Location: {new_user.location}</li>
<li>Job start date: {job_start_date.strftime('%d/%b/%Y')}</li>
<li>Job end date: {job_end_date.strftime('%d/%b/%Y') if job_end_date else ''}</li>
<li>Cost centre manager: {new_user.cost_centre.manager.name if new_user.cost_centre.manager else ''}</li>
</ul>
<p>OIM Service Desk will now complete the new account and provide you with confirmation and instructions for the new user.</p>
<p>Regards,</p>
<p>OIM Service Desk</p>"""
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.NOREPLY_EMAIL,
        to=[new_user.manager.email],
        cc=[settings.SERVICE_DESK_EMAIL],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)


def ascender_cc_manager_fetch():
    """Returns all records from cc_manager_view."""
    conn = get_ascender_connection()
    cursor = conn.cursor()
    cc_manager_query_sql = f'SELECT * FROM "{settings.FOREIGN_SCHEMA}"."{settings.FOREIGN_TABLE_CC_MANAGER}"'
    cursor.execute(cc_manager_query_sql)
    records = []

    while True:
        row = cursor.fetchone()
        if row is None:
            break
        records.append(row)

    return records


def update_cc_managers():
    """Queries cc_manager_view and updates the cost centre manager for each."""
    records = ascender_cc_manager_fetch()
    for r in records:
        if CostCentre.objects.filter(ascender_code=r[1]).exists():
            cc = CostCentre.objects.get(ascender_code=r[1])
            if DepartmentUser.objects.filter(employee_id=r[6]).exists():
                cc.manager = DepartmentUser.objects.get(employee_id=r[6])
                cc.save()
