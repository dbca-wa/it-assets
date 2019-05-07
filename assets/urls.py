from django.urls import path, re_path
from assets import views

urlpatterns = [
    path('hardwareasset/', views.HardwareAssetList.as_view(), name='hardware_asset_list'),
    path('hardwareasset/<int:pk>/', views.HardwareAssetDetail.as_view(), name='hardware_asset_detail'),
    path('hardwareasset/export/', views.HardwareAssetExport.as_view(), name='hardware_asset_export')
]
