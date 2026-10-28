from assets.models import Asset, Vulnerability
from assets.enum_library import Severity

from django.http import HttpResponse

from typing import Iterable
import csv


def export_asset_vulns(
    response: HttpResponse, assets: Iterable[Asset], severity_exclude_list: list[int] | None = [], simple: bool = False
) -> HttpResponse:
    """
    Writes asset vulnerabilities to the http response as a csv.
    severity_exclude_list can be optionally included to exclude specific vuln severity levels, but always hides info level vulns.
    Set simple as true to return a simplified version for tech custodians.
    """
    writer = csv.writer(response)

    # Headers
    it_system_header = "IT System" if simple else "IT_SYSTEMS"
    __write_vuln_header(writer=writer, prefix_headers=[it_system_header], simple=simple)

    # Body
    for a in assets:
        for v in a.get_active_vulns(severity_exclude_list=severity_exclude_list):
            __write_vuln(writer=writer, vuln=v, prefix_data=[a.associated_systems], simple=simple)

    return response


def export_vulns(response: HttpResponse, vulns: Iterable[Vulnerability], simple: bool = False) -> HttpResponse:
    """
    Writes vulnerabilities to the http response as a csv.
    Set simple as true to return a simplified version for tech custodians.
    """
    writer = csv.writer(response)

    # Headers
    __write_vuln_header(writer=writer, simple=simple)

    # Body
    for v in vulns:
        __write_vuln(writer=writer, vuln=v, simple=simple)

    return response


def __write_vuln_header(writer, prefix_headers=[], simple=False) -> None:
    """
    Writes headers to a csv, allowing for additional headers to be prepended using prefix_headers
    Allows for an alternative simple version. If simple headers are used, simple vulns must also be used
    """
    if simple:
        # Simplified version for tech custodians
        headers = prefix_headers + [
            "Asset",  # asset_name
            "Severity",  # severity
            "Type",  # plugin_name
            "Problem",  # plugin_output
            "Solution",  # solution
            "Full Problem",  # plugin_description
            "Technical Info",  # output
            "OIM Notes",  # Blank space for OIM to add any further clarification
        ]
    else:
        # Technical version
        headers = prefix_headers + [
            "ASSET",
            "FINDING_ID",
            "STATE",
            "SEVERITY",
            "SEVERITY_MODIFICATION_TYPE",
            "OUTPUT",
            "FIRST_FOUND",
            "LAST_FOUND",
            "LAST_FIXED",
            "SOURCE",
            "RESURFACED_DATE",
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
            "WORKAROUND",
        ]
    writer.writerow(headers)


def __write_vuln(writer, vuln, prefix_data=[], simple=False) -> None:
    """
    Writes vulnerabilities to a csv, allowing for additional data to be prepended using prefix_data.
    Allows for an alternative simple version. If simple vulns are used, simple headers must also have been used.
    """
    if simple:
        # Simplified version for tech custodians
        vulns = prefix_data + [
            vuln.asset_name,
            vuln.get_severity_display(),
            vuln.plugin_name,
            vuln.plugin_output,
            vuln.solution,
            vuln.plugin_description,
            vuln.output,
            "",  # Blank section for notes
        ]
    else:
        # Technical version
        vulns = prefix_data + [
            vuln.asset_name,
            vuln.finding_id,
            vuln.get_state_display(),
            vuln.get_severity_display(),
            vuln.get_severity_modification_type_display(),
            vuln.output,
            vuln.first_found.isoformat() if vuln.first_found is not None else None,
            vuln.last_found.isoformat() if vuln.last_found is not None else None,
            vuln.last_fixed.isoformat() if vuln.last_fixed is not None else None,
            vuln.source,
            vuln.resurfaced_date.isoformat() if vuln.resurfaced_date is not None else None,
            vuln.time_taken_to_fix,
            vuln.plugin_id,
            vuln.plugin_name,
            vuln.plugin_family,
            vuln.vuln_age,
            vuln.plugin_output,
            vuln.plugin_description,
            vuln.solution,
            vuln.has_patch,
            vuln.patch_publication_date.isoformat() if vuln.patch_publication_date is not None else None,
            vuln.exploitability_ease,
            vuln.exploited_by_malware,
            vuln.exploited_by_nessus,
            vuln.cvss3_base_score,
            vuln.cve,
            vuln.workaround,
        ]
    writer.writerow(vulns)
