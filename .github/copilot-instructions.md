# GitHub Copilot Instructions — IT Assets

## Project overview

IT Assets is a Django 5.2 web application built for the Department of Biodiversity, Conservation and Attractions (DBCA) in Western Australia. It serves as the authoritative register for:

- **Staff accounts** — `DepartmentUser` records linked to both Ascender (the department's HRMIS) and Microsoft Entra ID (Azure AD). The system syncs staff data from Ascender and uses the Microsoft Graph API to provision, update, and audit M365 accounts.
- **IT systems** — `ITSystem` records cataloguing production, development, and decommissioned software used by the department.
- **Organisational structure** — `CostCentre` and `Location` models representing the department's financial and physical structure.

The primary audience is the Office of Information Management (OIM) / Service Desk team, who use the Django admin and a suite of management commands to manage accounts and licences. An address book and REST API (`/api/v3/`) are also consumed by other DBCA services.

## Python environment

Always activate the local virtualenv before running any Python or Django commands:

```sh
source .venv/bin/activate
```

All `python`, `manage.py`, `ruff`, and `coverage` commands should be run inside this activated environment.

## Build, test, and lint commands

```sh
# Install dependencies
uv sync

# Run the development server
python manage.py runserver 0:8080

# Run all tests (requires PostGIS database)
coverage run manage.py test --keepdb
coverage report -m

# Run a single test module or class
python manage.py test organisation.tests.test_api --keepdb
python manage.py test organisation.tests.test_api.DepartmentUserAPIResourceTestCase --keepdb

# Lint with ruff
ruff check .
ruff format .
```

> Tests require a running PostGIS database. Set `DATABASE_URL="postgis://USER:PASSWORD@HOST:PORT/DBNAME"` in `.env`. The CI workflow uses `postgis/postgis:15-3.4-alpine`.

## Architecture

This is a Django 5.2 application (Python ≥ 3.13) for DBCA's IT asset and staff management.

**Two Django apps:**

- **`organisation`** — Core app. Manages `DepartmentUser`, `CostCentre`, and `Location` models. Syncs staff data from Ascender (HRMIS via SFTP or foreign PostgreSQL table) and Microsoft Entra ID (via MS Graph API). Contains the bulk of the business logic and management commands.
- **`registers`** — Manages IT systems (`ITSystem`) and related records. Lighter in scope.

**Two admin sites:**

- Default Django admin at `/admin/` — full access
- Custom `service_desk_admin_site` at `/service-desk-admin/` — scoped for service desk staff; this is the default redirect at `/`

**REST API at `/api/v3/`** — Custom class-based views (`View` subclasses returning `JsonResponse`), not Django REST Framework. Resources: `DepartmentUser`, `Location`, `License`, `ITSystem`, `CostCentre`.

**External integrations:**

- **Ascender** (HR system): data fetched via SFTP (CSV) or a PostgreSQL foreign data wrapper. Logic lives in `organisation/ascender.py`.
- **Microsoft Graph API**: Entra ID account sync, licence management. Tokens obtained via `itassets/utils.py:ms_graph_client_token()` using MSAL `ConfidentialClientApplication`.
- **Azure Blob Storage**: Used for media file storage by default (`django-storages`). Set `LOCAL_MEDIA_STORAGE=True` to use local filesystem instead.

**Management commands** in `organisation/management/commands/` handle scheduled sync jobs (e.g., `check_ascender_accounts`, `department_users_sync_ad_data`, `azure_account_provision`).

## Key conventions

**Settings via environment variables:** All runtime config uses `dbca_utils.utils.env()`. Required vars: `DATABASE_URL`, `SECRET_KEY`. See `itassets/settings.py` for the full list.

**Test fixtures with `mixer`:** Tests use `mixer.backend.django.mixer` (from the `mixer` package) to generate model instances. The shared base class `ApiTestCase` in `itassets/test_api.py` sets up a standard fixture (users, cost centres, locations, IT systems) for API tests. Inherit from it for new API tests.

**`ModelDescMixin`** (`itassets/utils.py`): Applied to `ModelAdmin` subclasses to inject a `model_description` into the changelist template context. If you add a model admin that needs a description banner, use this mixin and set `model_description` on the class.

**GIS fields:** `DepartmentUser` uses `django.contrib.gis.db.models`. The database must be PostGIS. The `SERIALIZATION_MODULES` setting enables GeoJSON serialisation.

**Ruff config:** Line length 140, `migrations/` excluded. Bare `except` and long-line warnings are suppressed (`E722`, `E501`).

**Caching:** Redis if `REDIS_CACHE_HOST` is set; falls back to `DummyCache`. API response cache duration is controlled via `API_RESPONSE_CACHE_SECONDS`.

**Date/time:** Timezone is `Australia/Perth`. Date input accepts `dd/mm/yyyy` and variants (not ISO 8601 order). `settings.TZ` holds the `ZoneInfo` object for use in Python code.

## Ascender sync flow

Ascender is DBCA's HRMIS. The sync pipeline lives entirely in `organisation/ascender.py`.

### Data source

Ascender data is read from a **PostgreSQL foreign data wrapper** — a view in a remote database exposed via `psycopg` using the `FOREIGN_DB_*` settings. The columns fetched are defined in `FOREIGN_TABLE_FIELDS`, a tuple of either bare field names or `(source_col, dest_key_or_callable)` tuples for renaming and/or transforming values. `row_to_python()` applies these transforms when iterating rows.

Each employee can have **multiple job rows** in Ascender (one per concurrent or historical position). `ascender_employees_fetch_all()` groups rows by `employee_id` and sorts each employee's job list using `ascender_job_sort_key()`. The sort gives highest priority to jobs with a future end date, then jobs with no end date, then expired jobs. The first job in this sorted list is used as the "current" job, unless the `DepartmentUser.position_no` field is set to manually pin a specific Ascender `position_no`.

### The main sync (`check_ascender_accounts`)

`ascender_user_import_all()` is the bulk sync function. For every employee returned from Ascender:

1. **FPC users are skipped** (`clevel1_id == "FPC"`).
2. **Location auto-creation:** if a new `geo_location_desc` is encountered, a `Location` is created automatically.
3. **Existing `DepartmentUser`:** cache the selected job dict to `DepartmentUser.ascender_data`, record a `DepartmentUserLog` entry if `position_no` changed, then call `user.update_from_ascender_data()` which propagates relevant Ascender fields (title, phone, cost centre, location, account type, etc.) and saves.
4. **New employee:** run `validate_ascender_user_account_rules()` — if all rules pass, call `create_entra_id_user()` to provision the Entra ID account and create the `DepartmentUser`.

### Account provisioning rules (`validate_ascender_user_account_rules`)

A new Entra ID account is only provisioned when **all** of the following hold:

| Rule | Detail |
|------|--------|
| Not FPC | `clevel1_id != "FPC"` |
| No existing `DepartmentUser` | Matched by `employee_id` |
| Job end date not in the past | `job_end_date` must be future or absent |
| M365 licence type set | `licence_type` must be `ONPUL` (E5/on-premise) or `CLDUL` (F3/cloud) |
| Manager exists in our DB | Looked up by `manager_emp_no`; overridable via `manager_override_email` |
| Cost centre exists | Matched by Ascender `paypoint`; auto-created if missing |
| Job start date present and not past | Can be bypassed with `ignore_job_start_date=True` |
| Start date within look-ahead limit | Controlled by `ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS` |
| Physical location exists in our DB | Matched by `ascender_desc`; NOT auto-created at this step |

`validate_ascender_user_account_rules()` returns either `False` or a tuple `(job, cc, job_start_date, licence_type, manager, location)`.

### `create_entra_id_user()`

1. Checks that the assigned manager has an `azure_guid`.
2. Calls `generate_valid_dbca_email()` to derive a unique `@dbca.wa.gov.au` UPN.
3. Checks licence availability via MS Graph `subscribedSku` (E5 for ONPUL; F3 + Exchange Online Plan 2 + F5 Security Add-on for CLDUL).
4. Generates and validates a random password via `ms_graph_validate_password()`.
5. **Short-circuits silently** if `ASCENDER_CREATE_AZURE_AD == False` or `DEBUG == True`.
6. Creates the Entra ID account (disabled initially) with a minimum payload, then PATCHes additional attributes, sets the manager, assigns the licence, and finally adds the user to the relevant security group.
7. All MS Graph calls use a 1-second sleep between them. Failures at any step are logged to `AscenderActionLog` and emailed to `ADMIN_EMAILS`.

### `DepartmentUser.ascender_data`

Raw Ascender job data is cached as a JSON blob on `DepartmentUser.ascender_data`. Model methods (`get_division()`, `get_business_unit()`, `get_ascender_org_path()`, `get_employment_status()`, etc.) derive their values from this cached field rather than re-querying Ascender. The `account_type` field is also set from `ascender_data['emp_status']` during `save()`.

## Management commands

All commands live in `organisation/management/commands/`. Commands that are monitored in production wrap their work with `sentry_sdk.crons.monitor`.

| Command | Purpose |
|---------|---------|
| `check_ascender_accounts` | Main Ascender sync: bulk import all employees, update existing `DepartmentUser` records, provision new Entra ID accounts. Runs `ascender_user_import_all()`. |
| `azure_account_provision` | Manually provision a single Ascender employee by `--employee-id`. Accepts `--ignore-job-start-date`, `--manager-override-email`, and `--position-no` flags to bypass/override normal rules. |
| `ascender_query` | Debug/inspect tool: queries Ascender by `--employee-id` and pretty-prints the raw job records. |
| `check_azure_accounts` | Syncs Entra ID user data (licences, account status, Azure GUID, etc.) back onto `DepartmentUser` records. Creates new `DepartmentUser` objects for Entra ID accounts not yet in the database. Optionally deactivates dormant accounts (`ASCENDER_DEACTIVATE_EXPIRED`). |
| `check_onprem_accounts` | Reads on-premise AD data from an Azure Blob JSON file and links `ad_guid` / caches `ad_data` on matching `DepartmentUser` records. Does not create new records. |
| `department_users_sync_ad_data` | Pushes selected `DepartmentUser` field changes (title, phone, manager, department, etc.) back to Entra ID via Graph API PATCH calls. Accepts `--log-only` to preview changes without writing. |
| `check_cost_centre_managers` | Queries Ascender for cost-centre manager data and updates `CostCentre.manager` FK. |
| `check_department_users` | Sanity-checks `DepartmentUser` objects for records with neither an on-prem AD link nor an Entra ID link. |
| `check_m365_licence_count` | Checks M365 licence availability and emails `SERVICE_DESK_EMAIL` when available licences fall below `LICENCE_NOTIFY_THRESHOLD`. |
| `department_users_changes_report` | Emails an XLSX report of `AscenderActionLog` / `DepartmentUserLog` changes over a nominated number of days. |
| `department_users_dormant_account_notifications` | Identifies active, licensed accounts with no sign-in activity within `DORMANT_ACCOUNT_DAYS` and sends warning emails to line managers or cost-centre managers. Optionally deactivates accounts (`DORMANT_ACCOUNT_DEACTIVATE`). |
| `department_users_signins` | Queries Entra ID audit sign-in logs via Graph API and updates `DepartmentUser.last_signin`. |
| `department_users_upload_ascender_sftp` | Generates a CSV of user data changes that need to be written back to Ascender and uploads it via SFTP (using `paramiko`). Requires `ASCENDER_SFTP_*` settings. |
| `department_users_audit_emails` | Cross-checks `DepartmentUser` email values against Entra ID and deletes records whose email no longer exists in Azure. |
| `site_storage_upload` | Queries SharePoint site storage usage via Graph API and uploads a summary CSV to Azure Blob Storage. |

## Service desk admin customisations

### Two admin sites

The project runs **two separate Django admin sites** mounted at different URLs:

| Site | URL | Object | Purpose |
|------|-----|--------|---------|
| `django.contrib.admin.site` (default) | `/admin/` | `admin.site` | Full superuser access |
| `ServiceDeskAdminSite` | `/service-desk-admin/` | `service_desk_admin_site` | Scoped site for Service Desk staff |

`ServiceDeskAdminSite` is a bare `AdminSite` subclass defined in `organisation/admin.py` with custom `site_header`, `site_title`, and `index_title`. It registers only four models: `DepartmentUser`, `CostCentre`, `Location`, and `AscenderActionLog`. The site URL name is `"service_desk_admin"`, so all `reverse()` calls and `{% url %}` tags targeting this site use the `service_desk_admin:` namespace (e.g. `service_desk_admin:organisation_departmentuser_change`).

`/` redirects to `service_desk_admin:index` — the service desk site is the default landing page.

### `DepartmentUserAdmin`

This is the most customised admin class in the project.

**Two change forms accessed from the same object:**

The `change_form.html` template override adds a toolbar button that toggles between the two views:

- **Normal change form** (`/<pk>/change/`) — rendered with the standard Django `change_form.html`. Most fields are `readonly_fields`. Editable fields are limited to `telephone`, `mobile_phone`, `maiden_name`, `update_reference`, and `account_type`. The form is organised into four fieldsets with inline `<span class="errornote">` descriptions indicating the source of truth for each group of fields (Ascender, Entra ID, or OIM-editable).

- **Superuser-only change form** (`/<pk>/admin-change/`) — served by `admin_change_view()`, a custom method registered as an extra URL. It raises `PermissionDenied` for non-superusers. Uses `DepartmentUserAdminForm` which limits POST fields to `employee_id`, `position_no`, `maiden_name`, `cost_centre`, `ad_guid`, and `azure_guid`. Also renders the raw `ad_data`, `azure_ad_data`, and `ascender_data` JSON blobs as pretty-printed `<pre>` blocks via `ad_data_pprint`, `entra_id_data_pprint`, and `ascender_data_pprint` display methods. The context flag `superuser_only_form=True` switches the toolbar link in the template.

**No add permission:** `has_add_permission` returns `False`. `DepartmentUser` records are only created by the Ascender sync pipeline, never manually.

**Export buttons:** The `change_list_template` override (`admin/organisation/departmentuser/change_list.html`) adds two download links to the changelist toolbar, both pointing to the `DepartmentUserExport` view:
- "Download active Department Users" — active users excluding `ACCOUNT_TYPE_EXCLUDE` types
- "Download all Department Users" — all records (`?all=true`)

The export view returns an XLSX file via `xlsxwriter`, generated by `organisation/reports.py:department_user_export()`.

**Extra URLs registered via `get_urls()`:**

```
organisation/departmentuser/<pk>/admin-change/   → admin_change_view  (superuser-only edit)
organisation/departmentuser/export/              → DepartmentUserExport (XLSX download)
```

**Custom list display callables:** `division()`, `unit()`, and `m365_licence()` are thin wrappers around `DepartmentUser` model methods (`get_division()`, `get_business_unit()`, `get_licence()`). Ascender-derived fields displayed in the change form (`ascender_full_name`, `ascender_org_path`, `employment_status`, etc.) are also callables that delegate to model methods rather than model fields, because the underlying data lives in `ascender_data` JSON.

**`AssignedLicenceFilter`:** A `SimpleListFilter` that filters the changelist by `assigned_licences` (an `ArrayField`). Uses `assigned_licences__contains=[value]` for licence type filters, and `assigned_licences=[]` for the "No licence" option.

### `LocationAdmin` and `CostCentreAdmin`

`LocationAdmin` blocks both `has_add_permission` and `has_delete_permission` — locations are sourced from Ascender and must not be manually created or removed via the admin. `ascender_desc` is read-only.

`CostCentreAdmin` marks `manager` and `ascender_code` as read-only — these are set by the `check_cost_centre_managers` management command and Ascender sync respectively.

### `AscenderActionLogAdmin`

All add, change, and delete permissions return `False`. This model is a pure append-only audit log written by the Ascender sync code. The `ascender_data` JSON field is rendered as a `<pre>` block in the detail view.
