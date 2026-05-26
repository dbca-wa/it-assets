import logging
import re
from collections.abc import Iterator
from datetime import date, datetime
from time import sleep
from typing import List, Literal, Optional

import requests
from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from psycopg import Connection, connect, sql

from itassets.utils import ms_graph_client_token
from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import AscenderActionLog, CostCentre, DepartmentUser, DepartmentUserLog, Location
from organisation.utils import generate_password, ms_graph_get_subscribed_sku, ms_graph_validate_password, title_except

User = get_user_model()
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
    "AO": "ACCESS ONLY",
    "BD": "BOARD",
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
    "SES": "SENIOR EXECUTIVE SERVICE",
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
    "Z": "NON-RESIDENT",
}
# A (partial) map of codes in the `term_reason` field to descriptive text.
TERM_REASON_MAP = {
    "AE": "Left employment",
    "CO": "Casual Officer",
    "EC": "End of appointment",
    "EP": "External promotion",
    "OR": "Other reasons",
    "RA": "Retirement",
    "RE": "Retirement",
    "RF": "Retirement",
    "RH": "Retirement",
    "RI": "Retirement",
    "RS": "Resignation",
    "TA": "Transfer to another agency",
}


def get_ascender_db_connection() -> Connection:
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


def ascender_db_fetch(employee_id: Optional[str] = None) -> Iterator:
    """Returns an iterator which yields all rows from the Ascender database query.
    Optionally pass employee_id to filter on a single employee.
    """
    if employee_id:
        # Validate `employee_id`: this value needs be castable as an integer, even though we use it as a string.
        try:
            int(employee_id)
        except ValueError:
            raise ValueError("Invalid employee ID value")

    conn = get_ascender_db_connection()
    cur = conn.cursor()
    columns = sql.SQL(",").join(sql.Identifier(f[0]) if isinstance(f, (list, tuple)) else sql.Identifier(f) for f in FOREIGN_TABLE_FIELDS)
    schema = sql.Identifier(settings.FOREIGN_SCHEMA)
    table = sql.Identifier(settings.FOREIGN_TABLE)
    employee_no = sql.Identifier("employee_no")

    if employee_id:
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


def ascender_job_sort_key(record: dict) -> int:
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


def ascender_employee_fetch(employee_id) -> tuple:
    """Returns a tuple: (employee_id, [sorted employee jobs])"""
    ascender_records = ascender_db_fetch(employee_id)
    jobs = []

    for row in ascender_records:
        jobs.append(row)

    # Sort the list of jobs in descending order of "score" from ascender_job_sort_key.
    jobs.sort(key=ascender_job_sort_key, reverse=True)
    return (employee_id, jobs)


def ascender_employees_fetch_all() -> dict:
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


def validate_ascender_user_account_rules(
    job: dict, ignore_job_start_date: bool = False, manager_override_email: Optional[str] = None, logging: bool = False
) -> tuple | Literal[False]:
    """Given a passed-in Ascender record and any qualifiers, determine
    whether a new Entra ID account can be provisioned for that user.
    The 'job start date' rule can be optionally bypassed.
    Returns either a tuple of values required to provision the new account, or False.
    """
    ascender_record = f"{job['employee_id']}, {job['first_name']} {job['surname']}"
    if logging:
        LOGGER.info(f"Checking Ascender record {ascender_record}")

    # Only process non-FPC users.
    if "clevel1_id" in job and job["clevel1_id"] == "FPC":
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
            log = f"New Entra ID account process generated new cost centre, code {job['paypoint']}"
            AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
            LOGGER.info(log)
        except:
            # In the event of an error (probably due to a duplicate code), fail gracefully and log the error.
            log = f"Exception during creation of new cost centre in new Entra ID account process, code {job['paypoint']}"
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
    if ignore_job_start_date:
        if logging:
            LOGGER.info(f"Skipped check for job start date {job_start_date.strftime('%d/%b/%Y')} being in the past")
    else:
        if job_start_date < today:
            if logging:
                LOGGER.warning(f"Job start date {job_start_date.strftime('%d/%b/%Y')} is in the past, aborting")
            return False

    # Rule: we set a limit for the number of days ahead of their starting date which we
    # allow to create an Entra ID account. If this value is not set (False/None), assume that there is
    # no limit.
    if job_start_date and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS > 0:
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
        if job["geo_location_desc"]:
            LOGGER.warning(f"Job physical location {job['geo_location_desc']} does not exist in IT Assets, aborting")
        else:
            LOGGER.warning("No job physical location recorded, aborting")
        return False

    # If all rules have passed, return a tuple containing required values.
    if cc and job_start_date and licence_type and manager and location:
        return (job, cc, job_start_date, licence_type, manager, location)
    else:
        return False


