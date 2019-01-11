from django.urls import path, re_path
from registers import views

urlpatterns = [
    path('itsystem/export/', views.ITSystemExport.as_view(), name='itsystem_export'),
    path('incident/', views.IncidentList.as_view(), name='incident_list'),
    path('incident/<int:pk>/', views.IncidentDetail.as_view(), name='incident_detail'),
    path('changerequest/', views.ChangeRequestList.as_view(), name='change_request_list'),
    path('changerequest/<int:pk>/', views.ChangeRequestDetail.as_view(), name='change_request_detail'),
    path('changerequest/<int:pk>/update/', views.ChangeRequestUpdate.as_view(), name='change_request_update'),
    path('changerequest/<int:pk>/endorse/', views.ChangeRequestEndorse.as_view(), name='change_request_endorse'),
    path('changerequest/<int:pk>/complete/', views.ChangeRequestComplete.as_view(), name='change_request_complete'),
    path('changerequest/create/', views.ChangeRequestCreate.as_view(), name='change_request_create'),
    path('changerequest/create/standard/', views.ChangeRequestCreate.as_view(), name='std_change_request_create', kwargs={'std': True}),
    path('changerequest/calendar/', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
    re_path('^changerequest/calendar/(?P<date>\d{4}-\d{2}-\d{2})/$', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
]
