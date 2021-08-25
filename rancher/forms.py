from django_json_widget.widgets import JSONEditorWidget

from django import forms

from . import models

class EnvScanModuleForm(forms.ModelForm):
    class Meta:
        model = models.EnvScanModule
        fields = "__all__"
        widgets = {
            'sourcecode': forms.Textarea(attrs={'style':'width:90%;height:500px'}),
        }
        
class ContainerImageFamilyForm(forms.ModelForm):
    class Meta:
        model = models.ContainerImageFamily
        fields = "__all__"
        widgets = {
            'config': JSONEditorWidget,
            'contacts':forms.TextInput(attrs={"style":"width:80%"}),
            'filtercode': forms.Textarea(attrs={"style":"width:80%;height:200px"})
        }
        