def ascender_user_import_all():
    """A utility function to cache data from Ascender to matching DepartmentUser objects.
    On no match, create a new Entra ID account and DepartmentUser based on Ascender data,
    assuming it meets all the business rules for new account provisioning.
    """
    LOGGER.info("Querying Ascender database for employee information")
    token = ms_graph_client_token()
    employee_records = ascender_employees_fetch_all()

    for employee_id, jobs in employee_records.items():
        # If we have no jobs data from Ascender for this employee, skip them.
        if not jobs:
            continue

        # BUSINESS RULE: the first object in the list of Ascender jobs for each user
        # is normally the "current"" one, however this can be manually overridden by
        # specifying a `position_no` value on the DepartmentUser object.
        # The list of jobs from Ascender is sorted via the `ascender_job_sort_key` function.
        # This override is only possible for existing user accounts, not for new ones.
        # By default, use the first job in the sorted list (ensures that we have a job record).
        job = jobs[0]
        # For an existing matched DepartmentUser record where a position_no value is recorded,
        # attempt to select that job from the list instead.
        if DepartmentUser.objects.filter(employee_id=employee_id, position_no__isnull=False).exists():
            user = DepartmentUser.objects.get(employee_id=employee_id)
            position_no = user.position_no
            for j in jobs:
                if j["position_no"] == position_no:
                    job = j
                    LOGGER.info(f"Using position no {position_no} for {user} job (override)")

        # Skip FPC users.
        if "clevel1_id" in job and job["clevel1_id"] == "FPC":
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
                log = f"Creation of new Entra ID account process generated new location, description {job['geo_location_desc']}"
                AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
                LOGGER.info(log)
            except:
                # In the event of an error (probably due to a duplicate name), fail gracefully and log the error.
                log = f"ASCENDER SYNC: exception during creation of new location in new Entra ID account process, description {job['geo_location_desc']}"
                LOGGER.error(log)

        if DepartmentUser.objects.filter(employee_id=employee_id).exists():
            # Ascender record does exist in our database; cache the current job record on the
            # DepartmentUser instance.
            user = DepartmentUser.objects.get(employee_id=employee_id)

            # Check if the user already has Ascender data cached. If so, check if the position_no
            # value has changed. In that situation, create a DepartmentUserLog object.
            if user.ascender_data and "position_no" in user.ascender_data and user.ascender_data["position_no"] != job["position_no"]:
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
        elif not DepartmentUser.objects.filter(employee_id=employee_id).exists():
            # Ascender record does not exist in our database; conditionally create a new
            # Entra ID account and DepartmentUser instance for them.
            # In this bulk check/create function, we do not ignore any account creation rules.
            rules_passed = validate_ascender_user_account_rules(job, logging=False)

            if not rules_passed:
                # This DepartmentUser does not exist but has not passed all rules to generate a new Entra ID user account.
                continue

            # Unpack the required values.
            job, cc, job_start_date, licence_type, manager, location = rules_passed

            if cc and job_start_date and licence_type and manager and location:
                LOGGER.info(f"Ascender employee ID {employee_id} does not exist and passed all rules; provisioning new account")
                _ = create_entra_id_user(job, cc, job_start_date, manager, location, token)


def ascender_user_import(
    employee_id: str, ignore_job_start_date: bool = False, manager_override_email: Optional[str] = None, position_no: Optional[str] = None
) -> DepartmentUser | None:
    """A convenience function to import a single Ascender employee and create an AD account for them.
    This is to allow easier manual intervention where a record goes in after the start date, or an
    old employee returns to work and needs a new account created.
    We can also manually specify the job position number to use for the new account, in order to
    bypass the default job sort order.
    """
    LOGGER.info("Querying Ascender database for employee record")
    employee_id, jobs = ascender_employee_fetch(employee_id)
    if not jobs:
        LOGGER.warning(f"Ascender employee ID {employee_id} import did not return jobs data")
        return None

    if position_no:
        # Don't use the default sort order of the jobs, instead use the supplied position_no value.
        job = None
        for record in jobs:
            if record["position_no"] == position_no:
                job = record
                break
        # If we didn't match a position_no returned in the Ascender jobs, abort.
        if not job:
            LOGGER.warning(f"Position no. {position_no} did not match any jobs in the Ascender employee record")
            return None
    else:
        job = jobs[0]

    rules_passed = validate_ascender_user_account_rules(job, ignore_job_start_date, manager_override_email, logging=True)
    if not rules_passed:
        LOGGER.warning(f"Ascender employee ID {employee_id} import did not pass all rules")
        return None

    # Unpack the required values.
    job, cc, job_start_date, licence_type, manager, location = rules_passed
    token = ms_graph_client_token()
    return create_entra_id_user(job, cc, job_start_date, manager, location, token, position_no)


