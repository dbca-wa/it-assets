from django.urls import path
from .views import IncidentList, IncidentDetail, ChangeRequestDetail, ChangeRequestList, ChangeRequestCreate

urlpatterns = [
    path('incidents/', IncidentList.as_view(), name='incident_list'),
    path('incidents/<int:pk>/', IncidentDetail.as_view(), name='incident_detail'),
    path('changerequests/', ChangeRequestList.as_view(), name='change_request_list'),
    path('changerequests/<int:pk>/', ChangeRequestDetail.as_view(), name='change_request_detail'),
    path('changerequests/create/', ChangeRequestCreate.as_view(), name='change_request_create'),
]
