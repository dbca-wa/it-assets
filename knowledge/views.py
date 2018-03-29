from __future__ import unicode_literals, absolute_import
from django.views.generic import TemplateView


class AddressBook(TemplateView):
    template_name = 'knowledge/address_book.html'


class UserAccounts(TemplateView):
    template_name = 'knowledge/user_accounts.html'


class NewUserForm(TemplateView):
    template_name = 'knowledge/new_user.html'


class UpdateUserForm(TemplateView):
    template_name = 'knowledge/update_user.html'


class TransferUserForm(TemplateView):
    template_name = 'knowledge/transfer_user.html'


class DeleteUserForm(TemplateView):
    template_name = 'knowledge/delete_user.html'
