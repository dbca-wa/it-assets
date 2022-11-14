from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from fuzzywuzzy import fuzz
import logging
import psycopg2
import pytz
import random
import requests
import string

from itassets.utils import ms_graph_client_token
from organisation.microsoft_products import MS_PRODUCTS
from organisation.models import DepartmentUser, DepartmentUserLog, CostCentre, Location
from organisation.utils import title_except, ms_graph_subscribed_sku

LOGGER = logging.getLogger('organisation')
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
    "loc_desc",
    "paypoint",
    "paypoint_desc",
    "geo_location_desc",
    "occup_type",
    ("job_start_date", lambda record, val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None),
    ("job_end_date", lambda record, val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None),
    "term_reason",
    "work_phone_no",
    "work_mobile_phone_no",
    "email_address",
    "extended_lv",
    ("ext_lv_end_date", lambda record, val: val.strftime("%Y-%m-%d") if val and val != DATE_MAX else None),
    "licence_type",
    "manager_emp_no",
    "manager_name",
)
FOREIGN_DB_QUERY_SQL = 'SELECT {} FROM "{}"."{}" ORDER BY employee_no;'.format(
    ", ".join(
        f[0] if isinstance(f, (list, tuple)) else f for f in FOREIGN_TABLE_FIELDS if (f[0] if isinstance(f, (list, tuple)) else f)
    ),
    settings.FOREIGN_SCHEMA,
    settings.FOREIGN_TABLE,
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
    Returns an integer value to "sort" a job, based on job end date and employment status type.
    The calculated score will be lower for jobs that have ended, and modified by where the employment
    status occurs in a ordered list (STATUS_RANKING). Jobs with no end date or with an end date in the
    future will have the same initial score, and are then modified by the employment status.

    1. The initial score is based on the job's end date (closer date == lower score).
      - If the job has ended, the initial score is calculated using the job's end date.
      - If the job is not ended or has no end date recorded, the initial score is calculated from tommorrow's date.
    2. The score is then modified based on emp_status, with values later in the list scoring higher.

    """
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    # Initial score from job_end_date.
    if record["job_end_date"] and record["job_end_date"] <= today.strftime("%Y-%m-%d"):
        score = int(record["job_end_date"].replace("-", "")) * 10000
    else:
        score = int(tomorrow.strftime("%Y%m%d0000"))
    # Modify score based on emp_status.
    if record["emp_status"] and record["emp_status"] in STATUS_RANKING:
        score += (STATUS_RANKING.index(record["emp_status"]) + 1) * 100
    return score


def ascender_employee_fetch():
    """Returns an iterator of tuples (employee_id, [sorted employee jobs])
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


def ascender_db_import(employee_iter=None):
    """A utility function to cache data from Ascender to a matching DepartmentUser object.
    In addition, this function will create a new Azure AD account based on Ascender records
    that match a set of rules.
    """
    # If we're expecting to create new Azure AD accounts, get Microsoft Graph API token and available licences.
    if settings.ASCENDER_CREATE_AZURE_AD:
        LOGGER.info("Querying Microsoft 365 licence availability")
        token = ms_graph_client_token()
        e5_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 E5'], token)
        f3_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 F3'], token)
        eo_sku = ms_graph_subscribed_sku(MS_PRODUCTS['EXCHANGE ONLINE (PLAN 2)'], token)
        sec_sku = ms_graph_subscribed_sku(MS_PRODUCTS['MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW'], token)

    LOGGER.info("Querying Ascender database for employee information")
    if not employee_iter:
        employee_iter = ascender_employee_fetch()

    for eid, jobs in employee_iter:
        # ASSUMPTION: the "first" object in the list of Ascender jobs for each user is the current one.
        job = jobs[0]
        # Only look at non-FPC users.
        if job['clevel1_id'] == 'FPC':
            continue

        if DepartmentUser.objects.filter(employee_id=eid).exists():
            user = DepartmentUser.objects.get(employee_id=eid)

            # Check if the user already has Ascender data cached. If so, check if the position_no
            # value has changed. In that instance, create a DepartmentUserLog object.
            if user.ascender_data and 'position_no' in user.ascender_data and user.ascender_data['position_no'] != job['position_no']:
                DepartmentUserLog.objects.create(
                    department_user=user,
                    log={
                        'ascender_field': 'position_no',
                        'old_value': user.ascender_data['position_no'],
                        'new_value': job['position_no'],
                        'description': 'Update position_no value from Ascender',
                    },
                )

            user.ascender_data = job
            user.ascender_data_updated = TZ.localize(datetime.now())
            user.update_from_ascender_data()  # This method calls save()
        elif not DepartmentUser.objects.filter(employee_id=eid).exists() and settings.ASCENDER_CREATE_AZURE_AD:
            # ENTRY POINT FOR NEW AZURE AD USER ACCOUNT CREATION.
            # Parse job end date (if present). Ascender records "no end date" using a date far in the future (DATE_MAX).
            job_end_date = None
            if job['job_end_date'] and datetime.strptime(job['job_end_date'], '%Y-%m-%d').date() != DATE_MAX:
                job_end_date = datetime.strptime(job['job_end_date'], '%Y-%m-%d').date()
                # Short circuit: if job_end_date is in the past, skip account creation.
                if job_end_date < date.today():
                    continue

            # Start parsing required information for new account creation.
            licence_type = None
            cc = None
            job_start_date = None
            manager = None
            location = None
            ascender_record = f"{eid} ({job['first_name']} {job['surname']})"

            # Rule: user must have a valid M365 licence type recorded, plus we need to have an available M365 licence to allocate.
            # Short circuit: if there is no value for licence_type, skip account creation.
            if not job['licence_type'] or job['licence_type'] == 'NULL':
                continue
            elif job['licence_type']:
                if job['licence_type'] == 'ONPUL':
                    licence_type = 'On-premise'
                    # Short circuit: no available licences, abort.
                    if e5_sku['consumedUnits'] >= e5_sku['prepaidUnits']['enabled']:
                        subject = f"ASCENDER SYNC: create new Azure AD user aborted, no onprem E5 licences available (employee ID {eid})"
                        LOGGER.warning(subject)
                        continue
                elif job['licence_type'] == 'CLDUL':
                    licence_type = 'Cloud'
                    # Short circuit: no available licences, abort.
                    if f3_sku['consumedUnits'] >= f3_sku['prepaidUnits']['enabled']:
                        subject = f"ASCENDER SYNC: create new Azure AD user aborted, no Cloud F3 licences available (employee ID {eid})"
                        LOGGER.warning(subject)
                        continue
                    if eo_sku['consumedUnits'] >= eo_sku['prepaidUnits']['enabled']:
                        subject = f"ASCENDER SYNC: create new Azure AD user aborted, no Cloud Exchange Online licences available (employee ID {eid})"
                        LOGGER.warning(subject)
                        continue
                    if sec_sku['consumedUnits'] >= sec_sku['prepaidUnits']['enabled']:
                        subject = f"ASCENDER SYNC: create new Azure AD user aborted, no Cloud Security & Compliance licences available (employee ID {eid})"
                        LOGGER.warning(subject)
                        continue
                else:  # The only valid licence type values stored in Ascender are currentl ONPUL and CLDUL.
                    continue

            # Rule: user must have a manager recorded, and that manager must exist in our database.
            if job['manager_emp_no'] and DepartmentUser.objects.filter(employee_id=job['manager_emp_no']).exists():
                manager = DepartmentUser.objects.get(employee_id=job['manager_emp_no'])
            elif not job['manager_emp_no']:  # Short circuit: if there is no manager recorded, skip account creation.
                continue

            # Rule: user must have a Cost Centre recorded (paypoint in Ascender).
            if job['paypoint'] and CostCentre.objects.filter(ascender_code=job['paypoint']).exists():
                cc = CostCentre.objects.get(ascender_code=job['paypoint'])
            elif job['paypoint'] and not CostCentre.objects.filter(ascender_code=job['paypoint']).exists():
                # Attempt to automatically create a new CC from Ascender data, and send a notification to admins.
                try:
                    cc = CostCentre.objects.create(
                        code=job['paypoint'],
                        ascender_code=job['paypoint'],
                    )
                    subject = f"ASCENDER SYNC: create new Azure AD user process generated new cost centre, code {job['paypoint']}"
                    LOGGER.info(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                except:
                    # In the event of an error (probably due to a duplicate code), fail gracefully and alert the admins.
                    subject = f"ASCENDER SYNC: exception during creation of new cost centre in new Azure AD user process, code {job['paypoint']}"
                    LOGGER.error(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)

            # Rule: user must have a job start date recorded.
            if job['job_start_date']:
                job_start_date = datetime.strptime(job['job_start_date'], '%Y-%m-%d').date()
            else:  # Short circuit.
                continue

            # Secondary rule: we might set a limit for the number of days ahead of their starting date which we
            # want to create an Azure AD account. If this value is not set (False/None), assume that there is
            # no limit.
            if job['job_start_date'] and job_start_date and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS > 0:
                today = date.today()
                diff = job_start_date - today
                if diff.days > 0 and diff.days > settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS:
                    LOGGER.info(f"Skipping creation of new Azure AD user for emp ID {ascender_record} (exceeds start date limit of {settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS} days)")
                    continue  # Start start exceeds our limit, abort creating an AD account yet.

            # Rule: user must have a physical location recorded, and that location must exist in our database.
            if job['geo_location_desc'] and Location.objects.filter(ascender_desc=job['geo_location_desc']).exists():
                location = Location.objects.get(ascender_desc=job['geo_location_desc'])
            elif job['geo_location_desc'] and not Location.objects.filter(ascender_desc=job['geo_location_desc']).exists():  # geo_location_desc must at least have a value.
                # Attempt to manually create a new location description from Ascender data, and send a note to admins.
                try:
                    location = Location.objects.create(
                        name=job['geo_location_desc'],
                        ascender_desc=job['geo_location_desc'],
                        address=job['geo_location_desc'],
                    )
                    subject = f"ASCENDER SYNC: create new Azure AD user process generated new location, description {job['geo_location_desc']}"
                    LOGGER.info(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                except:
                    # In the event of an error (probably due to a duplicate name), fail gracefully and alert the admins.
                    subject = f"ASCENDER SYNC: exception during creation of new location in new Azure AD user process, description {job['geo_location_desc']}"
                    LOGGER.error(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)

            # Final short-circuit: skip creation of new AD accounts while in Debug mode (mainly to avoid blunders during dev/testing).
            if settings.DEBUG:
                LOGGER.info(f"Skipping creation of new Azure AD user for emp ID {ascender_record} (debug mode)")
                continue

            # If we have everything we need, embark on setting up the new user account.
            if cc and job_start_date and licence_type and manager and location:
                email = None
                mail_nickname = None

                # New email address generation.
                # Make no assumption about names (presence or absence). Remove any spaces within name text.
                if job['preferred_name'] and job['surname']:
                    pref_name = job['preferred_name'].lower().replace(' ', '')
                    surname = job['surname'].lower().replace(' ', '')
                    if job['second_name']:
                        sec = job['second_name'].lower().replace(' ', '')
                    else:
                        sec = ''
                    # Patterns used for new email address generation, in order of preference:
                    email_patterns = [
                        f"{pref_name}.{surname}@dbca.wa.gov.au",
                        f"{pref_name}{sec}.{surname}@dbca.wa.gov.au",
                    ]
                    for pattern in email_patterns:
                        if not DepartmentUser.objects.filter(email=pattern).exists():
                            email = pattern
                            mail_nickname = pattern.split("@")[0]
                            break
                elif job['first_name'] and job['surname']:
                    first_name = job['first_name'].lower().replace(' ', '')
                    surname = job['surname'].lower().replace(' ', '')
                    if job['second_name']:
                        sec = job['second_name'].lower().replace(' ', '')
                    else:
                        sec = ''
                    # Patterns used for new email address generation, in order of preference:
                    email_patterns = [
                        f"{first_name}.{surname}@dbca.wa.gov.au",
                        f"{first_name}{sec}.{surname}@dbca.wa.gov.au",
                    ]
                    for pattern in email_patterns:
                        if not DepartmentUser.objects.filter(email=pattern).exists():
                            email = pattern
                            mail_nickname = pattern.split("@")[0]
                            break
                else:  # No preferred/first name recorded.
                    LOGGER.warning(f"ASCENDER SYNC: create new Azure AD user aborted, invalid name values (employee ID {eid})")
                    continue

                if not email and mail_nickname:
                    # We can't generate a unique email with the supplied information; abort.
                    LOGGER.warning(f"ASCENDER SYNC: create new Azure AD user aborted at email, invalid name values (employee ID {eid})")
                    continue

                # Display name generation. Set names to title case and strip trailing space.
                if job['preferred_name'] and job['surname']:
                    display_name = f"{job['preferred_name'].title().strip()} {job['surname'].title().strip()}"
                elif job['first_name'] and job['surname']:
                    display_name = f"{job['first_name'].title().strip()} {job['surname'].title().strip()}"
                else:  # No preferred/first name recorded.
                    LOGGER.warning(f"ASCENDER SYNC: create new Azure AD user aborted at display name, invalid name values (employee ID {eid})")
                    continue
                title = title_except(job['occup_pos_title'])

                # Ensure that the generated password meets our security complexity requirements.
                p = list('Pass1234' + ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(12)))
                random.shuffle(p)
                password = ''.join(p)
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                LOGGER.info(f"ASCENDER SYNC: Creating new Azure AD account: {display_name}, {email}, {licence_type} account")

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
                        }
                    }
                    resp = requests.post(url, headers=headers, json=data)
                    resp.raise_for_status()
                    resp_json = resp.json()
                    guid = resp_json['id']
                except:
                    subject = f"ASCENDER SYNC: create new Azure AD user failed at initial creation step ({email})"
                    LOGGER.exception(subject)
                    text_content = f"""Ascender record:\n
                    {job}\n
                    Request URL: {url}\n
                    Request body:\n
                    {data}\n
                    Response code: {resp.status_code}\n
                    Response content:\n
                    {resp.content}\n"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                    continue

                # Next, update the user details with additional information.
                try:
                    url = f"https://graph.microsoft.com/v1.0/users/{guid}"
                    data = {
                        "mail": email,
                        "employeeId": eid,
                        "givenName": job['preferred_name'].title().strip() if job['preferred_name'] else job['first_name'].title().strip(),
                        "surname": job['surname'].title(),
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
                    subject = f"ASCENDER SYNC: create new Azure AD user failed at update step ({email})"
                    LOGGER.exception(subject)
                    text_content = f"""Ascender record:\n
                    {job}\n
                    Request URL: {url}\n
                    Request body:\n
                    {data}\n
                    Response code: {resp.status_code}\n
                    Response content:\n
                    {resp.content}\n"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                    continue

                # Next, set the user manager.
                try:
                    manager_url = f"https://graph.microsoft.com/v1.0/users/{guid}/manager/$ref"
                    data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{manager.azure_guid}"}
                    resp = requests.put(manager_url, headers=headers, json=data)
                    resp.raise_for_status()
                except:
                    subject = f"ASCENDER SYNC: create new Azure AD user failed at assign manager step ({email})"
                    LOGGER.exception(subject)
                    text_content = f"""Ascender record:\n
                    {job}\n
                    Request URL: {url}\n
                    Request body:\n
                    {data}\n
                    Response code: {resp.status_code}\n
                    Response content:\n
                    {resp.content}\n"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                    continue

                # Next, add the required licenses to the user.
                try:
                    url = f"https://graph.microsoft.com/v1.0/users/{guid}/assignLicense"
                    if licence_type == "On-premise":
                        data = {
                            "addLicenses": [
                                {"skuId": MS_PRODUCTS['MICROSOFT 365 E5'], "disabledPlans": []},
                            ],
                            "removeLicenses": [],
                        }
                    elif licence_type == "Cloud":
                        data = {
                            "addLicenses": [
                                {"skuId": MS_PRODUCTS['MICROSOFT 365 F3'], "disabledPlans": [MS_PRODUCTS['EXCHANGE ONLINE KIOSK'],]},
                                {"skuId": MS_PRODUCTS['EXCHANGE ONLINE (PLAN 2)'], "disabledPlans": []},
                                {"skuId": MS_PRODUCTS['MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW'], "disabledPlans": [MS_PRODUCTS['EXCHANGE ONLINE ARCHIVING'],]},
                            ],
                            "removeLicenses": [],
                        }
                    resp = requests.post(url, headers=headers, json=data)
                    resp.raise_for_status()
                except:
                    subject = f"ASCENDER SYNC: create new Azure AD user failed at assign license step ({email})"
                    LOGGER.exception(subject)
                    text_content = f"""Ascender record:\n
                    {job}\n
                    Request URL: {url}\n
                    Request body:\n
                    {data}\n
                    Response code: {resp.status_code}\n
                    Response content:\n
                    {resp.content}\n"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                    continue

                # TODO: we don't currently add groups to the user (performed manually by SD staff)
                # because the organisation is not consistent in the usage of group types, and we
                # can't administer some group types via the Graph API.
                '''
                # Next, add user to the minimum set of M365 groups.
                dbca_guid = "329251f6-ff18-4015-958a-55085c641cdd"
                # Below are Azure GUIDs for the M365 groups for each division, mapped to the division code
                # (used in the CostCentre model).
                division_group_guids = {
                    "BCS": "003ea951-4f8b-44cb-bf53-9efd968002b2",
                    "BGPA": "cb59632a-f1dc-490b-b2f1-1a6eb469e56d",
                    "CBS": "1b2777c4-4bd9-4a49-9f02-41a71ab69c1f",
                    "ODG": "fbe3c349-fcc2-4ad1-92f6-337fb977b1b6",
                    "PWS": "64016b08-3466-4053-ba7c-713c8c7b5eeb",
                    "RIA": "128f4b94-98b0-4361-955c-5cdfda65b4f6",
                    "ZPA": "09b543ba-4cde-459a-a159-077bf2640c0e",
                }
                try:
                    data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{guid}"}
                    # DBCA group
                    url = f"https://graph.microsoft.com/v1.0/groups/{dbca_guid}/members/$ref"
                    resp = requests.post(url, headers=headers, json=data)
                    resp.raise_for_status()
                    # Division group
                    if cc.division_name in division_group_guids:
                        division_guid = division_group_guids[cc.code]
                        url = f"https://graph.microsoft.com/v1.0/groups/{division_guid}/members/$ref"
                        resp = requests.post(url, headers=headers, json=data)
                        resp.raise_for_status()
                except:
                    subject = f"ASCENDER SYNC: create new Azure AD user failed at assign M365 groups step ({email})"
                    LOGGER.exception(subject)
                    text_content = f"""Ascender record:\n
                    {job}\n
                    Request URL: {url}\n
                    Request body:\n
                    {data}\n
                    Response code: {resp.status_code}\n
                    Response content:\n
                    {resp.content}\n"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                    continue
                '''

                subject = f"ASCENDER_SYNC: New Azure AD account created from Ascender data ({email})"
                text_content = f"""New account record:\n
                {job}\n
                Azure GUID: {guid}\n
                Employee ID: {eid}\n
                Email: {email}\n
                Mail nickname: {mail_nickname}\n
                Display name: {display_name}\n
                Title: {title}\n
                Cost centre: {cc}\n
                Division: {cc.get_division_name_display()}\n
                Licence: {licence_type}\n
                Manager: {manager}\n
                Location: {location}\n
                Job start date: {job_start_date.strftime('%d/%b/%Y')}\n\n"""
                msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                msg.send(fail_silently=True)

                # Next, create a new DepartmentUser that is linked to the Ascender record and the Azure AD account.
                new_user = DepartmentUser.objects.create(
                    azure_guid=guid,
                    active=False,
                    email=email,
                    name=display_name,
                    given_name=job['preferred_name'].title().strip() if job['preferred_name'] else job['first_name'].title().strip(),
                    surname=job['surname'].title(),
                    title=title,
                    employee_id=eid,
                    cost_centre=cc,
                    location=location,
                    manager=manager,
                    ascender_data=job,
                    ascender_data_updated=TZ.localize(datetime.now()),
                )
                LOGGER.info(f"ASCENDER SYNC: Created new department user {new_user}")

                # Email the new account's manager the checklist to finish account provision.
                new_user_creation_email(new_user, licence_type, job_start_date, job_end_date)
                LOGGER.info(f"ASCENDER SYNC: Emailed {new_user.manager.email} about new user account creation")
            else:
                if licence_type:  # Everything else can still be False.
                    # If we had a candidate for a new account creation (they don't currently exist in OIM data, but they have a licence type recorded in Ascender), send a notification to admins.
                    subject = "ASCENDER SYNC: New account candidate creation skipped"
                    text_content = f"Employee ID: {eid}, Name: {job['first_name']} {job['surname']},  CC: {cc}, Start date: {job_start_date}, Licence: {licence_type}, Manager: {manager}, Location: {location}"
                    LOGGER.warning(subject)
                    LOGGER.info(text_content)
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)


