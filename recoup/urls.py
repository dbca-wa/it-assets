from django.urls import path
from .views import RecoupSummaryView, BillView, DUCReport

urlpatterns = [
    path('', RecoupSummaryView.as_view(), name='recoup_summary'),
    path('bill', BillView.as_view(), name='recoup_bill'),
    path('reports/DUCReport.xlsx', DUCReport, name='recoup_report'),
]
