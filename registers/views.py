from django.views.generic import TemplateView

class ChangeRequestView(TemplateView):
    template_name = 'changerequest.html'

class ChangeRequestDetailView(TemplateView):
    template_name = 'changerequestdetail.html'

class ChangeRequestListView(TemplateView):
    template_name = 'changerequestlist.html'