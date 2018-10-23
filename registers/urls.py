from django.urls import path
from .views import IncidentList, IncidentDetail, ChangeRequestDetail, ChangeRequestList, ChangeRequestCreate, ChangeRequestUpdate

urlpatterns = [
    path('incidents/', IncidentList.as_view(), name='incident_list'),
    path('incidents/<int:pk>/', IncidentDetail.as_view(), name='incident_detail'),
    path('changerequests/', ChangeRequestList.as_view(), name='change_request_list'),
    path('changerequests/<int:pk>/', ChangeRequestDetail.as_view(), name='change_request_detail'),
    path('changerequests/<int:pk>/update/', ChangeRequestUpdate.as_view(), name='change_request_update'),
    #path('changerequests/<int:pk>/approve/', ChangeRequestApprove.as_view(), name='change_request_approve'),
    path('changerequests/create/', ChangeRequestCreate.as_view(), name='change_request_create'),
    #path('changerequests/calendar/', ChangeRequestCalendar.as_view(), name='change_request_calendar'),
]
