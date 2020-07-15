from django.urls import path, re_path
from registers import views

urlpatterns = [
    path('itsystem/export/', views.ITSystemExport.as_view(), name='itsystem_export'),
    path('itsystem/platform/export/', views.ITSystemPlatformExport.as_view(), name='itsystem_platform_export'),
    path('itsystem/discrepancy-report/', views.ITSystemDiscrepancyReport.as_view(), name='itsystem_discrepancy_report'),
    path('itsystem/risk-assessment/', views.ITSystemRiskAssessmentList.as_view(), name='itsystem_risk_assessment_list'),
    path('changerequest/', views.ChangeRequestList.as_view(), name='change_request_list'),
    path('changerequest/<int:pk>/', views.ChangeRequestDetail.as_view(), name='change_request_detail'),
    path('changerequest/<int:pk>/change/', views.ChangeRequestChange.as_view(), name='change_request_change'),
    path('changerequest/<int:pk>/endorse/', views.ChangeRequestEndorse.as_view(), name='change_request_endorse'),
    path('changerequest/<int:pk>/approval/', views.ChangeRequestApproval.as_view(), name='change_request_approval'),
    path('changerequest/<int:pk>/complete/', views.ChangeRequestComplete.as_view(), name='change_request_complete'),
    path('changerequest/add/', views.ChangeRequestCreate.as_view(), name='change_request_create'),
    path('changerequest/create/', views.ChangeRequestCreate.as_view(), name='change_request_create'),
    path('changerequest/create-standard/', views.ChangeRequestCreate.as_view(), name='std_change_request_create', kwargs={'std': True}),
    path('changerequest/create-emergency/', views.ChangeRequestCreate.as_view(), name='emerg_change_request_create', kwargs={'emerg': True}),
    path('changerequest/calendar/', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
    re_path('^changerequest/calendar/(?P<date>\d{4}-\d{1,2}-\d{1,2})/$', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
    re_path('^changerequest/calendar/(?P<date>\d{4}-\d{1,2})/$', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
    path('changerequest/export/', views.ChangeRequestExport.as_view(), name='change_request_export'),
    path('standardchange/', views.StandardChangeList.as_view(), name='standard_change_list'),
    path('standardchange/<int:pk>/', views.StandardChangeDetail.as_view(), name='standard_change_detail'),
]
