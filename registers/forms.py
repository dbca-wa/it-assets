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


class UserChoiceField(forms.ChoiceField):
    # A basic ChoiceField that skips validation.
    def validate(self, value):
        pass


class ChangeRequestCreateForm(forms.ModelForm):
    """Base ModelForm class for ChangeRequest models.
    """
    save_button = Submit('save', 'Save draft', css_class='btn-lg')
    endorser_choice = UserChoiceField(
        required=False, label='Endorser', help_text='The person who will endorse this change prior to CAB')
    implementer_choice = UserChoiceField(
        required=False, label='Implementer', help_text='The person who will implement this change')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestCreateForm, self).__init__(*args, **kwargs)
        # Add a CSS class to user choice fields, to upgrade them easier using JS.
        self.fields['endorser_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementer_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementation'].help_text = 'Implementation/deployment instructions, including any rollback procedure'
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
                'title', 'description',
            ),
            Fieldset(
                'Endorsement and Implementer',
                'endorser_choice', 'implementer_choice',
            ),
            Fieldset(
                'Implementation',
                'test_date', 'planned_start', 'planned_end', 'outage',
                Div(
                    HTML('''<p>Please note that implementation instructions must be supplied prior to submission for approval.
                         Text instructions or an uploaded document (e.g. Word, PDF) are acceptable. Implemenation instructions
                         should include any details related to post-change testing and any rollback procedures.</p><br>'''),
                    css_id='div_id_implementation_note'
                ),
                'implementation', 'implementation_docs',
            ),
            Fieldset(
                'Communication',
                Div(
                    HTML('<p>Please include details about any required communications (timing, stakeholders, instructions, etc.)</p><br>'),
                    css_id='div_id_communication'
                ),
                'communication', 'broadcast',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'description', 'test_date', 'planned_start', 'planned_end', 'implementation',
            'implementation_docs', 'outage', 'communication', 'broadcast']

    def clean(self):
        if self.cleaned_data['planned_start'] and self.cleaned_data['planned_end']:
            if self.cleaned_data['planned_start'] > self.cleaned_data['planned_end']:
                msg = 'Planned start cannot be later than planned end.'
                self._errors['planned_start'] = self.error_class([msg])
                self._errors['planned_end'] = self.error_class([msg])
        return self.cleaned_data


class StandardChangeRequestCreateForm(forms.ModelForm):
    """Base ModelForm class for ChangeRequest models (standard change type).
    """
    save_button = Submit('save', 'Save draft', css_class='btn-lg')
    endorser_choice = UserChoiceField(
        required=False, label='Endorser', help_text='The person who will endorse this change prior to CAB')
    implementer_choice = UserChoiceField(
        required=False, label='Implementer', help_text='The person who will implement this change')

    def __init__(self, *args, **kwargs):
        super(StandardChangeRequestCreateForm, self).__init__(*args, **kwargs)
        self.fields['standard_change'].required = True
        self.fields['standard_change'].help_text = 'Standard change reference'
        # Add a CSS class to user choice fields, to upgrade them easier using JS.
        self.fields['endorser_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementer_choice'].widget.attrs['class'] = 'select-user-choice'
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('<p>Standard changes must be agreed and registered with OIM prior. Note that all fields below need not be completed until the point of submission and approval.</p><br>'),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Overview',
                'title', 'standard_change',
            ),
            Fieldset(
                'Endorsement and Implementer',
                'endorser_choice', 'implementer_choice',
            ),
            Fieldset(
                'Implementation',
                'planned_start', 'planned_end', 'outage',
            ),
            Fieldset(
                'Communication',
                Div(
                    HTML('<p>Please include details about any required communications (timing, stakeholders, instructions, etc.)</p><br>'),
                    css_id='div_id_communication'
                ),
                'communication', 'broadcast',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'standard_change', 'planned_start', 'planned_end', 'outage',
            'communication', 'broadcast']


class ChangeRequestChangeForm(ChangeRequestCreateForm):
    submit_button = Submit('submit', 'Submit for endorsement', css_class='btn-lg btn-success')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestChangeForm, self).__init__(*args, **kwargs)
        # Update the helper layout FormActions class to include the submit button.
        self.helper.layout[-1].fields.append(self.submit_button)


class StandardChangeRequestChangeForm(StandardChangeRequestCreateForm):
    submit_button = Submit('submit', 'Submit for endorsement', css_class='btn-lg btn-success')

    def __init__(self, *args, **kwargs):
        super(StandardChangeRequestChangeForm, self).__init__(*args, **kwargs)
        # Update the helper layout FormActions class to include the submit button.
        self.helper.layout[-1].fields.append(self.submit_button)


class ChangeRequestEndorseForm(forms.ModelForm):
    endorse_button = Submit('endorse', 'Endorse change request', css_class='btn-lg btn-success')
    reject_button = Submit('reject', 'Reject change request', css_class='btn-lg btn-warning')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestEndorseForm, self).__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            FormActions(self.endorse_button, self.reject_button),
        )

    class Meta:
        model = ChangeRequest
        fields = ['notes']  # Give the modelform one optional field (not rendered) so it can validate.


class ChangeRequestCompleteForm(forms.ModelForm):
    outcome = forms.ChoiceField(
        choices=[
            ('complete', 'Completed successfully'),
            ('rollback', 'Undertaken and rolled back'),
            ('cancelled', 'Cancelled (not undertaken)'),
        ],
        help_text='What was the final outcome of this change request?'
    )
    save_button = Submit('save', 'Complete change request', css_class='btn-lg')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestCompleteForm, self).__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Change request outcome',
                'outcome', 'completed', 'unexpected_issues', 'notes',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = ['completed', 'unexpected_issues', 'notes']
