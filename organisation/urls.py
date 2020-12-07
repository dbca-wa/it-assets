from django.urls import path
from organisation import views

urlpatterns = [
    path('user-account/export/', views.UserAccountExport.as_view(), name='user_account_export'),
    path('ascender-discrepancies/export/', views.AscenderDiscrepanciesExport.as_view(), name='ascender_discrepancies_export'),
    path('adaction/', views.ADActionList.as_view(), name='ad_action_list'),
    path('adaction/<int:pk>/', views.ADActionDetail.as_view(), name='ad_action_detail'),
    path('adaction/<int:pk>/complete/', views.ADActionComplete.as_view(), name='ad_action_complete'),
    path('departmentuser/confirm-phone-nos/', views.ConfirmPhoneNos.as_view(), name='confirm_phone_nos'),
]
