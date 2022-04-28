from django.urls import path
from organisation import views

urlpatterns = [
    path('address-book/', views.AddressBook.as_view(), name='address_book'),
    path('user-accounts/', views.UserAccounts.as_view(), name='user_accounts'),
    path('user-accounts/export/', views.UserAccountsExport.as_view(), name='user_accounts_export'),
    path('adaction/', views.ADActionList.as_view(), name='ad_action_list'),
    path('adaction/<int:pk>/', views.ADActionDetail.as_view(), name='ad_action_detail'),
    path('adaction/<int:pk>/complete/', views.ADActionComplete.as_view(), name='ad_action_complete'),
    path('departmentuser/sync-issues/', views.SyncIssues.as_view(), name='sync_issues'),
]