def sanitise_name_values(first_name: str = "", second_name: str = "", surname: str = "", preferred_name: str = ""):
    """Takes in string name values and returns them stripped of non-alphabetic characters, except hyphens ("-").
    This function is used for generating email-friendly values."""
    pattern = r"[^A-Za-z\-]"
    first_name = re.sub(pattern, "", first_name)
    second_name = re.sub(pattern, "", second_name)
    surname = re.sub(pattern, "", surname)
    preferred_name = re.sub(pattern, "", preferred_name)
    return first_name, second_name, surname, preferred_name


def _log_and_abort(message: str, job: dict, level: str = "WARNING") -> None:
    """Record an abort message to both the AscenderActionLog and the Python logger.

    Used as a shared helper for the early-exit paths in create_entra_id_user that need
    both a persistent database audit record and a log line before returning None.
    The `level` parameter controls both the AscenderActionLog level field and the
    logger method called (e.g. "WARNING" → LOGGER.warning).
    """
    AscenderActionLog.objects.create(level=level, log=message, ascender_data=job)
    getattr(LOGGER, level.lower())(message)


def _send_admin_failure_email(subject: str, body: str) -> None:
    """Send a failure notification email to the configured admin addresses.

    Used to alert OIM admins when a step in the Entra ID account creation pipeline fails
    in a way that may require manual investigation or remediation (e.g. a partially
    provisioned account left in the directory, or a licence assignment that timed out).
    """
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.NOREPLY_EMAIL,
        to=settings.ADMIN_EMAILS,
    )
    msg.send(fail_silently=True)


def _resolve_names(job: dict) -> tuple[str, str, str, str]:
    """Extract and sanitise name fields from an Ascender job dict for email generation.

    Reads first_name, second_name, surname, and preferred_name from the job dict,
    treating missing/None values as empty strings, then passes them through
    sanitise_name_values() to strip non-alphabetic characters (except hyphens).

    Returns a (first_name, second_name, surname, preferred_name) tuple ready for
    use in generate_valid_dbca_email().
    """
    first_name = job["first_name"] or ""
    second_name = job["second_name"] or ""
    surname = job["surname"] or ""
    preferred_name = job["preferred_name"] or ""
    return sanitise_name_values(first_name, second_name, surname, preferred_name)


