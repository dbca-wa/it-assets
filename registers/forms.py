from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Div, HTML
from crispy_forms.bootstrap import FormActions
from django import forms
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
    In order to improve user experience, the DepartmentUser select fields are replaced with basic
    validation-exempt ChoiceFields that are filled client-side via AJAX. Inputted data is then
    saved to the model after form validation.
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
        self.fields['endorser_choice'].label = 'Endorser email'
        self.fields['implementer_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementer_choice'].label = 'Implementer email'
        self.fields['test_result_docs'].help_text += ' - OPTIONAL'
        self.fields['implementation'].help_text = 'Implementation/deployment instructions, including any rollback procedure'
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('<p>Note that all fields below need not be completed until the point of submission for endorsement (RFCs may be saved as drafts).</p><br>'),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Overview',
                'title', 'description',
            ),
            Fieldset(
                'IT Tactical Roadmap',
                HTML('<p>If this change is part of the IT Tactical Roadmap, please provide the initiative name and number and/or project number.</p>'),
                'initiative_name', 'initiative_no', 'project_no',
            ),
            Fieldset(
                'Endorsement and Implementer',
                HTML('<p>Endorser and implementer must be nominated prior to submission for endorsement.</p>'),
                'endorser_choice', 'implementer_choice',
            ),
            Fieldset(
                'Testing and Implementation',
                HTML('<p>Test and implementation dates & times must be supplied prior to submission for endorsement.'),
                'test_date', 'test_result_docs', 'planned_start', 'planned_end', 'outage',
                Div(
                    HTML('''<p>Please note that implementation instructions must be supplied prior to submission for endorsement.
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
            Fieldset(
                'IT Systems',
                Div(
                    HTML('<p>IT Systems that are affected by this change request.')
                ),
                'it_systems',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'description', 'test_date', 'test_result_docs', 'planned_start', 'planned_end', 'implementation',
            'implementation_docs', 'outage', 'communication', 'broadcast', 'it_systems', 'initiative_name', 'initiative_no', 'project_no',
        ]

    def clean(self):
        if self.cleaned_data['planned_start'] and self.cleaned_data['planned_end']:
            if self.cleaned_data['planned_start'] > self.cleaned_data['planned_end']:
                msg = 'Planned start cannot be later than planned end.'
                self._errors['planned_start'] = self.error_class([msg])
                self._errors['planned_end'] = self.error_class([msg])
        return self.cleaned_data


class StandardChangeRequestCreateForm(forms.ModelForm):
    """Base ModelForm class for ChangeRequest models (standard change type).
    See notes on ChangeRequestCreateForm about implementer field.
    """
    save_button = Submit('save', 'Save draft', css_class='btn-lg')
    implementer_choice = UserChoiceField(
        required=False, label='Implementer', help_text='The person who will implement this change')

    def __init__(self, *args, **kwargs):
        super(StandardChangeRequestCreateForm, self).__init__(*args, **kwargs)
        self.fields['standard_change'].required = True
        self.fields['standard_change'].help_text = 'Standard change reference'
        self.fields['implementer_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementer_choice'].label = 'Implementer email'
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('<p>Standard changes must be agreed and registered with OIM prior. Note that all fields below need not be completed until the point of submission (RFCs may be saved as drafts).</p><br>'),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Overview',
                'title', 'standard_change',
            ),
            Fieldset(
                'Implementation',
                HTML('<p>Implementer and implementation dates & times must be supplied prior to submission.'),
                'implementer_choice', 'planned_start', 'planned_end', 'outage',
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

    def clean(self):
        if self.cleaned_data['planned_start'] and self.cleaned_data['planned_end']:
            if self.cleaned_data['planned_start'] > self.cleaned_data['planned_end']:
                msg = 'Planned start cannot be later than planned end.'
                self._errors['planned_start'] = self.error_class([msg])
                self._errors['planned_end'] = self.error_class([msg])
        return self.cleaned_data


class ChangeRequestChangeForm(ChangeRequestCreateForm):
    submit_button = Submit('submit', 'Submit for endorsement', css_class='btn-lg btn-success')

    def __init__(self, *args, **kwargs):
        super(ChangeRequestChangeForm, self).__init__(*args, **kwargs)
        # Update the helper layout FormActions class to include the submit button.
        self.helper.layout[-1].fields.append(self.submit_button)


class StandardChangeRequestChangeForm(StandardChangeRequestCreateForm):
    submit_button = Submit('submit', 'Submit to CAB', css_class='btn-lg btn-success')

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


class EmergencyChangeRequestForm(forms.ModelForm):
    """Change form for an Emergency Change. Basically, a simplified RFC form without
    associated business rules/restrictions.
    """
    save_button = Submit('save', 'Save', css_class='btn-lg')
    endorser_choice = UserChoiceField(
        required=False, label='Endorser', help_text='The person who endorses this change')
    implementer_choice = UserChoiceField(
        required=False, label='Implementer', help_text='The person who will implement this change')

    def __init__(self, *args, **kwargs):
        super(EmergencyChangeRequestForm, self).__init__(*args, **kwargs)
        self.fields['endorser_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['endorser_choice'].label = 'Endorser email'
        self.fields['implementer_choice'].widget.attrs['class'] = 'select-user-choice'
        self.fields['implementer_choice'].label = 'Implementer email'
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Instructions',
                Div(
                    HTML('<p>Please record as much relevant detail as possible about the emergency change in the fields below.</p><br>'),
                    css_id='div_id_instructions'
                ),
            ),
            Fieldset(
                'Details',
                'title', 'description', 'endorser_choice', 'implementer_choice', 'implementation',
                'planned_start', 'planned_end', 'outage', 'completed', 'it_systems',
            ),
            FormActions(self.save_button),
        )

    class Meta:
        model = ChangeRequest
        fields = [
            'title', 'description', 'implementation', 'planned_start', 'planned_end', 'outage', 'completed', 'it_systems']


class ChangeRequestApprovalForm(forms.Form):
    approve_button = Submit('approve', 'Approve', css_class='btn-lg')
    cancel_button = Submit('cancel', 'Cancel')

    def __init__(self, instance, *args, **kwargs):
        # NOTE: we've added instance to the args above to pretend that this is a ModelForm.
        super(ChangeRequestApprovalForm, self).__init__(*args, **kwargs)
        self.helper = BaseFormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'CAB member instructions',
                Div(
                    HTML('''
                    <p><strong>Please record your approval for this change request to proceed by clicking on the "Approve" button.</strong></p>
                    <p>Do not record approval prior to discussion and assessment being completed.</p>'''),
                    css_id='div_id_instructions'
                ),
            ),
            FormActions(self.approve_button, self.cancel_button),
        )
