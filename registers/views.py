from django.views.generic import ListView, DetailView
from .models import Incident


class IncidentList(ListView):
    paginate_by = 20

    def get_queryset(self):
        # By default, return ongoing incidents only.
        if 'all' in self.request.GET:
            return Incident.objects.all()
        return Incident.objects.filter(resolution__isnull=True)


class IncidentDetail(DetailView):
    model = Incident