def _check_licence_availability(licence_type_code: str, token: dict, ascender_record: str) -> str | None:
    """Check Microsoft 365 licence availability for the given Ascender licence type code.

    Queries the MS Graph subscribedSku endpoint to verify that at least one licence
    of each required SKU remains available for assignment. Returns the human-readable
    licence type string ("On-premise" or "Cloud") if all required licences are available,
    or None if the check fails or no licences remain.

    Licence availability is calculated as prepaidUnits (enabled + warning) minus
    consumedUnits. Only "enabled" and "warning" prepaid units can be assigned to new
    users; suspended or locked-out units are excluded from the available count.

    ONPUL maps to "On-premise" and requires: Microsoft 365 E5.
    CLDUL maps to "Cloud" and requires: Microsoft 365 F3, Exchange Online (Plan 2),
    and Microsoft 365 F5 Security + Compliance Add-on.

    References:
    - https://learn.microsoft.com/en-us/graph/api/resources/subscribedsku?view=graph-rest-1.0
    - https://learn.microsoft.com/en-us/graph/api/resources/licenseunitsdetail?view=graph-rest-1.0
    - https://github.com/microsoftgraph/microsoft-graph-docs-contrib/issues/2337
    """
    if licence_type_code == "ONPUL":
        e5_sku = ms_graph_get_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 E5"], token)
        if not e5_sku:
            LOGGER.warning(f"Graph API E5 SKU query returned no data ({ascender_record})")
            return None
        e5_assignable = e5_sku["prepaidUnits"]["enabled"] + e5_sku["prepaidUnits"]["warning"]
        if e5_assignable - e5_sku["consumedUnits"] <= 0:
            LOGGER.warning(f"Creation of new Entra ID account aborted, no E5 licences available ({ascender_record})")
            return None
        return "On-premise"

    elif licence_type_code == "CLDUL":
        f3_sku = ms_graph_get_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 F3"], token)
        if not f3_sku:
            LOGGER.warning(f"Graph API F3 SKU query returned no data ({ascender_record})")
            return None
        f3_assignable = f3_sku["prepaidUnits"]["enabled"] + f3_sku["prepaidUnits"]["warning"]
        if f3_assignable - f3_sku["consumedUnits"] <= 0:
            LOGGER.warning(f"Creation of new Entra ID account aborted, no Cloud F3 licences available ({ascender_record})")
            return None

        eo_sku = ms_graph_get_subscribed_sku(MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"], token)
        if not eo_sku:
            LOGGER.warning(f"Graph API Exchange Online (Plan 2) SKU query returned no data ({ascender_record})")
            return None
        eo_assignable = eo_sku["prepaidUnits"]["enabled"] + eo_sku["prepaidUnits"]["warning"]
        if eo_assignable - eo_sku["consumedUnits"] <= 0:
            LOGGER.warning(f"Creation of new Entra ID account aborted, no Cloud Exchange Online licences available ({ascender_record})")
            return None

        sec_sku = ms_graph_get_subscribed_sku(MS_PRODUCTS["MICROSOFT 365 F5 SECURITY + COMPLIANCE ADD-ON"], token)
        if not sec_sku:
            LOGGER.warning(f"Graph API F5 Security Addon SKU query returned no data ({ascender_record})")
            return None
        sec_assignable = sec_sku["prepaidUnits"]["enabled"] + sec_sku["prepaidUnits"]["warning"]
        if sec_assignable - sec_sku["consumedUnits"] <= 0:
            LOGGER.warning(
                f"Creation of new Entra ID account aborted, no Cloud Security & Compliance for FLW licences available ({ascender_record})"
            )
            return None
        return "Cloud"

    else:
        LOGGER.warning(f"Creation of new Entra ID account aborted, invalid license type ({ascender_record})")
        return None


def _build_licence_payload(licence_type: str) -> dict:
    """Build the MS Graph assignLicense request payload for the given licence type string.

    Returns a dict suitable for POSTing to the Graph API /users/{id}/assignLicense endpoint.

    For "On-premise" (ONPUL): assigns Microsoft 365 E5 with no disabled plans.
    For "Cloud" (CLDUL): assigns Microsoft 365 F3 (Exchange Online Kiosk disabled),
    Exchange Online Plan 2, and the F5 Security + Compliance Add-on
    (Exchange Online Archiving disabled).
    """
    if licence_type == "On-premise":
        return {
            "addLicenses": [
                {"skuId": MS_PRODUCTS["MICROSOFT 365 E5"], "disabledPlans": []},
            ],
            "removeLicenses": [],
        }
    else:  # "Cloud"
        return {
            "addLicenses": [
                {
                    "skuId": MS_PRODUCTS["MICROSOFT 365 F3"],
                    "disabledPlans": [MS_PRODUCTS["EXCHANGE ONLINE KIOSK"]],
                },
                {
                    "skuId": MS_PRODUCTS["EXCHANGE ONLINE (PLAN 2)"],
                    "disabledPlans": [],
                },
                {
                    "skuId": MS_PRODUCTS["MICROSOFT 365 F5 SECURITY + COMPLIANCE ADD-ON"],
                    "disabledPlans": [MS_PRODUCTS["EXCHANGE ONLINE ARCHIVING"]],
                },
            ],
            "removeLicenses": [],
        }


def _wait_for_usage_location(guid: str, headers: dict, job: dict, email: str) -> bool:
    """Poll MS Graph until the user's usageLocation field is confirmed set to 'AU'.

    Entra ID can take time to propagate newly-created user attributes, and the
    assignLicense call will fail if usageLocation is absent. This function retries
    with exponential backoff (starting at 1 s, doubling each attempt, up to a 300 s cap).

    On success returns True. On timeout: logs a warning, creates an AscenderActionLog
    entry, and emails admins before returning False.
    """
    user_has_usage_location = False
    graph_user = None
    timestamp = datetime.now()
    retry_delay = 1
    url = f"https://graph.microsoft.com/v1.0/users/{guid}"
    params = {"$select": "id,usageLocation"}

    while retry_delay < 300:
        resp = requests.get(url, headers=headers, params=params)
        try:
            resp.raise_for_status()
            graph_user = resp.json()
        except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception) as exc:
            LOGGER.warning(f"Call to {url} raised exception", exc_info=exc)

        timestamp = datetime.now()

        if graph_user and graph_user.get("usageLocation") == "AU":
            user_has_usage_location = True
            break
        else:
            LOGGER.info(f"User {guid} usageLocation not set; retrying in {retry_delay} seconds")
            sleep(retry_delay)
            retry_delay = retry_delay * 2

    if not user_has_usage_location:
        log = f"Create new Entra ID user failed at assign license step for {email}, usageLocation field value not set"
        _log_and_abort(log, job)
        _send_admin_failure_email(
            log,
            f"Ascender record:\n{job}\nMicrosoft Graph API endpoint: {url}\nRetry delay: {retry_delay}\nQuery timestamp: {timestamp.isoformat()}",
        )

    return user_has_usage_location


