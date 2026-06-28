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
    fields = []
    if "status_filter" in context:
        result += renderButton(str(context["status_filter"]), "status", "Status")
        fields.append("status")
    if "division_filter" in context:
        result += renderButton(str(context["division_filter"]), "division", "Division")
        fields.append("division")
    if "business_service_owner_filter"  in context:
        result += renderButton(str(context["business_service_owner_filter"]), "business_service_owner", "Business Service Owner")
        fields.append("business_service_owner")
    if "system_owner_filter" in context:
        result += renderButton(str(context["system_owner_filter"]), "system_owner", "System Owner")
        fields.append("system_owner")
    if "technology_custodian_filter" in context:
        result += renderButton(str(context["technology_custodian_filter"]), "technology_custodian", "Technology Custodian")
        fields.append("technology_custodian")
    if "information_custodian_filter" in context:
        result += renderButton(str(context["information_custodian_filter"]), "information_custodian", "Information Custodian")
        fields.append("information_custodian")
    if "seasonality_filter" in context:
        result += renderButton(str(context["seasonality_filter"]), "seasonality", "Seasonality")
        fields.append("seasonality")
    if "availability_filter" in context:
        result += renderButton(str(context["availability_filter"]), "availability", "Availability")
        fields.append("availability")
    if "vital_records_filter" in context:
        result += renderButton(str(context["vital_records_filter"]), "vital_records", "Vital Records")
        fields.append("vital_records")
    if "sensitivity_filter" in context:
        result += renderButton(str(context["sensitivity_filter"]), "sensitivity", "Sensitivity")
        fields.append("sensitivity")
    if "system_type_filter" in context:
        result += renderButton(str(context["system_type_filter"]), "system_type", "System Type")
        fields.append("system_type")
    
    if len(fields)>0:
        fields_string = "['" + "','".join(fields) + "']"
        clearAllButton = """<button type="button" class="btn btn-outline-secondary m-1" onClick="clearFields(""" + fields_string + """);">Clear All Filters</button>"""
        result = clearAllButton + result

    return format_html(result, **format_kwargs)

def renderButton(filter, field_name, verbose_name):
    """
    Renders a button that clears the inputted filter field if clicked
    """
    return (
        """<button type="button" class="btn btn-outline-secondary m-1" onClick="clearField('"""
        + field_name
        + """')">"""
        + verbose_name
        + """ | """
        + (filter or "None")
        + """  ✕</button>"""
    )

@register.simple_block_tag(takes_context=True)
def renderSort(context, content,field_name):
    """
    Renders an order-by button for a given field.
    """
    format_kwargs = {
        "field_name": field_name,
        "content": content,
        "context":context,
    }    
    button_icon = "⇅"
    if "order_by" in context:
        if context["order_by"] == field_name:
            if context["asc"] == "true":
                button_icon = "↑"
            else:
                button_icon = "↓"

    result = """<button type="button" class="order" onClick="orderField('{field_name}');">""" + button_icon  + """</button>"""

    return format_html(result, **format_kwargs)


@register.simple_block_tag(takes_context=True)
def renderSelect(context, content, id, filter_name, list_name, nullable=False):
    """
    Renders a dropdown field that defaults the selected option to the previously selected option.
    """
    format_kwargs = {
        "id": id,
        "list_name": list_name,
        "filter_name": filter_name,
        "nullable": nullable,
        "content": content,
        "context": context,
    }

    result = """<select id="{id}" class="select2" name="{id}" form="filters" onchange="this.form.submit()">"""
    if filter_name in context:
        result += """<option disabled id="{id}_disabled" value></option>"""
        if nullable and context[filter_name] == None:
            result += """<option selected value=>(Empty)</option>"""
        elif nullable:
            result += """<option value=>(Empty)</option>"""
    else:
        result += """<option disabled id="{id}_disabled" selected value></option>"""
        if nullable:
            result += """<option value=>(Empty)</option>"""

    if context.get(filter_name):
        for option in context[list_name]:
            if option.id == context[filter_name].id:
                result += """<option selected="selected" value = """ + str(option.id) + """>""" + str(option) + """</option>"""
            else:
                result += """<option value = """ + str(option.id) + """>""" + str(option) + """</option>"""
    else:
        for option in context[list_name]:
            result += """<option value = """ + str(option.id) + """>""" + str(option) + """</option>"""

    result += "</select>"
    return format_html(result, **format_kwargs)

