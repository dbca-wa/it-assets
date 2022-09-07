from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Div, HTML
from crispy_forms.bootstrap import FormActions
from django import forms


class BaseFormHelper(FormHelper):
    form_class = 'form-horizontal'
    form_method = 'POST'
    label_class = 'col-xs-12 col-sm-3 col-md-2'
    field_class = 'col-xs-12 col-sm-9 col-md-10'


class ConfirmPhoneNosForm(forms.Form):
    work_telephone = forms.ChoiceField(
        choices=[], widget=forms.RadioSelect, required=True,
        help_text='Teams / landline phone number. If none of these options are correct, contact Service Desk.')
    work_mobile_phone = forms.ChoiceField(
        choices=[], widget=forms.RadioSelect, required=True,
        help_text='Department-supplied mobile phone number. If none of these options are correct, contact Service Desk.')
    submit = Submit('submit', 'Submit', css_class='btn-lg')

    def __init__(self, options, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('''
                    <p>In order to consolidate staff contact details, OIM is requesting that staff confirm their work telephone numbers which are currently on record.</p>
                    <p>Please choose the current, correct option in each of the fields below.</p>
                    <p><strong>In the event that listed options are all incorrect, please contact Service Desk PRIOR TO submitting this form.</strong></p>
                    <br>
                    '''),
                    css_id='div_id_instructions'
                ),
            ),
            'work_telephone',
            'work_mobile_phone',
            FormActions(self.submit),
        )
        if options['work_telephone']:
            self.fields['work_telephone'].choices = options['work_telephone']
        else:
            self.fields['work_telephone'].required = False
            self.helper.layout.remove('work_telephone')
        if options['work_mobile_phone']:
            self.fields['work_mobile_phone'].choices = options['work_mobile_phone']
        else:
            self.fields['work_mobile_phone'].required = False
            self.helper.layout.remove('work_mobile_phone')