def _assign_licence_with_retry(
    guid: str,
    headers: dict,
    licence_payload: dict,
    job: dict,
    email: str,
    ascender_record: str,
) -> bool:
    """Assign M365 licences to a newly-created Entra ID user, retrying with exponential backoff.

    Newly-created accounts can take time to become fully ready for licence assignment, so
    this function retries the assignLicense Graph API call starting at 1 s, doubling each
    attempt, up to a 300 s cap.

    On permanent failure: logs a warning, creates an AscenderActionLog entry, emails admins,
    and attempts to DELETE the orphaned Entra ID account to avoid leaving a half-provisioned
    user in the directory. The cleanup result is itself logged regardless of outcome.

    Returns True on successful licence assignment, False on failure.
    """
    user_has_license = False
    url = f"https://graph.microsoft.com/v1.0/users/{guid}/assignLicense"
    timestamp = datetime.now()
    retry_delay = 1
    resp = None

    while retry_delay < 300:
        try:
            resp = requests.post(url, headers=headers, json=licence_payload)
            resp.raise_for_status()
            user_has_license = True
        except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception) as exc:
            LOGGER.warning(f"Call to {url} raised exception", exc_info=exc)

        timestamp = datetime.now()

        if user_has_license:
            break
        else:
            LOGGER.info(f"Licence assignment for user {guid} not yet successful; retrying in {retry_delay} seconds")
            sleep(retry_delay)
            retry_delay = retry_delay * 2

    if not user_has_license:
        log = f"Create new Entra ID user failed at assign license step for {email}, ask administrator to investigate ({ascender_record})"
        _log_and_abort(log, job)
        resp_code = resp.status_code if resp is not None else "N/A"
        resp_content = resp.content if resp is not None else "N/A"
        _send_admin_failure_email(
            log,
            f"Ascender record:\n{job}\nMicrosoft Graph API endpoint: {url}\nRetry delay: {retry_delay}\nQuery timestamp: {timestamp.isoformat()}\nRequest body: {licence_payload}\nResponse code: {resp_code}\nResponse content: {resp_content}",
        )

        # Delete the partially-provisioned account to avoid an orphaned Entra ID user.
        delete_url = f"https://graph.microsoft.com/v1.0/users/{guid}"
        try:
            delete_resp = requests.delete(delete_url, headers=headers)
            delete_resp.raise_for_status()
            cleanup_log = (
                f"Create new Entra ID user cleanup due to license assign failure: deleted orphaned Entra ID account {guid} ({email})"
            )
            AscenderActionLog.objects.create(level="INFO", log=cleanup_log, ascender_data=job)
            LOGGER.info(cleanup_log)
        except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception):
            cleanup_log = f"Create new Entra ID user cleanup due to license assign failure: failed to delete orphaned Entra ID account {guid} ({email}), manual deletion required"
            AscenderActionLog.objects.create(level="WARNING", log=cleanup_log, ascender_data=job)
            LOGGER.exception(cleanup_log)

    return user_has_license


