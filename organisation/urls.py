from django.urls import path, re_path
from organisation import views

urlpatterns = [
    path('user-account/export/', views.UserAccountExport.as_view(), name='user_account_export'),
    path('ad-actions/', views.ADActionList.as_view(), name='ad_action_list'),
    path('ad-actions/<int:pk>/', views.ADActionDetail.as_view(), name='ad_action_detail'),
]