def new_user_creation_email(new_user, licence_type, job_start_date, job_end_date=None):
    """This email function is split from the 'create' step so that it can be called again in the event of failure.
    Note that we can't call new_user.get_licence_type() because we probably haven't synced M365 licences to the department user yet.
    We also require the user's job start and end dates (end date may be None).
    """
    org_path = new_user.get_ascender_org_path()
    if org_path and len(org_path) > 1:
        org_unit = org_path[1]
    else:
        org_unit = ''
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
Organisational unit: {org_unit}\n
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
<li>Organisational unit: {org_unit}</li>
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


def get_ascender_matches():
    """For users with no employee ID, return a list of lists of possible Ascender matches in the format:
    [IT ASSETS PK, IT ASSETS NAME, ASCENDER NAME, EMPLOYEE ID]
    """
    dept_users = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER, employee_id__isnull=True, given_name__isnull=False, surname__isnull=False)
    ascender_data = ascender_employee_fetch()
    possible_matches = []
    ascender_jobs = []

    for eid, jobs in ascender_data:
        ascender_jobs.append(jobs[0])

    for user in dept_users:
        for data in ascender_jobs:
            if data['first_name'] and data['surname'] and not DepartmentUser.objects.filter(employee_id=data['employee_id']).exists():
                sn_ratio = fuzz.ratio(user.surname.upper(), data['surname'].upper())
                fn_ratio = fuzz.ratio(user.given_name.upper(), data['first_name'].upper())
                if sn_ratio > 80 and fn_ratio > 65:
                    possible_matches.append([
                        user.pk,
                        user.name,
                        '{} {}'.format(data['first_name'], data['surname']),
                        data['employee_id'],
                    ])
                    continue

    return possible_matches


def ascender_cc_manager_fetch():
    """Returns all records from cc_manager_view.
    """
    conn = psycopg2.connect(
        host=settings.FOREIGN_DB_HOST,
        port=settings.FOREIGN_DB_PORT,
        database=settings.FOREIGN_DB_NAME,
        user=settings.FOREIGN_DB_USERNAME,
        password=settings.FOREIGN_DB_PASSWORD,
    )
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
    """Queries cc_manager_view and updates the cost centre manager for each.
    """
    records = ascender_cc_manager_fetch()
    for r in records:
        if CostCentre.objects.filter(ascender_code=r[1]).exists():
            cc = CostCentre.objects.get(ascender_code=r[1])
            if DepartmentUser.objects.filter(employee_id=r[6]).exists():
                cc.manager = DepartmentUser.objects.get(employee_id=r[6])
                cc.save()
