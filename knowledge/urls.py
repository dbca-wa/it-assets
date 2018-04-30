from __future__ import unicode_literals, absolute_import
from django.conf.urls import url
from .views import AddressBook, UserAccounts, NewUserForm, UpdateUserForm, TransferUserForm, DeleteUserForm


urlpatterns = [
    url(r'^address-book/', AddressBook.as_view(), name='km_address_book'),
    url(r'^user-accounts/', UserAccounts.as_view(), name='km_user_accounts'),
    url(r'^new-user/', NewUserForm.as_view(), name='new_user_form'),
    url(r'^update-user/', UpdateUserForm.as_view(), name='update_user_form'),
    url(r'^transfer-user/', TransferUserForm.as_view(), name='update_user_form'),
    url(r'^delete-user/', DeleteUserForm.as_view(), name='delete_user_form'),
]
