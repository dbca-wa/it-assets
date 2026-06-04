import csv
import io
import reversion
from .models import ITSystemRecord
from .models import DepartmentUser


def export_csv(response):
    """
    Exports the IT Systems Register to a csv, writing it into a HttpResponse object passed to it.
    """
    writer = csv.writer(response)

    # Writes headers into the CSV
    headers = [field.name for field in __get_model_fields()]
    writer.writerow(headers)

    # Writes all record values into the csv
    records = ITSystemRecord.objects.all()
    for record in records:
        record_vals = record.to_array()
        writer.writerow(record_vals)


def import_csv(request):
    """
    Updates the IT System Register database from a csv contained within an Http Post Request.
    This function returns a dictionary containing the validation results and 3 lists respectively containing details of records created, records updated, and records that failed to process.
    """
    csv_file = request.FILES["csv_file"]
    force = request.POST["force"] == "True"
    update_list = []
    create_list = []
    failed_list = []

    # Checks if CSV file is valid
    validate_results = __validate_csv(csv_file)
    if validate_results["valid"]:
        # Convert raw text to dictionary
        raw_text = validate_results["raw_text"]
        record_list = list(csv.DictReader(io.StringIO(raw_text)))

        # Import each record by updating an existing record or creating a new one
        for record in record_list:
            force_failures = []
            # Search for existing record in database
            try:
                found_record = ITSystemRecord.objects.get(system_id=record["system_id"])
            except ITSystemRecord.DoesNotExist:
                found_record = None

            try:
                # Populate new record with data
                new_record = ITSystemRecord()
                force_failures = new_record.set_from_dict(dict=record, plain_text=True, force=force)

                if found_record:
                    # Finds differences between the two
                    changes = found_record.compare(new_record)
                    if len(changes) > 0:
                        # Updates existing record and creates an entry in the version history
                        with reversion.create_revision():
                            # Update Record
                            force_failures = found_record.set_from_dict(dict=record, plain_text=True, force=force)
                            found_record.modified_by = request.user.email
                            found_record.save()

                            # Create comment for version history
                            change_log = "Changed via CSV: "
                            for change in changes:
                                change_log += change["verbose_field"] + ", "
                            comment = change_log[:-2] + "."

                            # Create version history entry
                            reversion.set_user(request.user)
                            reversion.set_comment(comment)

                        update_list.append({"record": found_record.system_id_name, "changes": changes})
                elif not found_record:
                    # Creates a new record and creates an entry in the version history
                    with reversion.create_revision():
                        # Create Record
                        new_record.created_by = request.user.email
                        new_record.modified_by = request.user.email
                        new_record.save()

                        # Create version history entry
                        reversion.set_user(request.user)
                        reversion.set_comment("Created via CSV import.")
                    changes = new_record.compare(None)
                    create_list.append({"record": new_record.system_id_name, "changes": changes})

                if len(force_failures) > 0:
                    error_message = "Partial Failure(s): " + "\r\n".join(force_failures)
                    failed_list.append({"record": record["system_id"], "changes": error_message})

            except Exception as e:
                if hasattr(e, "message"):
                    error_message = e.message
                else:
                    error_message = str(e)
                failed_list.append({"record": record["system_id"], "changes": error_message})

    # Returns dictionary of results
    return {
        "validation": {"valid": validate_results["valid"], "message": validate_results["message"]},
        "created": create_list,
        "updated": update_list,
        "failed": failed_list,
    }


def get_or_none(cls, id):
    """
    Retrieves a record using an Id from an inputted class, and returns None if it can't find it
    """
    try:
        model = cls.objects.get(id=id)
    except Exception:
        model = None
    return model


def replace_contact(old_contact, new_contact, user):
    """
    Replaces all instances of one contact in the IT Systems Register with another.
    It then returns a list of changes.
    """
    changes = []

    # Searches for both contacts
    try:
        old_contact_fk = DepartmentUser.objects.get(email=old_contact)
    except DepartmentUser.DoesNotExist:
        old_contact_fk = None
    try:
        new_contact_fk = DepartmentUser.objects.get(email=new_contact)
    except DepartmentUser.DoesNotExist:
        new_contact_fk = None

    if old_contact_fk and new_contact_fk:
        # Retrieves all related systems of the old user
        related_systems = get_user_related_systems(old_contact_fk)

        # Replaces each instance of the old contact with the new contact, and creates an entry in the version history of each updated record
        for system_id, roles in related_systems.items():
            with reversion.create_revision():
                try:
                    record = ITSystemRecord.objects.get(system_id=system_id)
                    # Updates the IT System to replace the old user
                    for role in roles:
                        setattr(record, role, new_contact_fk)
                    record.modified_by = user.email
                    record.save()
                    # Updates change log
                    changes.append({"record": record.system_id, "success": True, "changes": roles})

                    # Create comment for version history
                    change_log = "Changed via web request: "
                    for field in roles:
                        change_log += record.__display_field__(field) + ", "
                    comment = change_log[:-2] + "."

                    # Create version history entry
                    reversion.set_user(user)
                    reversion.set_comment(comment)
                except Exception as e:
                    # Notes failure in the change log
                    changes.append({"record": record.system_id, "success": False, "changes": str(e)})
    else:
        error_msg = "Failed to find user for value(s):"
        if not old_contact_fk:
            error_msg += " old_contact - '" + old_contact + "'"
        if not new_contact_fk:
            error_msg += " new_contact - '" + new_contact + "'"
        raise DepartmentUser.DoesNotExist(error_msg)
    return changes