def create_entra_id_user(
    job: dict,
    cc: CostCentre,
    job_start_date: datetime,
    manager: DepartmentUser,
    location: Location,
    token: Optional[dict] = None,
    position_no: Optional[str] = None,
) -> DepartmentUser | None:
    """Create a new Entra ID user account based on supplied Ascender job data.

    Validates names, generates a DBCA email address, checks M365 licence availability,
    generates a compliant password, then (when not in dry-run mode) creates and configures
    the Entra ID account via the MS Graph API. Also creates the corresponding DepartmentUser
    record and emails the manager the provisioning checklist.

    Returns the new DepartmentUser on success, or None if any validation or API step fails.

    Safe to call with settings.ASCENDER_CREATE_AZURE_AD == False or settings.DEBUG == True;
    in either case all validation runs but the function returns None before making any
    mutating Graph API calls.
    """
    if not token:
        token = ms_graph_client_token()

    # Only create an account when the assigned manager already has one; the manager link
    # is required and must be set before the new account is enabled.
    if not manager.azure_guid:
        LOGGER.warning(f"Creation of new Entra ID account aborted, manager does not have Entra ID account ({manager})")
        return None

    ascender_record = f"{job['employee_id']}, {job['first_name']} {job['surname']}"
    job_end_date = None
    if job["job_end_date"] and datetime.strptime(job["job_end_date"], "%Y-%m-%d").date() != DATE_MAX:
        job_end_date = datetime.strptime(job["job_end_date"], "%Y-%m-%d").date()

    # --- Name validation and email generation ---
    # Surname is required, plus one of preferred_name or first_name.
    first_name, second_name, surname, preferred_name = _resolve_names(job)

    if not surname:
        _log_and_abort(f"Creation of new Entra ID account aborted, surname absent ({ascender_record})", job)
        return None
    if not preferred_name and not first_name:
        _log_and_abort(f"Creation of new Entra ID account aborted, first and preferred name both absent ({ascender_record})", job)
        return None

    email, mail_nickname = generate_valid_dbca_email(surname, preferred_name, first_name, second_name)
    if not email:
        _log_and_abort(f"Creation of new Entra ID account aborted at email step, unable to generate unique email ({ascender_record})", job)
        return None

    # --- Display name and job title ---
    # Set names to title case and strip trailing whitespace.
    if job["preferred_name"] and job["surname"]:
        display_name = f"{job['preferred_name'].title().strip()} {job['surname'].title().strip()}"
    elif job["first_name"] and job["surname"]:
        display_name = f"{job['first_name'].title().strip()} {job['surname'].title().strip()}"
    else:
        _log_and_abort(f"Creation of new Entra ID account aborted, first/preferred name absent ({ascender_record})", job)
        return None
    title = title_except(job["occup_pos_title"])

    # --- M365 licence availability check ---
    licence_type = _check_licence_availability(job["licence_type"], token, ascender_record)
    if not licence_type:
        return None

    # --- Password generation ---
    # Generate a random password and retry until it satisfies MS Graph complexity rules.
    # Reference: https://docs.python.org/3/library/secrets.html#secrets.token_urlsafe
    password = generate_password()
    while not ms_graph_validate_password(password):
        LOGGER.info("Generated password did not meet complexity requirements, retrying")
        password = generate_password()

    # --- Dry-run short-circuits ---
    # Honour these settings before making any mutating Graph API calls.
    if not settings.ASCENDER_CREATE_AZURE_AD:
        LOGGER.info(f"Skipping creation of new Entra ID account: {ascender_record} (ASCENDER_CREATE_AZURE_AD == False)")
        return None
    if settings.DEBUG:
        LOGGER.info(f"Skipping creation of new Entra ID account for emp ID {ascender_record} (DEBUG)")
        return None

    LOGGER.info(f"Creating new Entra ID account: {display_name}, {email}, {licence_type} account")

    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "Content-Type": "application/json",
    }

    # --- Step 1: Create the bare-minimum Entra ID user ---
    url = "https://graph.microsoft.com/v1.0/users"
    data = {
        "accountEnabled": False,
        "displayName": display_name,
        "userPrincipalName": email,
        "mailNickname": mail_nickname,
        "usageLocation": "AU",
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": password,
        },
    }
    resp = None
    try:
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        guid = resp.json()["id"]
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception):
        log = f"Create new Entra ID user failed at account creation step for {email}, most likely duplicate email account exists ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        resp_code = resp.status_code if resp is not None else "N/A"
        resp_content = resp.content if resp is not None else "N/A"
        _send_admin_failure_email(
            log,
            f"Ascender record:\n{job}\nRequest URL: {url}\nRequest body:\n{data}\nResponse code: {resp_code}\nResponse content:\n{resp_content}",
        )
        return None

    # --- Step 2: Patch additional user details ---
    sleep(3)
    url = f"https://graph.microsoft.com/v1.0/users/{guid}"
    data = {
        "mail": email,
        "employeeId": job["employee_id"],
        "givenName": job["preferred_name"].title().strip() if job["preferred_name"] else job["first_name"].title().strip(),
        "surname": job["surname"].title(),
        "jobTitle": title,
        "companyName": cc.code,
        "department": cc.get_division_name_display(),
        "officeLocation": location.name,
        "streetAddress": location.address,
        "state": "Western Australia",
    }
    resp = requests.patch(url, headers=headers, json=data)
    try:
        resp.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception):
        log = f"Create new Entra ID user failed at account update step for {email}, ask administrator to investigate ({ascender_record})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        _send_admin_failure_email(
            log,
            f"Ascender record:\n{job}\nRequest URL: {url}\nRequest body:\n{data}\nResponse code: {resp.status_code}\nResponse content:\n{resp.content}",
        )
        return None

    # --- Step 3: Assign the manager ---
    sleep(3)
    manager_url = f"https://graph.microsoft.com/v1.0/users/{guid}/manager/$ref"
    data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{manager.azure_guid}"}
    resp = requests.put(manager_url, headers=headers, json=data)
    try:
        resp.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException, Exception):
        log = f"Create new Entra ID user failed at assign manager update step for {email} (manager {manager})"
        AscenderActionLog.objects.create(level="ERROR", log=log, ascender_data=job)
        LOGGER.exception(log)
        _send_admin_failure_email(
            log,
            f"Ascender record:\n{job}\nRequest URL: {manager_url}\nRequest body:\n{data}\nResponse code: {resp.status_code}\nResponse content:\n{resp.content}",
        )
        return None

    # --- Step 4: Wait for usageLocation to propagate before assigning licences ---
    if not _wait_for_usage_location(guid, headers, job, email):
        return None

    # --- Step 5: Assign the M365 licence ---
    licence_payload = _build_licence_payload(licence_type)
    if not _assign_licence_with_retry(guid, headers, licence_payload, job, email, ascender_record):
        return None

    LOGGER.info(f"New Entra ID account created from Ascender data ({email})")

    # Create the corresponding DepartmentUser linked to the Ascender record and Entra ID account.
    new_user = department_user_create(job, guid, email, display_name, title, cc, location, manager, position_no)

    # Email the new account's manager the provisioning checklist.
    email_sent = new_user_creation_email(new_user, manager, licence_type, job_start_date, job_end_date)
    if email_sent:
        LOGGER.info(f"ASCENDER SYNC: Emailed {manager.email} about new user account creation")
    else:
        LOGGER.error("ASCENDER SYNC: no email sent regarding new user account creation")

    return new_user


