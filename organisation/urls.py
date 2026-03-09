from django.urls import path

from organisation import views

urlpatterns = [
    path("address-book/", views.AddressBook.as_view(), name="address_book"),
    path("user-accounts/", views.UserAccounts.as_view(), name="user_accounts"),
    path("user-accounts/admin/", views.UserAccounts.as_view(admin_view=True), name="user_accounts_admin"),
]
