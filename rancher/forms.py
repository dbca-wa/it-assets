from django_json_widget.widgets import JSONEditorWidget

from django import forms
from django.utils.safestring import mark_safe

from . import models
from itassets.utils import GetRequestUserMixin,SecretPermissionMixin
from itassets.widgets import textarea_readonly_widget,boolean_readonly_widget,json_readonly_widget,text_readonly_widget

def get_help_text(model_class,field):
    return mark_safe("<pre>{}</pre>".format(model_class._meta.get_field(field).help_text))

class EnvScanModuleForm(forms.ModelForm):
    class Meta:
        model = models.EnvScanModule
        fields = "__all__"
        widgets = {
            'sourcecode': forms.Textarea(attrs={'style':'width:90%;height:500px'}),
        }
        
class ContainerImageFamilyForm(SecretPermissionMixin,GetRequestUserMixin,forms.ModelForm):
    sourcecode = forms.CharField(required=False,widget=forms.Textarea(attrs={"style":"width:80%;height:200px"}),help_text=get_help_text(models.ContainerImageFamily,"sourcecode"))
    is_developer = staticmethod(lambda user,obj:(user.email in obj.contacts) if obj and obj.contacts else False)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance :
            if not self.secretpermission_granted(self.instance,user = self.user):
                if "sourcecode" in self.fields :
                    self.fields["sourcecode"].widget = textarea_readonly_widget
                if "enable_notify" in self.fields :
                    self.fields["enable_notify"].widget = boolean_readonly_widget
                if "enable_warning_msg" in self.fields :
                    self.fields["enable_warning_msg"].widget = boolean_readonly_widget
                if "config" in self.fields:
                    self.fields["config"].widget =  json_readonly_widget
                if "contacts" in self.fields :
                    self.fields["contacts"].widget = text_readonly_widget

    class Meta:
        model = models.ContainerImageFamily
        fields = "__all__"
        widgets = {
            'config': JSONEditorWidget,
            'contacts':forms.TextInput(attrs={"style":"width:80%"}),
        }
        
