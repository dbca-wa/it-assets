from django.urls import path
from .views import IncidentList, IncidentDetail

urlpatterns = [
    path('incidents/', IncidentList.as_view(), name='incident_list'),
    path('incidents/<int:pk>/', IncidentDetail.as_view(), name='incident_detail'),
]
