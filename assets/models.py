import re

from django.db import models
from django.core.validators import RegexValidator
from django.utils.timezone import now
from datetime import datetime


from organisation.models import DepartmentUser
from itsystems.models import ITSystemRecord


class AssetTagCategory(models.Model):
    """
    Represents an arbitrary category for 1 or more asset tags
    """

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return AssetTagCategory.objects.get_or_create(name="Misc.")[0].pk

    def number_of_values(self) -> int:
        return len(self.tag_values.all())

    def __str__(self):
        return self.name


class AssetTag(models.Model):
    """
    Represents an asset tag value under a given tag category
    """

    class Meta:
        verbose_name = "Tag Value"
        verbose_name_plural = "Tag Values"
        # Forces tags to be unique within their own category
        constraints = [models.UniqueConstraint(fields=["name", "category"], name="unique_tag")]

    name = models.CharField(max_length=255, verbose_name="Name")
    category = models.ForeignKey(
        AssetTagCategory,
        on_delete=models.CASCADE,
        default=AssetTagCategory.get_default_pk,
        related_name="tag_values",
        verbose_name="Tag Category",
        help_text="Tag Category",
    )

    def number_of_tagged_assets(self) -> int:
        return len(self.tagged_assets.all())

    def __str__(self):
        return f"{self.category.name}: {self.name}"


