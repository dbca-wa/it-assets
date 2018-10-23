from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Div, HTML
from crispy_forms.bootstrap import FormActions
from django import forms
from organisation.models import DepartmentUser
from .models import ChangeRequest


class BaseFormHelper(FormHelper):
    form_class = 'form-horizontal'
    form_method = 'POST'
    label_class = 'col-xs-12 col-sm-4 col-md-3'
    field_class = 'col-xs-12 col-sm-8 col-md-7'
    #help_text_inline = True


class UserChoiceField(forms.ModelChoiceField):
    """Returns a ModelChoiceField of active DepartmentUser objects having "user" account types,
    i.e. not shared/role-based accounts.
    """
    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = DepartmentUser.objects.filter(active=True, account_type__in=DepartmentUser.ACCOUNT_TYPE_USER).order_by('email')
        super(UserChoiceField, self).__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return obj.get_full_name()


class ChangeRequestCreateForm(forms.ModelForm):
    """Base ModelForm class for referral models.
    """
    save_button = Submit('save', 'Save draft', css_class='btn-lg')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestCreateForm, self).__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['requester'] = UserChoiceField(required=False, help_text='The person requesting this change')
        self.fields['approver'] = UserChoiceField(required=False, help_text='The person who will approve this change')
        self.fields['implementer'] = UserChoiceField(required=False, help_text='The person who will implement this change')
        self.fields['test_date'] = forms.DateField(
            required=False, widget=forms.TextInput(attrs={'class':'date-input'}),
            help_text='Date that the change was tested')
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('<p>Note that all fields below need not be completed until the point of submission and approval.</p><br>'),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Overview',
                'title', 'change_type', 'standard_change', 'description',
            ),
            Fieldset(
                'Approval',
                'requester', 'approver', 'implementer',
            ),
            Fieldset(
                'Implementation',
                'test_date', 'planned_start', 'planned_end', 'outage',
                Div(
                    HTML('''<p>Please note that implementation instructions must be supplied prior to submission for approval.
                         Text instructions or an uploaded document (e.g. Word, PDF) are acceptable.</p><br>'''),
                    css_id='div_id_implementation_note'
                ),
                'implementation', 'implementation_docs',
            ),
            Fieldset(
                'Communication',
                'communication', 'broadcast',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'change_type', 'standard_change', 'description', 'requester', 'approver',
            'implementer', 'test_date', 'planned_start', 'planned_end', 'implementation',
            'implementation_docs', 'outage', 'communication', 'broadcast']


class ChangeRequestUpdateForm(ChangeRequestCreateForm):
    submit_button = Submit('submit', 'Submit for approval', css_class='btn-lg btn-success')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestUpdateForm, self).__init__(*args, **kwargs)
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('''
                    <p>Note that all fields below need not be completed until the point of submission and approval.</p>
                    <p>Upon submitting a change request for approval, a read-only email link will be sent to the approver for action.</p>
                    <br>'''),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Overview',
                'title', 'change_type', 'standard_change', 'description',
            ),
            Fieldset(
                'Approval',
                'requester', 'approver', 'implementer',
            ),
            Fieldset(
                'Implementation',
                'test_date', 'planned_start', 'planned_end', 'outage',
                Div(
                    HTML('''<p>Please note that implementation instructions must be supplied prior to submission for approval.
                         Text instructions or an uploaded document (e.g. Word, PDF) are acceptable.</p><br>'''),
                    css_id='div_id_implementation_note'
                ),
                'implementation', 'implementation_docs',
            ),
            Fieldset(
                'Communication',
                'communication', 'broadcast',
            ),
            FormActions(self.save_button, self.submit_button),
        )