def generate_valid_dbca_email(
    surname: str, preferred_name: str = "", first_name: str = "", second_name: str = ""
) -> tuple[str, str] | tuple[None, None]:
    # New DBCA email address generation.
    # Make no assumption about names (presence or absence) other than surname.
    # Email patterns in order of preference:
    # 1. {preferred_name}.{surname}@dbca.wa.gov.au
    # 2. {preferred_name}{second_name}.{surname}@dbca.wa.gov.au
    # 3. {first_name}.{surname}@dbca.wa.gov.au
    # 4. {first_name}{second_name}.{surname}@dbca.wa.gov.au
    # If we can't make a new unique (according to current records) email, return a null result.

    # First, lowercase any supplied name values.
    surname = surname.lower()
    preferred_name = preferred_name.lower()
    first_name = first_name.lower()
    second_name = second_name.lower()

    if preferred_name and surname:
        email_patterns = [
            f"{preferred_name}.{surname}@dbca.wa.gov.au",
            f"{preferred_name}{second_name}.{surname}@dbca.wa.gov.au",
        ]
        for pattern in email_patterns:
            if not DepartmentUser.objects.filter(email=pattern).exists():
                email = pattern
                mail_nickname = pattern.split("@")[0]
                return (email, mail_nickname)
    elif first_name and surname:
        email_patterns = [
            f"{first_name}.{surname}@dbca.wa.gov.au",
            f"{first_name}{second_name}.{surname}@dbca.wa.gov.au",
        ]
        for pattern in email_patterns:
            if not DepartmentUser.objects.filter(email=pattern).exists():
                email = pattern
                mail_nickname = pattern.split("@")[0]
                return (email, mail_nickname)

    return (None, None)


