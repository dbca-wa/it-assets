from django.urls import path
from .views import AddressBook, UserAccounts, OrganisationStructure, NewUserForm, UpdateUserForm, TransferUserForm, DeleteUserForm


urlpatterns = [
    path('address-book/', AddressBook.as_view(), name='km_address_book'),
    path('user-accounts/', UserAccounts.as_view(), name='km_user_accounts'),
    path('organisation-structure/', OrganisationStructure.as_view(), name='km_user_accounts'),
    path('new-user/', NewUserForm.as_view(), name='new_user_form'),
    path('update-user/', UpdateUserForm.as_view(), name='update_user_form'),
    path('transfer-user/', TransferUserForm.as_view(), name='update_user_form'),
    path('delete-user/', DeleteUserForm.as_view(), name='delete_user_form'),
]
