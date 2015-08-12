'''
Models and Forms and main classes to inherit::

    Copyright (C) 2011 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe

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
from __future__ import division, print_function, unicode_literals, absolute_import
import logging
logger = logging.getLogger("log."+__name__)

import threading
from datetime import datetime

from django.contrib.auth.models import User
from django.contrib.gis.admin import ModelAdmin
from django.contrib.gis.db import models
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.timezone import utc

import reversion
from reversion.admin import VersionAdmin
from model_utils.managers import QueryManager
from restless.fields import UTCCreatedField, UTCLastModifiedField
from restless.utils import transform_geom

_locals = threading.local()


def get_locals():
    '''
    Setup locals for a request thread so we can attach stuff and make it available globally
    import from request.models::
        from request.models import get_locals
        _locals = get_locals
        _locals.request.user = amazing
    '''
    return _locals


class AuditAdmin(VersionAdmin, ModelAdmin):
    search_fields = ['id', 'creator__username', 'modifier__username', 'creator__email',
        'modifier__email']
    list_display = ['__unicode__', 'creator', 'modifier', 'created', 'modified']
    raw_id_fields = ['creator', 'modifier']


class Audit(models.Model):
    class Meta:
        abstract = True

    creator = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_created', editable=False)
    modifier = models.ForeignKey(User, related_name='%(app_label)s_%(class)s_modified', editable=False)
    created = UTCCreatedField()
    modified = UTCLastModifiedField()

    def __init__(self, *args, **kwargs):
        super(Audit, self).__init__(*args, **kwargs)
        # Initialise any existing model with a dictionary (prev_values), to keep track of any changes on save().
        if self.pk:
            fieldnames = self._meta.get_all_field_names()
            self._fieldnames = set(fieldnames + [f + "_id" for f in fieldnames]).intersection(set(self.__dict__.keys()))
            self._initvalues = set([k for k in self.__dict__.iteritems() if k[0] in self._fieldnames])
        else:
            pass

    def save(self, *args, **kwargs):
        '''
        This falls back on using an admin user if a thread request object wasn't found
        '''
        if not hasattr(_locals, "request") or _locals.request.user.is_anonymous():
            if hasattr(_locals, "user"):
                user = _locals.user
            else:
                user = User.objects.get(id=1)
                _locals.user = user
        else:
            user = _locals.request.user
        # If creating a new model, set the creator.
        if not self.pk:
            self.creator = user
        self.modifier = user
        super(Audit, self).save(*args, **kwargs)
        # If the model has existing values, test if any values are being changed.
        # Old values can be accessed through self.prev_values
        change_list = []
        if hasattr(self, '_initvalues'):
            currentvalues = set([k for k in self.__dict__.iteritems() if k[0] in self._fieldnames])
            change_list = self._initvalues - currentvalues
        # Modified and modifier always change; filter these from the list.
        change_list = [item for item in change_list if item[0] not in ['modified','modifier_id']]
        if change_list:
            comment_changed = 'Changed ' + ', '.join([t[0] for t in change_list]) + '.'
            with reversion.create_revision():
                reversion.set_comment(comment_changed)
        elif not change_list and not self.pk:
            with reversion.create_revision():
                reversion.set_comment('Initial version.')
        else:
            # An existing object was saved, with no changes: don't create a revision.
            with reversion.create_revision():
                reversion.set_comment('Nothing changed.')

    def _searchfields(self):
        return set(field.name for field in self.__class__._meta.fields)

    def __unicode__(self):
        fields = ""
        for field in self._searchfields().difference(set(['created', 'modified', 'creator', 'modifier', 'id'])):
            fields += "{0}: {1}, ".format(field, repr(getattr(self, field)))
        return "{0} - {1}".format(self.pk, fields)[:320]

    class admin_config(AuditAdmin):
        search_fields = ['id', 'creator__username', 'modifier__username', 'creator__email',
            'modifier__email']
        list_display = ['__unicode__', 'creator', 'modifier', 'created', 'modified']

    def get_absolute_url(self):
        return reverse('{0}_detail'.format(self._meta.object_name.lower()), kwargs={'pk':self.pk})


class PolygonModelMixin(models.Model):
    """
    Model mixin to provide a polygon field called the_geom having the default SRID of 4326 (WGS84).
    """
    the_geom = models.PolygonField(blank=True, null=True, verbose_name='the_geom')

    class Meta:
        abstract = True

    def area_ha(self):
        """
        Returns the area of the polygon field in hectares, transformed to a projection of
        GDA94/MGA zone 49 through 56.
        """
        if self.the_geom:
            return transform_geom(self.the_geom).area/10000
        else:
            return None

    def perim_m(self):
        '''
        Returns the perimeter of the polygon field in metres, transformed to a projection of
        GDA94/MGA zone 49 through 56.
        '''
        if self.the_geom:
            return transform_geom(self.the_geom).boundary.length
        else:
            return None


class LineStringModelMixin(models.Model):
    """
    Model mixin to provide a linestring spatial field called the_geom having the default SRID
    of 4326 (WGS84).
    """
    the_geom = models.LineStringField(blank=True, null=True, verbose_name='the_geom')

    class Meta:
        abstract = True


class PointModelMixin(models.Model):
    """
    Model mixin to provide a point spatial field called the_geom having the default SRID
    of 4326 (WGS84).
    """
    the_geom = models.PointField(blank=True, null=True, verbose_name='the_geom')

    class Meta:
        abstract = True


class ActiveModelManager(models.GeoManager):
    '''
    Manager Class for the ActiveModelMixin class.
    These Manager methods are useful in Django templates, where you can call:
    {% for m in model.childmodel_set.active %}
        ...
    {% endfor %}
    '''
    def active(self):
        return self.filter(effective_to=None) # Allows: MyModel.objects.active()

    def deleted(self):
        return self.filter(effective_to__isnull=False) # Allows: MyModel.objects.deleted()


class ActiveModelMixin(models.Model):
    '''
    Model mixin to allow objects to be saved as 'non-current' or 'inactive', instead of deleting
    those objects.
    The standard model delete() method is overridden, note that this does not override the Django
    Admin "delete" action (which calls Queryset.delete()). You need to write a custom action to
    prevent models from being 'properly' deleted in the Admin interface.
    "effective_from" allows 'past' and/or 'future' objects to be saved.
    "effective_to" is used to 'delete' objects (null==not deleted).
    '''
    effective_from = models.DateTimeField(default=datetime.utcnow().replace(tzinfo=utc))
    effective_to = models.DateTimeField(null=True, blank=True)
    objects = ActiveModelManager()
    active = QueryManager(effective_to=None) # Allows: MyModel.active.all()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        '''
        Overides the standard model delete method; sets "effective_to" as the current date and time
        and then calls save() instead.
        '''
        self.effective_to = datetime.utcnow().replace(tzinfo=utc)
        super(ActiveModelMixin, self).save(*args, **kwargs)

    def as_th(self):
        '''
        Returns a string of HTML that renders the model field names inside HTML <th> elements.
        '''
        html = ''
        for f in self._meta.fields:
            html += '<th>{0}</th>'.format(f.verbose_name)
        return mark_safe(html)

    def as_td(self):
        '''
        Returns a string of HTML that renders the object field values inside HTML <td> elements.
        '''
        html = ''
        for f in self._meta.fields:
            html += '<td>{0}</td>'.format(f.value_to_string(self))
        return mark_safe(html)

    def as_table(self):
        '''
        Returns a string of HTML that renders the object details inside an HTML <table> element.
        '''
        html = '<table class="table table-bordered">'
        #<tr><td class="bold">ID</td><td>$id</td></tr>
        for f in self._meta.fields:
            html += '<tr><th>{0}</th><td>{1}</td></tr>'.format(f.verbose_name, f.value_to_string(self))
        html += '</table>'
        return mark_safe(html)
