from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from .models import Workload


class WorkloadDetail(LoginRequiredMixin, DetailView):
    model = Workload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['page_title'] = 'Workload: {}'.format(obj)
        if hasattr(obj, 'image_scan_json') and obj.image_scan_json:
            context['image_vulns'] = obj.image_scan_json['Vulnerabilities']
        else:
            context['image_vulns'] = []
        return context
