from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
import json
from .models import Workload


class WorkloadDetail(LoginRequiredMixin, DetailView):
    model = Workload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['page_title'] = 'Workload: {}'.format(obj)
        if obj.image_scan_json:
            context['image_scan_json'] = json.dumps(obj.image_scan_json, indent=2)
        else:
            context['image_scan_json'] = ''
        return context
