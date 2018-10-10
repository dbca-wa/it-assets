from django.views.generic import DetailView
from .models import Incident


class IncidentDetail(DetailView):
    model = Incident
