from django.db import models

from organisation.models import DepartmentUser


class Division(models.Model):
    """
    Represents a division within DBCA.
    """

    class Meta:
        verbose_name = "Division"
        verbose_name_plural = "Divisions"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    def __str__(self):
        return self.name


class Status(models.Model):
    """
    Represents the status of a IT System.
    """

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Statuses"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return Status.objects.get_or_create(name="Production")[0].pk

    def __str__(self):
        return self.name


class Seasonality(models.Model):
    """
    Represents the seasonality of an IT System within DBCA.
    """

    class Meta:
        verbose_name = "Seasonality"
        verbose_name_plural = "Seasonalities"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return Seasonality.objects.get_or_create(name="Default")[0].pk

    def __str__(self):
        return self.name


class Availability(models.Model):
    """
    Represents the availability of an IT System within DBCA.
    """

    class Meta:
        verbose_name = "Availability"
        verbose_name_plural = "Availabilities"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return Availability.objects.get_or_create(name="Business hours")[0].pk

    def __str__(self):
        return self.name


class SystemType(models.Model):
    """
    Represents the system type of an IT System within DBCA.
    """

    class Meta:
        verbose_name = "System Type"
        verbose_name_plural = "System Types"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return SystemType.objects.get_or_create(name="Application")[0].pk

    def __str__(self):
        return self.name


class Sensitivity(models.Model):
    """
    Represents the sensitivity of an IT System within DBCA.
    """

    class Meta:
        verbose_name = "Sensitivity"
        verbose_name_plural = "Sensitivities"

    name = models.CharField(max_length=255, unique=True, verbose_name="Name")

    @classmethod
    def get_default_pk(cls):
        return Sensitivity.objects.get_or_create(name="Official")[0].pk

    def __str__(self):
        return self.name


