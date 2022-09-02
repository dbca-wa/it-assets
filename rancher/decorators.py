from django.urls import reverse
from django.utils.html import mark_safe


def _get_change_url(self,obj):
    if not obj:
        return None
    if not self.__class__._change_url_name:
        self.__class__._change_url_name = 'admin:{}_{}_change'.format(obj.__class__._meta.app_label,obj.__class__._meta.model_name)
    return  reverse(self.__class__._change_url_name, args=(obj.id,))


def add_changelink(field_name):
    def _decorator(cls):
        def _get_field(self,obj,name,link=False):
            if not obj:
                return ""
            else:
                val = getattr(obj,name)
                if not val:
                    return ""
                elif link:
                    return mark_safe("<A href='{}'>{}</A>".format(self.get_change_url(obj),val))
                else:
                    return val

        def _get_field_display(self,obj,name,link=False):
            if not obj:
                return ""
            else:
                get_val = getattr(obj,name)
                if not get_val:
                    return ""
                else:
                    val = get_val()
                    if not val:
                        return ""
                    elif link:
                        return mark_safe("<A href='{}'>{}</A>".format(self.get_change_url(obj),val))
                    else:
                        return val

        if not cls.readonly_fields:
            return cls

        cls._change_url_name = None
        cls.get_field = _get_field
        cls.get_field_display = _get_field_display
        cls.get_change_url = _get_change_url

        if not isinstance(cls.readonly_fields,list):
            cls.readonly_fields = list(cls.readonly_fields)

        try:
            index = cls.readonly_fields.index(field_name)
        except:
            return cls

        name = cls.readonly_fields[index]
        #rename the name to avoid confliction
        new_name = "_{}_".format(name)
        if name.startswith("get_") and name.endswith("_display"):
            method_body = """
def {2}(self,obj):
    return self.get_field_display(obj,'{1}',True)
setattr({2},"short_description",'{0}')
""".format(name[4:-8],name,new_name)
        else:
            method_body = """
def {1}(self,obj):
    return self.get_field(obj,'{0}',True)
setattr({1},"short_description",'{0}')
    """.format(name,new_name)
        exec(method_body)
        setattr(cls,new_name,eval(new_name))
        cls.readonly_fields[index] = new_name
        if cls.fields:
            if not isinstance(cls.fields,list):
                cls.fields = list(cls.fields)

            try:
                index1 = cls.fields.index(name)
                cls.fields[index1] = new_name
            except:
                pass

        return cls
    return _decorator


def many2manyinline(field_name):
    def _decorator(cls):
        def _get_field(self,obj,name,link=False):
            if not obj:
                return ""
            else:
                target = getattr(obj,field_name)
                if not target:
                    return ""
                val = getattr(target,name)
                if not val:
                    return ""
                elif link:
                    return mark_safe("<A href='{}'>{}</A>".format(self.get_change_url(target),val))
                else:
                    return val

        def _get_field_display(self,obj,name,link=False):
            if not obj:
                return ""
            else:
                target = getattr(obj,field_name)
                if not target:
                    return ""
                get_val = getattr(target,name)
                if not get_val:
                    return ""
                else:
                    val = get_val()
                    if not val:
                        return ""
                    elif link:
                        return mark_safe("<A href='{}'>{}</A>".format(self.get_change_url(target),val))
                    else:
                        return val

        cls._change_url_name = None

        cls.get_field = _get_field
        cls.get_field_display = _get_field_display
        cls.get_change_url = _get_change_url

        first = True
        if cls.readonly_fields:
            readonly_fields = list(cls.readonly_fields)
        else:
            readonly_fields = None

        if cls.fields:
            fields = list(cls.fields)
        else:
            fields = None
        index = 0
        length = len(readonly_fields) if readonly_fields else 0
        while index < length:
            name = readonly_fields[index]
            if name.startswith("_"):
                #local declared fields, ignore
                index += 1
                continue
            #rename the name to avoid confliction
            new_name = "_{}_".format(name)
            if name.startswith("get_") and name.endswith("_display"):
                method_body = """
def {2}(self,obj):
    return self.get_field_display(obj,'{1}',{3})
setattr({2},"short_description",'{0}')
""".format(name[4:-8],name,new_name,first)
            else:
                method_body = """
def {1}(self,obj):
    return self.get_field(obj,'{0}',{2})
setattr({1},"short_description",'{0}')
""".format(name,new_name,first)
            exec(method_body)
            setattr(cls,new_name,eval(new_name))
            readonly_fields[index] = new_name
            if fields:
                pos = 0
                while pos < len(fields):
                    if fields[pos] == name:
                        fields[pos] = new_name
                        break
                    pos += 1
            index += 1
            first = False

        if readonly_fields:
            cls.readonly_fields = readonly_fields
        if fields:
            cls.fields = fields

        return cls
    return _decorator
