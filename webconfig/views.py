from django.shortcuts import render
from django.views.generic.base import TemplateView

from webconfig.models import Site


class ConfigRenderView(TemplateView):
    template_name = 'nginx.conf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sites'] = Site.objects.all()
        return context
