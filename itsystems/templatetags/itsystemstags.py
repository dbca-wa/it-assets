from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_block_tag(takes_context=True)
def renderButtons(context, content):
    """
    Renders all dynamic filter buttons in a row.
    """
    format_kwargs = {
        "context": context,
        "content": content,
    }
    result = ""
    if context.get("status_filter"):
        result += renderButton(context["status_filter"].name, "status", "Status")
    if context.get("division_filter"):
        result += renderButton(context["division_filter"].name, "division", "Division")
    if context.get("business_service_owner_filter"):
        result += renderButton(context["business_service_owner_filter"].name, "business_service_owner", "Business Service Owner")
    if context.get("system_owner_filter"):
        result += renderButton(context["system_owner_filter"].name, "system_owner", "System Owner")
    if context.get("technology_custodian_filter"):
        result += renderButton(context["technology_custodian_filter"].name, "technology_custodian", "Technology Custodian")
    if context.get("information_custodian_filter"):
        result += renderButton(context["information_custodian_filter"].name, "information_custodian", "Information Custodian")
    if context.get("seasonality_filter"):
        result += renderButton(context["seasonality_filter"].name, "seasonality", "Seasonality")
    if context.get("availability_filter"):
        result += renderButton(context["availability_filter"].name, "availability", "Availability")
    if context.get("vital_records_filter"):
        result += renderButton(context["vital_records_filter"], "vital_records", "Vital Records")
    if context.get("sensitivity_filter"):
        result += renderButton(context["sensitivity_filter"].name, "sensitivity", "Sensitivity")
    if context.get("system_type_filter"):
        result += renderButton(context["system_type_filter"].name, "system_type", "System Type")

    return format_html(result, **format_kwargs)


def renderButton(filter, field_name, verbose_name):
    """
    Renders a button that clears the inputted filter field if clicked
    """
    return (
        """<button type="button" class="btn btn-outline-secondary" onClick="clearField('"""
        + field_name
        + """')">"""
        + verbose_name
        + """ | """
        + filter
        + """  ✕</button>"""
    )


@register.simple_block_tag(takes_context=True)
def renderSelect(context, content, id, filter, list_name):
    """
    Renders a dropdown field that defaults the selected option to the previously selected option.
    """
    format_kwargs = {
        "id": id,
        "list_name": list_name,
        "content": content,
        "context": context,
    }

    result = """<select id="{id}" class="select2" name="{id}" form="filters" onchange="this.form.submit()">"""
    if filter:
        for option in context[list_name]:
            if option.id == filter.id:
                result += """<option selected="selected" value = """ + str(option.id) + """>""" + str(option) + """</option>"""
            else:
                result += """<option value = """ + str(option.id) + """>""" + str(option) + """</option>"""
    else:
        result += """<option disabled selected value></option>"""
        for option in context[list_name]:
            result += """<option value = """ + str(option.id) + """>""" + str(option) + """</option>"""

    result += "</select>"
    return format_html(result, **format_kwargs)

@register.simple_block_tag(takes_context=False)
def renderCheckboxField(content, title,text, value):
    """
    Renders a checkbox field within the searchbar dropdown menu for selecting fields to search within.
    Defaults to the last selected value.
    """
    format_kwargs = {
        "title": title,
        "text": text,
        "value": value,
        "content": content,
    }
    result = """
    <a class="dropdown-item" href="#">
        <div class="form-check">
    """
    if value:
        result +="""
                <input class="form-check-input" type="checkbox" name="{title}" id="{title}" checked/>
        """
    else:
        result +="""
                <input class="form-check-input" type="checkbox" name="{title}" id="{title}"/>
        """
    result +="""
            <label class="form-check-label" for="{title}">{text}</label>
        </div>
    </a>
    """
    return format_html(result, **format_kwargs)