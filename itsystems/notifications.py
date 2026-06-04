from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def send_user_deletion_email(user, related_systems):
    """
    Sends a contact deletion notification email to the defined ITSR Mailbox.
    """
    all_systems = ""
    all_systems_html = ""

    if len(related_systems) > 0:
        # Converts each 'system' item into a human readable text.
        for system_id, roles in related_systems.items():
            all_systems += "\n - " + system_id + ": " + ", ".join(roles)
            all_systems_html += "<li>" + system_id + ": " + ", ".join(roles) + "</li>"

        # Creates email content
        text_content = f"""Hi,
This is an automated email to notify you of the deletion of an IT System Register user contact.
User: {user}
Affected Systems: {all_systems}

Regards,
OIM Service Desk"""
        html_content = f"""<p>Hi,</p>
<p>This is an automated email to notify you of the deletion of an IT System Register user contact.</p>
<p><ul>User: {user}<br>
Affected Fields:{all_systems_html}</ul></p>
<p>Regards,</p>
<p>OIM Service Desk</p>"""
        subject = f"IT System Register - User Contact Deletion: {user}"

        # Sends the email
        return notify(subject=subject, body=text_content, html_body=html_content)


def send_daily_audit_email(flagged_users):
    """
    Sends a contact audit email to the specified ITSR mailbox.
    This email contains a list of flagged user contact fields that require attention.
    """

    num_users = len(flagged_users)
    if num_users > 0:
        # Creates an initial text body and subject
        subject = "IT Systems Register - Flagged Users"
        text_content_header = f"Hi,\n This is an automated email to notify you of IT Systems Register contacts flagged as missing from address book.\n There are {num_users} flagged contacts.\n"
        html_content_header = f"<p>Hi,</p><p>This is an automated email to notify you of IT Systems Register contacts flagged as missing from address book.</p><p>There are {num_users} flagged contacts.</p>"

        text_content_footer = "Regards,\nOIM Service Desk\n"
        html_content_footer = "<p>Regards,</p><p>OIM Service Desk</p>"
        text_content_body = ""
        html_content_body = ""

        # Converts each flagged_user item into human readable text
        for flagged_user in flagged_users:
            text_content_body += f"""
{flagged_user["system_name"]}
{flagged_user["field_name"]}: {flagged_user["user_email"]}
Account status: {flagged_user["user_status"]}
"""
            html_content_body += f"""
<ul>
<li><b>{flagged_user["system_name"]}</b></li>
<li>{flagged_user["field_name"]}: {flagged_user["user_email"]}</li>
<li>Account status: {flagged_user["user_status"]}</li>
</ul>
"""
        # Appends new text to existing text body
        text_body = text_content_header + text_content_body + text_content_footer
        html_body = html_content_header + html_content_body + html_content_footer

        # Sends the email
        return notify(subject=subject, body=text_body, html_body=html_body)


def notify(subject, body, html_body):
    """
    Sends an email to the specified ITSR mailbox.
    """
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.NOREPLY_EMAIL,
        to=[settings.IT_SYSTEMS_REGISTER_EMAIL],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return msg
