from django.urls import path
from registers import views

urlpatterns = [
    path('incidents/', views.IncidentList.as_view(), name='incident_list'),
    path('incidents/<int:pk>/', views.IncidentDetail.as_view(), name='incident_detail'),
    path('changerequests/', views.ChangeRequestList.as_view(), name='change_request_list'),
    path('changerequests/<int:pk>/', views.ChangeRequestDetail.as_view(), name='change_request_detail'),
    path('changerequests/<int:pk>/update/', views.ChangeRequestUpdate.as_view(), name='change_request_update'),
    path('changerequests/<int:pk>/approve/', views.ChangeRequestApprove.as_view(), name='change_request_approve'),
    path('changerequests/create/', views.ChangeRequestCreate.as_view(), name='change_request_create'),
    #path('changerequests/calendar/', views.ChangeRequestCalendar.as_view(), name='change_request_calendar'),
]