def edit_record_from_dict(record, dict, user):
    """updates record with new values passed in from a dictionary, returning the updated record values as a dictionary"""
    # Compares incoming values to base record
    incoming = record.to_dict()
    incoming.update(dict)
    incoming_rec = ITSystemRecord()
    incoming_rec.set_from_dict(incoming)
    changes = record.compare(incoming_rec)

    if len(changes) > 0:
        # Updates record, creating an addition to the version history
        with reversion.create_revision():
            # updated record
            record.set_from_dict(dict=incoming, plain_text=True, force=False)
            record.modified_by = user.email
            record.save()

            # Create comment for version history
            change_log = "Changed via web request: "
            for change in changes:
                change_log += change["verbose_field"] + ", "
            comment = change_log[:-2] + "."

            # Create version history entry
            reversion.set_user(user)
            reversion.set_comment(comment)

    # Returns result
    return record.to_dict()


def get_unique_users(field):
    """
    Retrieves all unique contacts in a specified ITSystemRecord contact field
    """
    unique_vals = ITSystemRecord.objects.values_list(field, flat=True).distinct()
    return DepartmentUser.objects.filter(pk__in=unique_vals).order_by("email")


def __validate_csv(csv_file):
    """
    Validates that passed-in file is a csv file, has the correct headers, and is under 2mb.
    Results are passed back as a dictionary containing a validation boolean and an error message for display
    """
    valid = False
    msg = ""
    raw_text = None
    # Checks that file is a CSV
    if csv_file.name.endswith(".csv"):
        # Checks that file isn't chunked / over 2 mb
        if not csv_file.multiple_chunks():
            raw_text = csv_file.read().decode(encoding="utf-8", errors="replace")
            csv_headers = raw_text.splitlines()[0].split(",")
            model_fields = __get_model_fields()
            all_headers_present = True
            for field in model_fields:
                all_headers_present = field.name in csv_headers and all_headers_present
            # Checks that all required headers are present
            if all_headers_present:
                valid = True
                msg = "CSV is Valid"
            else:
                msg = "CSV Headers do not match the required format"
        else:
            msg = "File size is too large (>2MB)."
    else:
        msg = "The selected file isn't a CSV"
    return {"valid": valid, "message": msg, "raw_text": raw_text}


def __get_model_fields():
    """
    Retrieves data-entry relevant fields of the ITSystemRecord class.
    """
    excluded_fields = ["created_date", "modified_date", "created_by", "modified_by", "id", "_state"]
    return [x for x in ITSystemRecord._meta.get_fields() if x.name not in excluded_fields]


def get_user_related_systems(user, hide_decommissioned=False, verbose_names=False):
    """
    returns a dictionary of arrays that represent the systems a user is a contact in, and what roles they fill.
    """
    systems_dict = {}
    __process_related_list(
        systems_dict,
        user.systems_business_service_owner_of.all(),
        "Business Service Owner" if verbose_names else "business_service_owner",
        hide_decommissioned,
    )
    __process_related_list(
        systems_dict, user.systems_owner_of.all(), "System Owner" if verbose_names else "system_owner", hide_decommissioned
    )
    __process_related_list(
        systems_dict,
        user.systems_technology_custodian_of.all(),
        "Technology Custodian" if verbose_names else "technology_custodian",
        hide_decommissioned,
    )
    __process_related_list(
        systems_dict,
        user.systems_information_custodian_of.all(),
        "Information Custodian" if verbose_names else "information_custodian",
        hide_decommissioned,
    )

    return systems_dict


def __process_related_list(systems_dict, related_list, fieldname, hide_decommissioned):
    """
    For each related system, appends the specified field to that systems list.
    Hides decommissioned systems if specified.
    """
    for item in related_list:
        if not (hide_decommissioned and item.status.name == "Decommissioned"):
            if item.system_id in systems_dict:
                systems_dict[item.system_id].append(fieldname)
            else:
                systems_dict[item.system_id] = [fieldname]
