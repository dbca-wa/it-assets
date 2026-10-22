from django.contrib import admin

DROPDOWN_TEMPLATE = 'admin/dropdown_filter.html'

class DropdownFilterAllValues(admin.AllValuesFieldListFilter):
    template = DROPDOWN_TEMPLATE

class DropdownFilterRelatedOnly(admin.RelatedOnlyFieldListFilter):
    template = DROPDOWN_TEMPLATE

class DropdownFilterRelated(admin.RelatedFieldListFilter):
    template = DROPDOWN_TEMPLATE

class DropdownFilterChoices(admin.ChoicesFieldListFilter):  
    template = DROPDOWN_TEMPLATE

class DropdownFilterBoolean(admin.BooleanFieldListFilter):  
    template = DROPDOWN_TEMPLATE
