from django.db import models
from django.core.exceptions import FieldDoesNotExist
from django.contrib.postgres.fields import JSONField,ArrayField

class OriginalConfigMixin(models.Model):
    original_configs = JSONField(null=True,editable=False)
    def set_config(self,field_name,field_value,update_fields):
        """
        set model field to new value.
        if the field is editable, save the value to original_configs and also update the field if not edited by the user
        if the field is not editable, just update the field directly
        """
        field = self._meta.get_field(field_name)
        original_configs_field = None
        try:
            original_configs_field = self._meta.get_field("original_configs")
        except FieldDoesNotExist as ex:
            pass
    
        if field.editable and original_configs_field:
            #field is editable,update the original value
            if isinstance(field,models.ForeignKey):
                if (self.original_configs.get(field_name) if self.original_configs else None) == (field_value.pk if field_value else None):
                    #configure is not changed
                    return 
                else:
                    #configure is changed
                    if not self.original_configs:
                        self.original_configs = {}
                    if hasattr(self,field_name) and getattr(self,field_name):
                        if getattr(self,field_name).pk == self.original_configs.get(field_name):
                            #configure was not edited by the user
                            setattr(self,field_name,field_value)
                            update_fields.append(field_name)
                    elif not self.original_configs.get(field_name):
                        #configure was not edited by the user
                        setattr(self,field_name,field_value)
                        update_fields.append(field_name)
    
                    self.original_configs[field_name] = (field_value.pk if field_value else None)
                    if "original_configs" not in update_fields:
                        update_fields.append("original_configs")
            else:
                if (self.original_configs.get(field_name) if self.original_configs else None) == field_value:
                    #configure is not changed
                    return
                else:
                    #configure is changed
                    if not self.original_configs:
                        self.original_configs = {}
                    if getattr(self,field_name) == self.original_configs.get(field_name):
                        #configure was not edited by the user
                        setattr(self,field_name,field_value)
                        update_fields.append(field_name)
    
                    self.original_configs[field_name] = field_value
                    if "original_configs" not in update_fields:
                        update_fields.append("original_configs")
        else:
            if getattr(self,field_name) == field_value:
                #not changed
                return
            else:
                setattr(self,field_name,field_value)
                update_fields.append(field_name)

    class Meta:
        abstract = True

