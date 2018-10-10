from django.urls import path
from .views import IncidentDetail

urlpatterns = [
    path('incidents/<int:pk>/', IncidentDetail.as_view(), name='incident_detail'),
]
