import datetime
from data_storage.utils import get_property

from django.utils import timezone

def to_datetime(data):
    if not data:
        return None
    data = data.strip()
    if not data or data.lower() in ("none","null"):
        return None

    if data.endswith("Z"):
        data = data[:-1]
    data = data.rsplit(".",1)
    d = datetime.datetime.strptime(data[0],"%Y-%m-%dT%H:%M:%S")
    if len(data) == 2:
        d += datetime.timedelta(milliseconds=int(data[1]))


    return timezone.localtime(d.replace(tzinfo=datetime.timezone.utc))

def set_fields(obj,fields,update_fields=None):
    if update_fields is None:
        update_fields = None if obj.pk is None else []
    for field,val in fields:
        if obj.pk is None:
            setattr(obj,field,val)
        elif getattr(obj,field) != val:
            setattr(obj,field,val)
            if field not in update_fields:
                update_fields.append(field)

    return update_fields

def set_field(obj,field,val,update_fields):
    if obj.pk is None:
        setattr(obj,field,val)
    elif getattr(obj,field) != val:
        setattr(obj,field,val)
        if field not in update_fields:
            update_fields.append(field)

def set_fields_from_config(obj,config,fields,update_fields=None):
    if update_fields is None:
        update_fields = None if obj.pk is None else []
    for field,prop,get_func in fields:
        val = get_property(config,prop,get_func)
        if obj.pk is None:
            setattr(obj,field,val)
        elif getattr(obj,field) != val:
            setattr(obj,field,val)
            if field not in update_fields:
                update_fields.append(field)

    return update_fields

