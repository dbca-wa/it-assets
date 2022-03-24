# Security Policy

The Department of Biodiversity, Conservation and Attractions (DBCA) takes the
security of our software products and services seriously, which includes all
source code repositories managed through our GitHub organisation
[dbca-wa](https://github.com/dbca-wa).

This repository takes guidance relating to Secure Software Development from the
[WA Government Cyber Security
Policy](https://www.wa.gov.au/system/files/2022-01/WA%20Government%20Cyber%20Security%20Policy.pdf).

If you believe that you have found a security vulnerability in any DBCA-managed
repository, please report it to us as described below.

## Reporting a vulnerability or security issue

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report any security vulnerabilities to
[OIMSecurity@dbca.wa.gov.au](mailto:OIMSecurity@dbca.wa.gov.au).

You should receive a response within 1-2 business days. If for some reason you
do not, please follow up via email to ensure we received your original message.

Please include the requested information listed below (as much as you can provide)
to help us better understand the nature and scope of the possible issue:

  * Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
  * Full paths of source file(s) related to the manifestation of the issue
  * The location of the affected source code (tag/branch/commit or direct URL)
  * Any special configuration required to reproduce the issue
  * Step-by-step instructions to reproduce the issue
  * Proof-of-concept or exploit code (if possible)
  * Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly. Please note that
we prefer all communications to be in English.

## Updates related to security issues

Updates and patches to this project which are related to identified security
issues will be undertaken with reference to the "Patch applications" mitigation
strategy as part of the [Essential Eight Maturity
Model](https://www.cyber.gov.au/acsc/view-all-content/publications/essential-eight-maturity-model).
In practice this means that patches, updates or mitigations for security
vulnerabilites will be applied on an ongoing basis during the normal development
cycle. In general we aim to apply mitigations within two weeks of release, or
within 48 hours if an exploit exists.

## Automated monitoring of security issues

This repository makes use of automated scanning to check for known security
issues within software dependencies and built outputs. Where security issues
are identified within project dependencies and/or outputs, updates to mitigate
those issues will be incorporated into our normal development cycle and
mitigated as soon as practical.