class ITSystemRecord(models.Model):
    """Represents a named system providing a package of functionality to
    Department staff (normally vendor or bespoke software), which is supported
    by OIM and/or an external vendor.
    """

    class Meta:
        verbose_name = "IT System"
        verbose_name_plural = "IT Systems"

    # Standard IT System fields
    system_id = models.CharField(max_length=255, unique=True, verbose_name="System ID")
    name = models.CharField(max_length=255, verbose_name="Name")
    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        verbose_name="Status",
        default=Status.get_default_pk,
        related_name="assigned_status",
        help_text="Status",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Division",
        related_name="assigned_division",
        help_text="Division",
    )
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    link = models.URLField(max_length=2048, null=True, blank=True, verbose_name="Link", help_text="URL to web application")
    business_service_owner = models.ForeignKey(
        DepartmentUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Business Service Owner",
        related_name="systems_business_service_owner_of",
        help_text="IT system business service owner",
    )
    system_owner = models.ForeignKey(
        DepartmentUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="System Owner",
        related_name="systems_owner_of",
        help_text="IT system owner",
    )
    technology_custodian = models.ForeignKey(
        DepartmentUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Technology Custodian",
        related_name="systems_technology_custodian_of",
        help_text="IT system technology custodian",
    )
    information_custodian = models.ForeignKey(
        DepartmentUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Information Custodian",
        related_name="systems_information_custodian_of",
        help_text="IT system information custodian",
    )
    seasonality = models.ForeignKey(
        Seasonality,
        on_delete=models.PROTECT,
        default=Seasonality.get_default_pk,
        verbose_name="Seasonality",
        related_name="assigned_seasonality",
        help_text="Seasonality",
    )
    availability = models.ForeignKey(
        Availability,
        on_delete=models.PROTECT,
        default=Availability.get_default_pk,
        verbose_name="Availability",
        related_name="assigned_availability",
        help_text="Availability",
    )
    file_store_link = models.URLField(max_length=2048, null=True, blank=True, verbose_name="File Store Link", help_text="URL to file store")
    vital_records = models.BooleanField(default=False, null=True, blank=True, verbose_name="Vital Records")
    disposal_authority = models.CharField(max_length=255, null=True, blank=True, default=None, verbose_name="Disposal Authority")
    retention_and_disposal = models.CharField(max_length=255, null=True, blank=True, verbose_name="Retention and Disposal")
    ubcs = models.CharField(max_length=255, null=True, blank=True, verbose_name="UBCS")
    sensitivity = models.ForeignKey(
        Sensitivity,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=Sensitivity.get_default_pk,
        verbose_name="Sensitivity",
        related_name="assigned_sensitivity",
        help_text="Sensitivity",
    )
    system_type = models.ForeignKey(
        SystemType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=SystemType.get_default_pk,
        verbose_name="System Type",
        related_name="assigned_system_type",
        help_text="System Type",
    )

    # Meta-Data fields
    created_date = models.DateTimeField(auto_now_add=True, verbose_name="Created")
    created_by = models.EmailField(editable=False, verbose_name="Created By")
    modified_date = models.DateTimeField(auto_now=True, verbose_name="Modified")
    modified_by = models.EmailField(editable=False, verbose_name="Modified By")

    @property
    def system_id_name(self):
        """
        A calculated field combining the ID of the record and the name.
        """
        return self.system_id + " - " + self.name
    
    @property
    def short_description(self):
        """
        A calculated field producing a shortened version of the description.
        This is used primarily in the admin view.
        """
        limit = 100
        if self.description and len(self.description)> limit:
            text = self.description[:97] + "..."
        else:
            text = self.description
        return text


    def compare(self, obj):
        """
        Compares a record instance with itself, returning a list of differences between the two.
        These differences are returned in the form of dictionaries containing the field, the old (current) value, and the new (external) value.
        """
        excluded_fields = ["created_date", "modified_date", "created_by", "modified_by", "id", "_state", "system_id"]
        changes = []
        if obj:
            # Compares self to other record object, returns differences
            self_fields = self.__dict__
            obj_fields = obj.__dict__

            for field_name, self_value in self_fields.items():
                if (field_name not in excluded_fields) and (field_name in obj_fields):
                    #  obj_fileds' 'Or None' accounts for empty string values, self fields' 'Or None' allows for Boolean 'False' equivalency
                    if (self_value or None) != (obj_fields[field_name] or None):
                        changes.append(
                            {
                                "field": self.__strip_field__(field_name),
                                "verbose_field": self.__display_field__(field_name),
                                "old": self.__display_val__(field_name, self_value),
                                "new": obj.__display_val__(field_name, obj_fields[field_name]),
                            }
                        )
        else:
            # Returns all fields
            self_fields = self.__dict__
            for field_name, self_value in self_fields.items():
                if field_name not in excluded_fields:
                    changes.append(
                        {
                            "field": self.__strip_field__(field_name),
                            "verbose_field": self.__display_field__(field_name),
                            "old": None,
                            "new": self.__display_val__(field_name, self_value),
                        }
                    )

        return changes

    def save(self, *args, **kwargs):
        """
        Overrides the default save method.
        This override converts empty string values to null values.
        """
        if self.description == "":
            self.description = None
        if self.link == "":
            self.link = None
        if self.file_store_link == "":
            self.file_store_link = None
        if self.disposal_authority == "":
            self.disposal_authority = None
        if self.retention_and_disposal == "":
            self.retention_and_disposal = None
        if self.ubcs == "":
            self.ubcs = None

        super(ITSystemRecord, self).save(*args, **kwargs)

    def set_from_dict(self, dict, plain_text=True, force=False):
        """
        Sets field values from inputted dictionary object.
        If plain_text is false, data with fk fields are set using PK values rather than human readable display values.
        """
        force_failures = []

        # Sets Non-FK fields
        self.system_id = dict.get("system_id")
        self.name = dict.get("name")
        self.description = dict.get("description")
        self.link = dict.get("link")
        self.file_store_link = dict.get("file_store_link")
        self.disposal_authority = dict.get("disposal_authority")
        self.retention_and_disposal = dict.get("retention_and_disposal")
        self.ubcs = dict.get("ubcs")
        if plain_text:
            # Sets FK fields using their human readable display values
            self.division = self.__get_choice_fk(dict.get("division"), Division, force, force_failures)
            self.status = self.__get_choice_fk(dict.get("status"), Status, force, force_failures)
            self.seasonality = self.__get_choice_fk(dict.get("seasonality"), Seasonality, force, force_failures)
            self.availability = self.__get_choice_fk(dict.get("availability"), Availability, force, force_failures)
            self.system_owner = self.__get_user_fk(dict.get("system_owner"), "system_owner", force, force_failures)
            self.technology_custodian = self.__get_user_fk(dict.get("technology_custodian"), "technology_custodian", force, force_failures)
            self.information_custodian = self.__get_user_fk(
                dict.get("information_custodian"), "information_custodian", force, force_failures
            )
            self.business_service_owner = self.__get_user_fk(
                dict.get("business_service_owner"), "business_service_owner", force, force_failures
            )
            self.sensitivity = self.__get_choice_fk(dict.get("sensitivity"), Sensitivity, force, force_failures)
            self.system_type = self.__get_choice_fk(dict.get("system_type"), SystemType, force, force_failures)
            vital_records = dict.get("vital_records")
            if vital_records and not str(vital_records)=="":
                self.vital_records = str(vital_records).strip().lower() == "true"
            else:
                self.vital_records = None
        else:
            # Sets FK fields by using their direct value
            self.division = Division.objects.get(pk=dict.get("division_id"))
            self.status = Status.objects.get(pk=dict.get("status_id"))
            self.seasonality = Seasonality.objects.get(pk=dict.get("seasonality_id"))
            self.availability = Availability.objects.get(pk=dict.get("availability_id"))
            self.system_owner = DepartmentUser.objects.get(pk=dict.get("system_owner_id"))
            self.technology_custodian = DepartmentUser.objects.get(pk=dict.get("technology_custodian_id"))
            self.information_custodian = DepartmentUser.objects.get(pk=dict.get("information_custodian_id"))
            self.business_service_owner = DepartmentUser.objects.get(pk=dict.get("business_service_owner_id"))
            self.sensitivity = Sensitivity.objects.get(pk=dict.get("sensitivity_id"))
            self.system_type = SystemType.objects.get(pk=dict.get("system_type_id"))
            self.vital_records = dict.get("vital_records")

        return force_failures

    def to_dict(self):
        """
        Returns a human readable dictionary representation of the record.
        FK fields are displayed using their primary display value rather than their ID.
        """
        return {
            "system_id": self.system_id,
            "name": self.name,
            "status": self.status.name if self.status else None,
            "division": self.division.name if self.division else None,
            "description": self.description,
            "link": self.link,
            "business_service_owner": self.business_service_owner.email if self.business_service_owner else None,
            "system_owner": self.system_owner.email if self.system_owner else None,
            "technology_custodian": self.technology_custodian.email if self.technology_custodian else None,
            "information_custodian": self.information_custodian.email if self.information_custodian else None,
            "seasonality": self.seasonality.name if self.seasonality else None,
            "availability": self.availability.name if self.availability else None,
            "file_store_link": self.file_store_link,
            "vital_records": self.vital_records,
            "disposal_authority": self.disposal_authority,
            "retention_and_disposal": self.retention_and_disposal,
            "ubcs": self.ubcs,
            "sensitivity": self.sensitivity.name if self.sensitivity else None,
            "system_type": self.system_type.name if self.system_type else None,
        }

    def to_array(self):
        """
        Creates a human readable array representation of the record field values.
        FK fields are displayed using their primary display value rather than their ID
        """
        return self.to_dict().values()

    def __str__(self):
        """
        Overrides the default __str__ method.
        """
        return self.system_id_name

    def __display_val__(self, field, value):
        """
        Returns the natural display value for a field value.
        """
        return_val = value
        if field.endswith("_id"):
            return_val = str(getattr(self, field[:-3], None))

        return return_val

    def __strip_field__(self, field):
        """
        Strips any _id suffix from a field name.
        """
        field_name = field
        if field.endswith("_id"):
            field_name = field[:-3]
        return field_name

    def __display_field__(self, field):
        """
        Returns the natural display string for a field value.
        """
        return self._meta.get_field(self.__strip_field__(field)).verbose_name

    def __get_choice_fk(self, text, ChoiceClass, force=False, force_failures=None):
        """
        Retrieves a division id from the inputted text value.
        This is used for generic choice FK fields, where 'name' is the identifying field.
        """
        fk = None

        try:
            if text:
                fk = ChoiceClass.objects.get(name=text)
        except ChoiceClass.DoesNotExist:
            message = str(ChoiceClass._meta.verbose_name) + ": Can't find option '" + text + "'."
            if force and (force_failures is not None):
                force_failures.append(message)
            else:
                raise ChoiceClass.DoesNotExist(message)
        return fk

    def __get_user_fk(self, email, field, force=False, force_failures=None):
        """
        Retrieves a user id from an inputted email or display name.
        This is exclusively used for DepartmentUser FK fields.
        """
        user = None
        suffix = "@dbca.wa.gov.au"
        email_query = None

        try:
            if email:
                if email.endswith(suffix):
                    # Retrieves the email directly
                    email_query = email
                elif " " in email:
                    # Attempts to recreate the email based on the user's full name.
                    names = email.split(" ")
                    email_query = names[0].lower() + "." + "".join(names[1:]).lower() + suffix
            if email_query:
                user = DepartmentUser.objects.get(email=email_query)
        except DepartmentUser.DoesNotExist:
            message = field + ": Can't find user '" + email + "'."
            if email and force and (force_failures is not None):
                force_failures.append(message)
            elif email and not force:
                raise DepartmentUser.DoesNotExist(message)
            user = None
        return user
