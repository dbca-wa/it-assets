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


def retrieve(cls, id):
    """
    Retrieves a record using an Id from an inputted class.
    """
    try:
        model = cls.objects.get(id=id)
    except Exception:
        model = None
    return model


# Improvement: Instead of checking through entire database, use related name to directly query the fk field.
def replace_contact(old_contact, new_contact, user):
    """
    Replaces all instances of one contact in the IT Systems Register with another.
    It then returns a list of changes.
    """
    records = ITSystemRecord.objects.all()
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
        # Replaces each instance of the old contact with the new contact, and creates an entry in the version history of each updated record
        for record in records:
            record_changes = []
            with reversion.create_revision():
                # Checks record contacts for old contact
                if record.business_service_owner == old_contact_fk:
                    record.business_service_owner = new_contact_fk
                    record_changes.append("business_service_owner")
                if record.system_owner == old_contact_fk:
                    record.system_owner = new_contact_fk
                    record_changes.append("system_owner")
                if record.technology_custodian == old_contact_fk:
                    record.technology_custodian = new_contact_fk
                    record_changes.append("technology_custodian")
                if record.information_custodian == old_contact_fk:
                    record.information_custodian = new_contact_fk
                    record_changes.append("information_custodian")

                if len(record_changes) > 0:
                    try:
                        # Updates record
                        record.modified_by = user.email
                        record.save()
                        changes.append({"record": record.system_id, "success": True, "changes": record_changes})

                        # Create comment for version history
                        change_log = "Changed via web request: "
                        for field in record_changes:
                            change_log += record.__display_field__(field) + ", "
                        comment = change_log[:-2] + "."

                        # Create version history entry
                        reversion.set_user(user)
                        reversion.set_comment(comment)
                    except Exception as e:
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
    Retrieves data-entry relevant fields of the ITSystemRecord class
    """
    return ITSystemRecord._meta.get_fields()[1:-4]