def department_user_create(
    job: dict,
    azure_guid: str,
    email: str,
    display_name: str,
    title: str,
    cc: CostCentre,
    location: Location,
    manager: DepartmentUser,
    position_no: Optional[str] = None,
) -> DepartmentUser:
    """This helper function is split from the Entra ID 'create' function to allow for unit testing.
    It creates a new DepartmentUser object, an initial Django admin LogEntry, an AscenderActionLog for record-keeping,
    then returns the new DepartmentUser object."""
    given_name = job["preferred_name"].title().strip() if job["preferred_name"] else job["first_name"].title().strip()
    new_user = DepartmentUser.objects.create(
        azure_guid=azure_guid,
        active=False,
        email=email,
        name=display_name,
        given_name=given_name,
        surname=job["surname"].title(),
        preferred_name=job["preferred_name"].title().strip() if job["preferred_name"] else None,
        title=title,
        employee_id=job["employee_id"],
        cost_centre=cc,
        location=location,
        manager=manager,
        ascender_data=job,
        ascender_data_updated=timezone.localtime(),
        position_no=position_no,
    )

    # Create an admin log entry for initial creation of the new user.
    try:
        user = User.objects.order_by("pk").first()  # Admin user
    except Exception:
        # Handle the edge case of not having an admin user object available.
        user = None

    if user:
        LogEntry.objects.log_actions(
            user_id=user.pk,
            queryset=DepartmentUser.objects.filter(pk=new_user.pk),
            action_flag=ADDITION,
            change_message="System-generated initial version created",
            single_object=True,
        )

    ascender_record = f"{job['employee_id']}, {job['first_name']} {job['surname']}"
    log = f"Created new department user {new_user} ({ascender_record})"
    AscenderActionLog.objects.create(level="INFO", log=log, ascender_data=job)
    LOGGER.info(log)

    return new_user


def new_user_creation_email(
    new_user: DepartmentUser,
    manager: DepartmentUser,
    licence_type: str,
    job_start_date: datetime,
    job_end_date: Optional[datetime] = None,
) -> bool:
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
    text_content = f"""Hi {manager.given_name},\n\n
This is an automated email to confirm that a new user account has been created, using the information that was provided in Ascender. The details are:\n\n
Name: {new_user.name}\n
Employee ID: {new_user.employee_id}\n
Email: {new_user.email}\n
Title: {new_user.title}\n
Position number: {new_user.ascender_data["position_no"]}\n
Cost centre: {new_user.cost_centre}\n
Division: {new_user.cost_centre.get_division_name_display()}\n
Organisational unit: {unit}\n
Employment status: {new_user.ascender_data["emp_stat_desc"]}\n
M365 licence: {licence_type}\n
Manager: {new_user.manager.name}\n
Location: {new_user.location}\n
Job start date: {job_start_date.strftime("%d/%b/%Y")}\n\n
Job end date: {job_end_date.strftime("%d/%b/%Y") if job_end_date else ""}\n\n
Cost centre manager: {new_user.cost_centre.manager.name if new_user.cost_centre.manager else ""}\n\n
OIM Service Desk will now complete the new account and provide you with confirmation and instructions for the new user.\n\n
Regards,\n\n
OIM Service Desk\n"""
    html_content = f"""<p>Hi {manager.given_name},</p>
<p>This is an automated email to confirm that a new user account has been created, using the information that was provided in Ascender. The details are:</p>
<ul>
<li>Name: {new_user.name}</li>
<li>Employee ID: {new_user.employee_id}</li>
<li>Email: {new_user.email}</li>
<li>Title: {new_user.title}</li>
<li>Position number: {new_user.ascender_data["position_no"]}</li>
<li>Cost centre: {new_user.cost_centre}</li>
<li>Division: {new_user.cost_centre.get_division_name_display()}</li>
<li>Organisational unit: {unit}</li>
<li>Employment status: {new_user.ascender_data["emp_stat_desc"]}</li>
<li>M365 licence: {licence_type}</li>
<li>Manager: {new_user.manager.name}</li>
<li>Location: {new_user.location}</li>
<li>Job start date: {job_start_date.strftime("%d/%b/%Y")}</li>
<li>Job end date: {job_end_date.strftime("%d/%b/%Y") if job_end_date else ""}</li>
<li>Cost centre manager: {new_user.cost_centre.manager.name if new_user.cost_centre.manager else ""}</li>
</ul>
<p>OIM Service Desk will now complete the new account and provide you with confirmation and instructions for the new user.</p>
<p>Regards,</p>
<p>OIM Service Desk</p>"""
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.NOREPLY_EMAIL,
        to=[manager.email],
        cc=[settings.SERVICE_DESK_EMAIL],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)

    return True


def ascender_cc_manager_fetch() -> List[tuple]:
    """Returns all records from cc_manager_view."""
    conn = get_ascender_db_connection()
    cursor = conn.cursor()
    schema = sql.Identifier(settings.FOREIGN_SCHEMA)
    table = sql.Identifier(settings.FOREIGN_TABLE_CC_MANAGER)
    query = sql.SQL("SELECT * FROM {schema}.{table}").format(schema=schema, table=table)
    cursor.execute(query)
    return cursor.fetchall()