@register.simple_block_tag(takes_context=True)
def renderBooleanSelect(context, content, id, filter_name, nullable=False):
    """
    Renders a boolean dropdown field that defaults the selected option to the previously selected option.
    """
    format_kwargs = {
        "id": id,
        "filter_name": filter_name,
        "content": content,
        "context": context,
    }

    result = """<select id="{id}" class="select2" name="{id}" form="filters" onchange="this.form.submit()">"""
    if filter_name in context:
        result += """<option disabled id="{id}_disabled" value></option>"""
        if nullable and context[filter_name] == None:
            result += """<option selected value=>(Empty)</option>"""
        elif nullable:
            result += """<option value=>(Empty)</option>"""
    else:
        result += """<option disabled id="{id}_disabled" selected value></option>"""
        if nullable:
            result += """<option value=>(Empty)</option>"""

    if filter_name in context:
        if context[filter_name]=="True":
            result+="""
                <option selected>True</option>
                <option>False</option>
                """
        elif context[filter_name]=="False":
            result+="""
                <option>True</option>
                <option selected>False</option>
                """
        else:
         result+="""
            <option>True</option>
            <option>False</option>
            """ 
    else:
        result+="""
            <option>True</option>
            <option>False</option>
            """

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

@register.simple_block_tag(takes_context=True)
def encodeURL(context, content):
    """
    Encodes all filtering and search variables (not including pagination variables) into a url string.
    """
    format_kwargs = {
        "content": content,
        "context":context
    }
    url_string = ""
    if "order_by" in context:
        url_string += "&order_by="+context["order_by"]
    if "asc" in context:
        url_string += "&asc="+context["asc"]
    if "query_string" in context and len(context["query_string"])>0:
        url_string += "&q="+context["query_string"]
    if "SIDN" in context:
        url_string += "&SIDN=on"
    if "Desc" in context:
        url_string += "&Desc=on"
    if "BSO" in context:
        url_string += "&BSO=on"
    if "SO" in context:
        url_string += "&SO=on"
    if "TC" in context:
        url_string += "&TC=on"
    if "IC" in context:
        url_string += "&IC=on"
    if "DA" in context:
        url_string += "&DA=on"
    if "RaD" in context:
        url_string += "&RaD=on"
    if "UBCS" in context:
        url_string += "&UBCS=on"
    if "drafts_filter" in context:
        url_string += "&show_drafts="+str(context["drafts_filter"])
    if "status_filter" in context:
        url_string += "&status="+str(getattr(context["status_filter"],'id',""))
    if "division_filter" in context:
        url_string += "&division="+str(getattr(context["division_filter"],'id',""))
    if "business_service_owner_filter" in context:
        url_string += "&business_service_owner="+str(getattr(context["business_service_owner_filter"],'id',""))
    if "system_owner_filter" in context:
        url_string += "&system_owner="+str(getattr(context["system_owner_filter"],'id',""))
    if "technology_custodian_filter" in context:
        url_string += "&technology_custodian="+str(getattr(context["technology_custodian_filter"],'id',""))
    if "information_custodian_filter" in context:
        url_string += "&information_custodian="+str(getattr(context["information_custodian_filter"],'id',""))
    if "seasonality_filter" in context:
        url_string += "&seasonality="+str(getattr(context["seasonality_filter"],'id',""))
    if "availability_filter" in context:
        url_string += "&availability="+str(getattr(context["availability_filter"],'id',""))
    if "vital_records_filter" in context:
        url_string += "&vital_records="+context["vital_records_filter"]
    if "sensitivity_filter" in context:
        url_string += "&sensitivity="+str(getattr(context["sensitivity_filter"],'id',""))
    if "system_type_filter" in context:
        url_string += "&system_type="+str(getattr(context["system_type_filter"],'id',""))

    return format_html(url_string, **format_kwargs)
