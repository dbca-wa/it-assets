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
from organisation.models import DepartmentUser, DepartmentUserLog, CostCentre, Location
from organisation.utils import title_except

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
    "PFAS",
    "PFA",
    "PFT",
    "CFA",
    "CFT",
    "PPA",
    "PPT",
    "CPA",
    "CPT",
    "CCFA",
    "CAS",
    "SEAS",
    "TRAIN",
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
    # Initial score from job_end_date
    score = (
        (int(record["job_end_date"].replace("-", "")) * 10000)
        if record["job_end_date"]
        and record["job_end_date"] <= today.strftime("%Y-%m-%d")
        else int(tomorrow.strftime("%Y%m%d0000"))
    )
    # Second score based emp_status
    score += (
        (STATUS_RANKING.index(record["emp_status"]) + 1)
        if (record["emp_status"] in STATUS_RANKING) else 0
    ) * 100
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
    if not employee_iter:
        employee_iter = ascender_employee_fetch()

    for eid, jobs in employee_iter:
        # ASSUMPTION: the "first" object in the list of Ascender jobs for each user is the current one.
        job = jobs[0]
        # Only look at non-FPC users.
        if job['clevel1_id'] != 'FPC':
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

                # Short circuit: if there is no value for licence_type, skip account creation.
                if not job['licence_type'] or job['licence_type'] == 'NULL':
                    continue

                cc = None
                job_start_date = None
                licence_type = None
                manager = None
                location = None

                # Rule: user must have a CC recorded, and that CC must exist in our database.
                if job['paypoint'] and CostCentre.objects.filter(ascender_code=job['paypoint']).exists():
                    cc = CostCentre.objects.get(ascender_code=job['paypoint'])
                else:
                    # Email an alert that a new CC exists.
                    subject = f"ASCENDER SYNC: create new Azure AD user process encountered new cost centre {job['paypoint']}"
                    LOGGER.warning(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)
                # Rule: user must have a job start date recorded.
                if job['job_start_date']:
                    job_start_date = datetime.strptime(job['job_start_date'], '%Y-%m-%d').date()
                # Secondary rule: we might set a limit for the number of days ahead of their starting date which we
                # want to create an Azure AD account. If this value is not set (False/None), assume that there is
                # no limit.
                if job['job_start_date'] and job_start_date and settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS:
                    today = date.today()
                    diff = job_start_date - today
                    if diff.days > settings.ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS:
                        job_start_date = None  # Start start exceeds our limit, clear this so that we don't create an AD account yet.
                # Rule: user must have a valid M365 licence type recorded.
                if job['licence_type']:
                    if job['licence_type'] == 'ONPUL':
                        licence_type = 'On-premise'
                    elif job['licence_type'] == 'CLDUL':
                        licence_type = 'Cloud'
                # Rule: user must have a manager recorded, and that manager must exist in our database.
                if job['manager_emp_no'] and DepartmentUser.objects.filter(employee_id=job['manager_emp_no']).exists():
                    manager = DepartmentUser.objects.get(employee_id=job['manager_emp_no'])
                # Rule: user must have a physical location recorded, and that location must exist in our database.
                if job['geo_location_desc'] and Location.objects.filter(ascender_desc=job['geo_location_desc']).exists():
                    location = Location.objects.get(ascender_desc=job['geo_location_desc'])
                else:
                    # Email an alert that a new geo_location_desc exists.
                    subject = f"ASCENDER SYNC: create new Azure AD user process encountered new location description {job['geo_location_desc']}"
                    LOGGER.warning(subject)
                    text_content = f"""Ascender record:\n
                    {job}"""
                    msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                    msg.send(fail_silently=True)

                if cc and job_start_date and licence_type and manager and location:
                    email = None
                    # Make no assumption about names (presence or absence).
                    if job['preferred_name']:
                        pref = job['preferred_name'].lower().replace(' ', '')
                    else:
                        pref = ''
                    if job['first_name']:
                        first = job['first_name'].lower().replace(' ', '')
                    else:
                        first = ''
                    if job['second_name']:
                        sec = job['second_name'].lower().replace(' ', '')
                    else:
                        sec = ''
                    if job['surname']:
                        sur = job['surname'].lower().replace(' ', '')
                    else:
                        sur = ''
                    if not DepartmentUser.objects.filter(email=f"{pref}.{sur}@dbca.wa.gov.au").exists():
                        email = f"{pref}.{sur}@dbca.wa.gov.au"
                        mail_nickname = f"{pref}.{sur}"
                    elif not DepartmentUser.objects.filter(email=f"{first}.{sur}@dbca.wa.gov.au").exists():
                        email = f"{first}.{sur}@dbca.wa.gov.au"
                        mail_nickname = f"{first}.{sur}"
                    elif not DepartmentUser.objects.filter(email=f"{pref}{sec}.{sur}@dbca.wa.gov.au").exists():
                        email = f"{pref}{sec}.{sur}@dbca.wa.gov.au"
                        mail_nickname = f"{pref}{sec}.{sur}"
                    elif not DepartmentUser.objects.filter(email=f"{first}{sec}.{sur}@dbca.wa.gov.au").exists():
                        email = f"{first}{sec}.{sur}@dbca.wa.gov.au"
                        mail_nickname = f"{first}{sec}.{sur}"
                    else:
                        # We can't generate a unique email with the supplied information; abort and send a note to the admins.
                        # This email should pick up instances where the function can't match any existing CC, manager or location
                        # and allow manual intervention.
                        subject = f"ASCENDER SYNC: create new Azure AD user failed, unable to generate unique email"
                        text_content = f"Ascender record:\n{job}\n"
                        msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, settings.ADMIN_EMAILS)
                        msg.send(fail_silently=True)
                        continue
                    display_name = f"{job['preferred_name'].title()} {job['surname'].title()}"
                    title = title_except(job['occup_pos_title'])
                    # Ensure that the generated password meets our security complexity requirements.
                    p = list('Pass1234' + ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(12)))
                    random.shuffle(p)
                    password = ''.join(p)
                    token = ms_graph_client_token()
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
                            "givenName": job['preferred_name'].title(),
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
                                    {"skuId": "06ebc4ee-1bb5-47dd-8120-11324bc54e06", "disabledPlans": []},  # MICROSOFT 365 E5
                                ],
                                "removeLicenses": [],
                            }
                        elif licence_type == "Cloud":
                            data = {
                                "addLicenses": [
                                    {"skuId": "66b55226-6b4f-492c-910c-a3b7a3c9d993", "disabledPlans": ['4a82b400-a79f-41a4-b4e2-e94f5787b113']},  # MICROSOFT 365 F3
                                    {"skuId": "19ec0d23-8335-4cbd-94ac-6050e30712fa", "disabledPlans": []},  # EXCHANGE ONLINE (PLAN 2)
                                    {"skuId": "2347355b-4e81-41a4-9c22-55057a399791", "disabledPlans": ['176a09a6-7ec5-4039-ac02-b2791c6ba793']},  # MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW
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
                        given_name=job['preferred_name'].title(),
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
