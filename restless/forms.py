'''
Models for restless to store app links & tests::

    Copyright (C) 2011 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe
     * Ashley Felton

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
#Python3 compatibility
from __future__ import division, print_function, unicode_literals, absolute_import

import re

from django.conf import settings
from django.utils.http import urlencode
from django.utils import simplejson as json
from django.utils.safestring import mark_safe

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import floppyforms as forms

from restless.models import ApplicationLink, shorthash

GEDEFAULTS = {
    "showcontents":"false",
    "width":800,
    "height":400
}

def retrieve_access_token(request, service):
    '''Returns serviceurl, access_token for a service and request.
    Service should be a string representing a service to connect to.
    System will introspect settings.SITE_NAME to find service.
    Probably issues if more than one link, will default to using latest modified.
    '''
    applink = ApplicationLink.objects.get(server_name=service)
    serviceurl = applink.server_url
    access_token = applink.get_access_token(request.user.username)
    return serviceurl, access_token

class BaseFormHelper(FormHelper):
    '''
    A crispy_forms FormHelper class consisting of Save and Cancel submit buttons.
    '''
    def __init__(self, *args, **kwargs):
        super(BaseFormHelper, self).__init__(*args, **kwargs)
        self.form_class = 'form-horizontal'
        self.form_method = 'POST'
        self.help_text_inline = True
        save_button = Submit('save','Save')
        save_button.field_classes = 'btn-primary btn-large'
        self.add_input(save_button)
        cancel_button = Submit('cancel','Cancel')
        self.add_input(cancel_button)

class BaseAuditForm(forms.ModelForm):
    '''
    A basic ModelForm meant to be used by any model type that inherits from Audit and/or
    ActiveModelMixin. It uses the BaseFormHelper and excludes the audit fields from the rendered
    form.
    Note that you can use this as the basis for other model types - the Meta class exclude will
    fail silently if a named field does not exist on that model.
    '''
    def __init__(self, *args, **kwargs):
        self.helper = BaseFormHelper()
        super(BaseAuditForm, self).__init__(*args, **kwargs)

    class Meta:
        model = None
        # Exclude fields from the Audit and ActiveModelMixin abstract models.
        exclude = ['created', 'modified', 'creator', 'modifier', 'effective_from', 'effective_to']

class GoldenEyeWidget(forms.Textarea):
    def __init__(self, request, instance=None, options={"mode":"polygoncapture"}, *args, **kwargs):
        self.request = request
        self.instance = instance
        self.options = GEDEFAULTS
        self.options.update(options)
        super(GoldenEyeWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        serviceurl, access_token = retrieve_access_token(self.request, "goldeneye")
        self.options["access_token"] = access_token
        self.options["spatial"] = "textarea#id_" + name
        urlparams = urlencode(self.options)
        output = u'''
            <link rel="stylesheet" href="{2}/api/geoserver/v1/static/geoserver.css" type="text/css" />
            <script src="{2}/api/geoserver/v1/static/geoserver.js"></script>
            <script src="{2}/api/geoserver/v1/workspaces/{3}.js?{4}"></script>
            <textarea id="id_{0}" name="{0}" style="display:none;">{1}</textarea>
            <div id="{0}" class="goldeneye-widget" style="float:left;"></div>
            <script type="text/javascript">
                $(function() {{
                    new GoldenEye.SpatialView("{0}");
                }});
            </script>
            <div style="clear:both;"></div>
        '''.format(name, value, serviceurl, self.instance, urlparams).strip()
        return mark_safe(output)

class GoldenEyeWidget2(forms.Textarea):
    request = None
    instance = 'public'
    showcontents = 'false'
    mode = 'viewer'
    width = 800
    height = 400
    features = [] # Can be a list of objects, or a queryset.
    geom_field = None # A string; the name of the geometry field of the passed-in features.
    html_info = ''
    unique_id = shorthash(html_info)
    service = 'goldeneye'

    def __init__(self, request, instance=None, showcontents=None, mode=None, width=None,
            height=None, features=None, html_info=None, service=None, *args, **kwargs):
        self.request = request
        if instance: self.instance = instance
        if showcontents: self.showcontents = showcontents
        if mode: self.mode = mode
        if width: self.width = width
        if height: self.height = height
        if features: self.features = features
        if html_info: self.html_info = html_info
        if service: self.service = service
        self.serviceurl, self.access_token = retrieve_access_token(request, self.service)
        super(GoldenEyeWidget2, self).__init__(*args, **kwargs)

    def get_context(self, *args, **kwargs):
        context = super(GoldenEyeWidget, self).get_context(*args, **kwargs)
        context["ge_api"] = "//ge-dev.dec.wa.gov.au/api/geoserver/v1"
        context["strew_api"] = "//ge-dev.dec.wa.gov.au/api/strew/v1"
        return context

    def features_json(self):
        '''Returns the geometries of passed-in features as a GeoJSON FeatureCollection.
        '''
        if self.features:
            features_json = []
            for feature in self.features:
                if getattr(feature, self.geom_field):
                    features_json.append({
                       "type":"Feature",
                       "id":feature.pk,
                       "properties":{"html_info":self.html_info.format(feature)},
                       "geometry": json.loads(getattr(feature, self.geom_field).json)
                    })
            return json.dumps({"type":"FeatureCollection","features":features_json})
        else:
            return None

    def url_params(self):
        '''Returns widget parameters as URL-encoded output.
        '''
        options = {
            'showcontents':self.showcontents,
            'width':self.width,
            'height':self.height,
            'access_token':self.access_token,
            'mode':self.mode
        }
        return urlencode(options)

    def render(self, name, value, attrs=None):
        output = u'''
            <link rel="stylesheet" href="{0}/api/geoserver/v1/static/geoserver.css" type="text/css" />
            <script src="{0}/api/geoserver/v1/static/geoserver.js"></script>
            <script src="{0}/api/geoserver/v1/workspaces/{1}.js?{2}"></script>
            <textarea id="id_{3}" name="{3}" style="display:none;">{4}</textarea>
            <div id="{3}" style="float:left;"></div>
            <script type="text/javascript">
                $(function() {{
                    new GoldenEye.SpatialView("{3}");
                }});
            </script>
            <div style="clear:both;"></div>
        '''
        output = output.format(self.serviceurl, self.instance, self.url_params(),
            name, value).strip()
        return mark_safe(output)

#class GoldenEyeForm(forms.Form):
#    request = None
#    the_geom = forms.CharField(widget=GoldenEyeWidget(request=request))
#    template_name = 'restless/goldeneye_input.html'

def GoldenEyeViewer(request, features=[], geom_field="shape", instance="cc/instances/public", html_info=None):
    serviceurl, access_token = retrieve_access_token(request, "goldeneye")
    uniqueid = shorthash(html_info)
    options = GEDEFAULTS
    options["spatial"] = "textarea#features_{0}".format(uniqueid)
    options["access_token"] = access_token
    options["mode"] = "viewer"
    html_info = re.sub(r"([^{]){([^{])", r"\1{0.\2", html_info)
    featuresjson = []
    for feature in features:
        if getattr(feature, geom_field):
            featuresjson.append({
               "type": "Feature",
               "id": feature.pk,
               "properties": { "html_info": html_info.format(feature) },
               "geometry": json.loads(getattr(feature, geom_field).json)
            })
    featuresjson = json.dumps({"type":"FeatureCollection","features":featuresjson})
    urlparams = urlencode(options)
    output = u'''
    <link rel="stylesheet" href="{0}/api/geoserver/v1/static/geoserver.css" type="text/css" />
    <script src="{0}/api/geoserver/v1/static/geoserver.js"></script>
    <script src="{0}/api/geoserver/v1/workspaces/{1}.js?{2}"></script>
    <textarea id="features_{4}" style="display:none;">{3}</textarea>
    <div id="{4}" class="goldeneye-viewer-widget" style="float:left;"></div>
    <script type="text/javascript">
        $(function() {{
        new GoldenEye.SpatialView("{4}");
    }});
    </script>
    <div style="clear:both;"></div>
    '''.format(serviceurl, instance, urlparams, featuresjson, uniqueid).strip()
    return mark_safe(output)

