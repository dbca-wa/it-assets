from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import DepartmentUser
from .notifications import send_user_deletion_email


@receiver(pre_delete, sender=DepartmentUser)
def check_it_system_register_contacts(*args, **kwargs):
    """
    If a DepartmentUser is deleted while being listed on the IT System Register as a contact, notify the set ITSR Mailbox.
    """
    user = kwargs["instance"]

    systems = []
    # Creates a list of all systems the user is a contact in
    systems.extend(_process_list(user.systems_business_service_owner_of.all(), "Business Service Owner"))
    systems.extend(_process_list(user.systems_owner_of.all(), "System Owner"))
    systems.extend(_process_list(user.systems_technology_custodian_of.all(), "Technology Custodian"))
    systems.extend(_process_list(user.systems_information_custodian_of.all(), "Information Custodian"))

    if len(systems) > 0:
        # Sends deletion notification
        send_user_deletion_email(systems=systems, field_value=str(user))


def _process_list(system_list, name):
    """
    Converts the systems list to a formatted list of active systems
    """
    processed_list = []
    if len(system_list) > 0:
        for system in system_list:
            if system.status.name != "Decommissioned":
                processed_list.append({"system": str(system), "field": name})
    return processed_list
