from django.urls import path
from organisation import views

urlpatterns = [
    path('address-book/', views.AddressBook.as_view(), name='address_book'),
    path('department-user-log/', views.DepartmentUserLogList.as_view(), name='department_user_log_list'),
    path('user-accounts/', views.UserAccounts.as_view(), name='user_accounts'),
    path('user-accounts/export/', views.UserAccountsExport.as_view(), name='user_accounts_export'),
]
