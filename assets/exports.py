from assets.models import Asset, Vulnerability, Severity
from itsystems.models import ITSystemRecord

from django.http import HttpResponse

from typing import Iterable
import csv

def export_asset_vulns(response: HttpResponse, assets: Iterable[Asset], severity_exclude_list: list[int] | None = [Severity.INFO]) -> HttpResponse:
    """
    Writes asset vulnerabilities to the http response as a csv.
    severity_exclude_list can be optionally included to exclude specific vuln severity levels, default to hiding info level.
    """
    writer = csv.writer(response)

    # Headers
    __write_vuln_header(writer, ["IT SYSTEM"])

    # Body
    for a in assets:
        for v in a.get_active_vulns(severity_exclude_list=severity_exclude_list):
            __write_vuln(writer,v, prefix_data=[a.associated_systems])

    return response

def export_vulns(response: HttpResponse, vulns: Iterable[Vulnerability]) -> HttpResponse:
    """
    Writes asset vulnerabilities to the http response as a csv.
    severity_exclude_list can be optionally included to exclude specific vuln severity levels, default to hiding info level.
    """
    writer = csv.writer(response)

    # Headers
    __write_vuln_header(writer)

    # Body
    for v in vulns:
        __write_vuln(writer,v)

    return response

def __write_vuln_header(writer, prefix_headers = []):
    prefix_headers.extend([
        "ASSET",
        "FINDING_ID",
        "STATE",
        "SEVERITY",
        "SEVERITY_MODIFICATION_TYPE",
        "FIRST_FOUND",
        "LAST_FOUND",
        "LAST_FIXED",
        "SOURCE",
        "RESURFACEED_DATE",
        "TIME_TAKEN_TO_FIX",
        "PLUGIN_ID",
        "PLUGIN_NAME",
        "PLUGIN_FAMILY",
        "VULN_AGE",
        "PLUGIN_OUTPUT",
        "PLUGIN_DESCRIPTION",
        "SOLUTION",
        "HAS_PATCH",
        "PATCH_PUBLICATION_DATE",
        "EXPLOITABILITY_EASE",
        "EXPLOITED_BY_MALWARE",
        "EXPLOITED_BY_NESSUS",
        "CVSS3_BASE_SCORE",
        "CVE",
        "VPR",
        "WORKAROUND"
    ])
    writer.writerow(prefix_headers)

def __write_vuln(writer, vuln, prefix_data = []):
    prefix_data.extend([
        vuln.asset_name,
        vuln.finding_id,
        vuln.get_state_display(),
        vuln.get_severity_display(),
        vuln.get_severity_modification_type_display(),
        vuln.first_found,
        vuln.last_found,
        vuln.last_fixed,
        vuln.source,
        vuln.resurfaced_date,
        vuln.time_taken_to_fix,
        vuln.plugin_id,
        vuln.plugin_name,
        vuln.plugin_family,
        vuln.vuln_age,
        vuln.plugin_output,
        vuln.plugin_description,
        vuln.solution,
        vuln.has_patch,
        vuln.patch_publication_date,
        vuln.exploitability_ease,
        vuln.exploited_by_malware,
        vuln.exploited_by_nessus,
        vuln.cvss3_base_score,
        vuln.cve,
        vuln.vpr,
        vuln.workaround
    ])
    writer.writerow(prefix_data)