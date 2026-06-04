from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import DepartmentUser
from .notifications import send_user_deletion_email
from .utils import get_user_related_systems


@receiver(pre_delete, sender=DepartmentUser)
def check_it_system_register_contacts(*args, **kwargs):
    """
    If a DepartmentUser is deleted while being listed on the IT System Register as a contact, notify the set ITSR Mailbox.
    """
    user = kwargs["instance"]

    # Finds all related systems to a user and their roles in it
    related_systems = get_user_related_systems(user, hide_decommissioned=True, verbose_names=True)
    if len(related_systems) > 0:
        # Sends deletion notification
        send_user_deletion_email(user, related_systems)
