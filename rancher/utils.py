import datetime
import re
import  json
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

def parse_json(s,null={}):
    """
    convert a object json string to an object
    return  null if s is empty
    """
    
    if s is None:
        return null

    if not isinstance(s,str):
        return s
   
    try:
        while isinstance(s,str):
            s = s.strip()
            if not s:
                return null

            s = json.loads(s)
    except:
        pass

    if s is None:
        return null
    else:
        return s


ip_re = re.compile("^[0-9]{1,3}(\.[0-9]{1,3}){3,3}$")
def parse_host(host):
    """
    Return (domain,hostname,ip) if have
    """
    ip = None
    if ip_re.search(host):
        #ip address
        hostname = host
        ip = host
        domain = None
    elif "." in host:
        hostname,domain = host.split(".",1)
    else:
        hostname = host
        domain = None

    return (domain,hostname,ip)



