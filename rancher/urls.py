from django.urls import path
from rancher import views

urlpatterns = [
    path('workload/<int:pk>/', views.WorkloadDetail.as_view(), name='workload_detail'),
]