class Asset(models.Model):
    """
    Represents a physical or digital asset owned by the organisation.
    IE; a server, a user device, a web app, etc
    """

    class Meta:
        verbose_name = "Asset"
        verbose_name_plural = "Assets"

    tenable_id = models.CharField(max_length=255, unique=True, verbose_name="tenable_id", editable=False)
    name = models.CharField(max_length=255, unique=False, null=True, blank=True, verbose_name="Name")
    aliases = models.JSONField(verbose_name="Alternate names", default=list, null=True, blank=True, editable=False)
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    contacts = models.ManyToManyField(
        DepartmentUser,
        blank=True,
        verbose_name="Contacts",
        related_name="asset_contact_of",
        help_text="The department user(s) to contact for a technical request",
    )
    systems = models.ManyToManyField(
        ITSystemRecord,
        blank=True,
        verbose_name="Associated IT Systems",
        related_name="related_assets",
        help_text="IT Systems that use this asset",
    )
    os = models.CharField(max_length=255, verbose_name="OS", null=True, blank=True)
    os_version = models.CharField(
        max_length=255,
        verbose_name="OS Version",
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^(?:$|(?:(\d+)\.)?(?:(\d+)\.)?(\d+))$",
                message="Invalid OS Version formatting. Please use format Int[.Int[.Int]], ie; '24.04', '12.6.03', etc).",
                code="invalid_os_version",
            )
        ],
    )
    os_list = models.JSONField(default=list, null=True, blank=True)
    ipv4_list = models.JSONField(default=list, null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True, verbose_name="First Seen")
    last_seen = models.DateTimeField(
        verbose_name="Last Seen",
        null=True,
        blank=True,
    )
    last_modified = models.DateTimeField(auto_now=True, verbose_name="Last Modified")
    defender_data = models.JSONField(
        default=dict,
        null=True,
        blank=True,
    )
    tenable_data = models.JSONField(
        default=dict,
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(AssetTag, blank=True, verbose_name="Tags", related_name="tagged_assets", help_text="Tenable Tags")

    # Cached during every sync for better load performance and to enable admin ordering
    # the use-case doesn't include manually adding or deleting vulns, so this should be fine
    total_vulns = models.IntegerField(null=True, blank=True, verbose_name="Total Vulns", default=0)
    total_active_vulns = models.IntegerField(null=True, blank=True, verbose_name="Total Active Vulns", default=0)
    total_critical_vulns = models.IntegerField(null=True, blank=True, verbose_name="Total Critical Vulns", default=0)

    @property
    def asset_contacts(self) -> str:
        """Provides a string representation of all contacts"""
        return ", ".join([str(c) for c in self.contacts.all()])

    @property
    def associated_systems(self) -> str:
        """Provides a string representation of all associated IT Systems"""
        return ", ".join([str(s) for s in self.systems.all()])

    @property
    def operating_system(self) -> str:
        """Provides a combined 'OS - Version' string for display"""
        displayString = self.os or ""
        if self.os_version:
            displayString += f" - {self.os_version}"
        return displayString

    @property
    def operating_systems(self) -> str:
        """Provides a string representation of all operating systems"""
        return ", ".join(self.os_list)

    @property
    def ipv4s(self) -> str:
        """Returns a string representation of all ipv4 values"""
        return ", ".join(self.ipv4_list)

    @property
    def custodian(self) -> str:
        """
        Returns a string representation of the custodian tag.
        """
        return self.__get_tag_category_string("Custodian")

    @property
    def asset_type(self) -> str:
        """
        Returns a string representation of the device type tag.
        """
        return self.__get_tag_category_string("Devices")

    @property
    def display_tags(self) -> str:
        """Returns a string representation of each tag"""
        return ", ".join([f"{t.category.name}: {t.name}" for t in self.tags.all()])

    def save(self, *args, **kwargs):
        """
        Overrides the default save method.
        This override converts empty string values to null values.
        """
        if self.description == "":
            self.description = None

        if self.os == "":
            self.os = None

        super(Asset, self).save(*args, **kwargs)

    def update_from_tenable_data(self, tenable_data: dict | None = None, vuln_data: list | None = None):
        """
        Updates internal fields using data found in tenable_data.
        If passed tenable_data as a parameter, the model's internal tenable_data is overridden first.
        """
        # Override internal tenable_data if passed in.
        if tenable_data:
            self.tenable_data = tenable_data
            self.last_seen = now()

        # Update internal fields
        if self.tenable_data:
            t = self.tenable_data
            # Set ID
            self.tenable_id = t.get("id")
            # Retrieve Aliases & IPv4s
            aliases = []
            if t.get("network"):
                self.ipv4_list = t["network"].get("ipv4s")
                if t["network"].get("hostnames"):
                    aliases.append(t["network"]["hostnames"][0].split(".")[0])
                    aliases.extend(t["network"]["hostnames"])
                if t["network"].get("fqdns"):
                    # If it's found through a web app scan, use the FQDN as the primary alias, otherwise treat as normal
                    if "webapp" in t["types"]:
                        aliases.extend(t["network"]["fqdns"])
                    else:
                        aliases.append(t["network"]["fqdns"][0].split(".")[0])
                        aliases.extend(t["network"]["fqdns"])
            if t.get("agent_names"):
                aliases.extend(t["agent_names"])
            # Set name & aliases
            self.aliases = []  # clear aliases
            self.name = None
            if aliases:
                self.name = aliases[0]
                self.aliases = list(set(aliases))  # set aliases without duplicates
            # Set OS & OS Version
            self.os, self.os_version = (
                self.__split_tenable_os_and_version(t.get("operating_systems")[0]) if t.get("operating_systems") else (None, None)
            )
            self.os_list = t.get("operating_systems")

            # Replace tags
            self.tags.clear()
            if self.tenable_data.get("tags"):
                # Add new tags
                for tag in self.tenable_data.get("tags"):
                    self.add_tag(tag=tag["value"], category=tag["key"])

        # Updates vulnerability data
        self.total_vulns = 0
        self.total_critical_vulns = 0
        if vuln_data:
            for vuln in vuln_data:
                self.add_or_update_vuln(vuln)

            # Retrieves active vulnerabilities for stats
            total_vulns = self.vulns.all()
            self.total_vulns = len(total_vulns)
            active_vulns = (
                total_vulns.exclude(state=State.FIXED)
                .exclude(severity_modification_type=SeverityMT.ACCEPTED)
                .exclude(severity=Severity.INFO)
            )
            self.total_active_vulns = len(active_vulns)
            self.total_critical_vulns = len(active_vulns.filter(severity=Severity.CRITICAL))

        self.save()

    def add_tag(self, tag: str, category: str):
        """
        Adds a tag to an asset. If the tag and/or category doesn't exist, they're created.
        """
        if not self.has_tag(tag, category):
            found_category, _ = AssetTagCategory.objects.get_or_create(name=category)
            found_tag, _ = AssetTag.objects.get_or_create(
                name=tag,
                category=found_category,
            )
            self.tags.add(found_tag)

    def add_or_update_vuln(self, vuln: dict):
        """
        Creates or updates a vulnerability linked to this asset via a tenable api vuln dict.
        Note, this method does not automatically update any total vuln stats.
        """
        if vuln["asset"].get("uuid") == self.tenable_id:
            new_vuln, created = Vulnerability.objects.get_or_create(
                finding_id=vuln["finding_id"], defaults={"asset": self, "raw_vuln_data": vuln}
            )
            if created:
                new_vuln.update_from_raw_vuln_data()
            else:
                new_vuln.update_from_raw_vuln_data(raw_vuln_data=vuln)

    def has_vuln(self, finding_id: str) -> bool:
        """
        Checks if an asset has a specific vulnerability
        """
        return self.get_vulns().filter(finding_id=finding_id).exists()

    def get_vulns(
        self, severity: int | None = None, severity_exclude_list: list[int] | None = None
    ) -> models.query.QuerySet[Vulnerability]:  # noqa
        """
        Returns a queryset of all vulnerabilities for this asset.
        Severity can be optionally specified to return vulns prefiltered for that specific severity.
        Severity exclude list can be specified to exclude different severity levels from the search
        """
        # Filter for active vulns
        vulns = self.vulns.all()

        # filter for specified severity
        if severity is not None:
            vulns = vulns.filter(severity=severity)

        # Filter out excluded severities
        if severity_exclude_list is not None:
            vulns = vulns.exclude(severity__in=severity_exclude_list)

        return vulns

    def get_active_vulns(
        self, severity: int | None = None, severity_exclude_list: list[int] | None = None
    ) -> models.query.QuerySet[Vulnerability]:  # noqa
        """
        Returns a queryset of all vulnerabilities for this asset that don't have a 'fixed' state or 'accepted' severity mod type.
        Severity can be optionally specified to return vulns prefiltered for that specific severity.
        Severity exclude list can be specified to exclude different severity levels from the search
        """
        # Filter for active vulns
        vulns = (
            self.vulns.exclude(state=State.FIXED).exclude(severity_modification_type=SeverityMT.ACCEPTED).exclude(severity=Severity.INFO)
        )

        # filter for specified severity
        if severity is not None:
            vulns = vulns.filter(severity=severity)

        # Filter out excluded severities
        if severity_exclude_list is not None:
            vulns = vulns.exclude(severity__in=severity_exclude_list)

        return vulns

    def remove_vuln(self, finding_id: str):
        """
        Deletes an associated vulnerability
        """
        vuln = self.vulns.filter(finding_id=finding_id)
        if vuln.exists():
            vuln[0].delete()

    def remove_tag(self, tag: str, category: str):
        """
        Removes a specific tag from an asset.
        """
        if self.has_tag(tag=tag, category=category):
            self.tags.remove(self.tags.get(name=tag, category__name=category))

    def has_tag(self, tag: str, category: str) -> bool:
        """
        Checks if an asset has a tag.
        """
        return self.tags.filter(name=tag, category__name=category).exists()

    def __split_tenable_os_and_version(self, os_string: str) -> tuple[str | None, str | None]:
        """
        Converts a tenable OS string into an OS & version number.
        Returns a tuple of (OS <string>, version number <string>)
        """
        os, version = (None, None)
        if os_string:
            version_regex = r"\d+\.\d+(?:\.\d+)?"  # Looks for Major.Minor or Major.Minor.Patch
            if "Debian" in os_string:
                version_regex = r"\d{1,2}"  # Looks only for Major
            match = re.search(version_regex, os_string)
            if match:
                os = re.split(version_regex, os_string)[0].strip()
                version = match.group().strip()
            elif "Build" in os_string:
                os = os_string.split("Build")[0].strip()
            elif os_string is not None or "":
                os = os_string
        return os, version

    def __get_tag_category_string(self, category: str) -> str:
        """
        Gets a display string for all attached tags within a category
        """
        tags = [tag.name for tag in self.tags.filter(category__name__iexact=category)]
        return ", ".join(tags)

    def __str__(self):
        """
        Overrides the default __str__ method.
        """
        return str(self.name)


class Severity:
    """Enum class for the Vulnerability field "severity" """

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SeverityMT:
    """Enum class for the Vulnerability field "severity_modification_type" """

    NONE = "N"
    RECASTED = "R"
    ACCEPTED = "A"


class State:
    """Enum class for the Vulnerability field "state" """

    OPEN = "O"
    REOPENED = "R"
    FIXED = "F"


class Vulnerability(models.Model):
    """
    Represents a vulnerability with a given asset.
    """

    class Meta:
        verbose_name = "Vulnerability"
        verbose_name_plural = "Vulnerabilities"

    # Choices for fields
    SEVERITY_CHOICES = {
        Severity.INFO: "Info",
        Severity.LOW: "Low",
        Severity.MEDIUM: "Medium",
        Severity.HIGH: "High",
        Severity.CRITICAL: "Critical",
    }
    SEVERITY_MOD_TYPE_CHOICES = {SeverityMT.NONE: "None", SeverityMT.RECASTED: "Recasted", SeverityMT.ACCEPTED: "Accepted"}
    STATE_CHOICES = {State.OPEN: "Open", State.REOPENED: "Reopened", State.FIXED: "Fixed"}

    asset = models.ForeignKey(Asset, related_name="vulns", verbose_name="Asset", on_delete=models.CASCADE)
    output = models.TextField(null=True, blank=True, verbose_name="Output")
    plugin = models.JSONField(verbose_name="Plugin", default=dict)
    port = models.JSONField(verbose_name="Port", default=dict)
    recast_reason = models.TextField(null=True, blank=True, verbose_name="Recast Reason")
    recast_rule_uuid = models.CharField(max_length=255, null=True, blank=True, verbose_name="Recast Rule UUID")
    scan = models.JSONField(verbose_name="Scan", default=dict)
    severity = models.PositiveSmallIntegerField(choices=SEVERITY_CHOICES, verbose_name="Severity", null=True, blank=True)
    severity_default = models.PositiveSmallIntegerField(choices=SEVERITY_CHOICES, verbose_name="Default Severity", null=True, blank=True)
    severity_modification_type = models.CharField(
        max_length=1, choices=SEVERITY_MOD_TYPE_CHOICES, null=True, blank=True, verbose_name="Severity Modification Type"
    )
    first_found = models.DateTimeField(null=True, blank=True, verbose_name="First Found")
    last_fixed = models.DateTimeField(null=True, blank=True, verbose_name="Last Fixed")
    last_found = models.DateTimeField(null=True, blank=True, verbose_name="Last Found")
    indexed = models.DateTimeField(null=True, blank=True, verbose_name="Indexed")
    state = models.CharField(max_length=1, choices=STATE_CHOICES, verbose_name="State", null=True, blank=True)
    source = models.CharField(max_length=255, null=True, blank=True, verbose_name="Source")
    finding_id = models.CharField(max_length=255, unique=True, verbose_name="Finding Id")
    resurfaced_date = models.DateField(null=True, blank=True, verbose_name="Resurfaced Date")
    time_taken_to_fix = models.IntegerField(null=True, blank=True, verbose_name="Time taken to fix (seconds)")
    software_vulns = models.JSONField(verbose_name="Software Vulns", default=list)
    raw_vuln_data = models.JSONField(verbose_name="Raw Vuln Data", default=dict)

    def update_from_raw_vuln_data(self, raw_vuln_data: dict | None = None):
        """
        Updates all fields using raw tenable vulnerability data.
        If not passed in, the vulnerability's internal raw_vuln_data field is used instead.
        """
        if raw_vuln_data is not None:
            self.raw_vuln_data = raw_vuln_data

        if self.raw_vuln_data:
            data = self.raw_vuln_data
            self.output = data.get("output")
            self.plugin = data.get("plugin", {})
            self.port = data.get("port", {})
            self.recast_reason = data.get("recast_reason")
            self.recast_rule_uuid = data.get("recast_rule_uuid")
            self.scan = data.get("scan", {})
            self.severity = data.get("severity_id")
            self.severity_default = data.get("severity_default_id")
            self.severity_modification_type = (
                data["severity_modification_type"][0].upper() if data.get("severity_modification_type") else None
            )
            self.first_found = self.__convert_iso(data.get("first_found"))
            self.last_fixed = self.__convert_iso(data.get("last_fixed"))
            self.last_found = self.__convert_iso(data.get("last_found"))
            self.indexed = data.get("indexed")
            self.state = data["state"][0].upper() if data.get("state") else None
            self.source = data.get("source")
            self.finding_id = data.get("finding_id")
            self.resurfaced_date = self.__convert_iso(data.get("resurfaced_date"))
            self.time_taken_to_fix = data.get("time_taken_to_fix")
            self.software_vulns = data.get("software_vulns", [])

        self.save()

    def __convert_iso(self, iso_date: str | None) -> datetime | None:
        """
        Converts a given iso date string to a datetime, returns none if iso string is empty or None
        """
        return datetime.fromisoformat(iso_date) if iso_date else None

    @property
    def asset_name(self):
        return self.asset.name

    @property
    def cve(self):
        if self.plugin and self.plugin.get("cve"):
            return ", ".join(self.plugin["cve"])

    @property
    def cvss3_base_score(self):
        return self.plugin.get("cvss3_base_score")

    @property
    def exploitability_ease(self):
        return self.plugin.get("exploitability_ease")

    @property
    def exploited_by_malware(self):
        return self.plugin.get("exploited_by_malware")

    @property
    def exploited_by_nessus(self):
        return self.plugin.get("exploited_by_nessus")

    @property
    def ipv4_addresses(self):
        return self.asset.ipv4s

    @property
    def operating_systems(self):
        return self.asset.operating_systems

    @property
    def has_patch(self):
        return self.plugin.get("has_patch")

    @property
    def patch_publication_date(self):
        if self.plugin.get("patch_publication_date"):
            return self.__convert_iso(self.plugin["patch_publication_date"]).date()

    @property
    def plugin_description(self):
        return self.plugin.get("description")

    @property
    def plugin_family(self):
        return self.plugin.get("family")

    @property
    def plugin_id(self):
        return self.plugin.get("id")

    @property
    def plugin_name(self):
        return self.plugin.get("name")

    @property
    def plugin_output(self):
        return self.plugin.get("synopsis")

    @property
    def solution(self):
        return self.plugin.get("solution")

    @property
    def vpr(self):
        return str(self.plugin.get("vpr"))

    @property
    def vuln_age(self):
        if self.plugin.get("vpr") and self.plugin["vpr"].get("drivers"):
            age_dict = self.plugin["vpr"]["drivers"].get("age_of_vuln")
            if age_dict["lower_bound"] > 730:
                age_str = "More than 730 days"
            else:
                age_str = f"{age_dict['lower_bound']}-{age_dict['upper_bound']} days"
            return age_str

    @property
    def workaround(self):
        return self.plugin.get("workaround")

    def __str__(self):
        return self.plugin_name
