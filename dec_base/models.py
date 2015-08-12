'''
Models to provide database representation for DEC regions and districts::

    Copyright (C) 2011 Department of Environment & Conservation

    Authors:
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
from __future__ import division, print_function, unicode_literals, absolute_import
import logging
logger = logging.getLogger("log."+__name__)
from django.contrib.gis.db import models
from django.contrib.gis import admin
from restless.abstract2 import Audit, AuditAdmin

class RegionManager(models.Manager):
    '''
    ModelManager class for the Region model type.
    '''
    def current(self):
        return self.filter(effective_to=None)

class RegionAbstract(Audit):
    '''
    Abstract model to represent DEC regions and district areas,
    for use within other corporate Django applications.
    Subclasses the Audit model in restless.abstract2
    '''
    effective_to = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=320, unique=True)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(unique=True, help_text='Must be unique. Automatically generated from name.')
    # Use the custom ModelManager class.
    objects = RegionManager()

    class Meta:
        abstract = True
        ordering = ['name']

    def __unicode__(self):
        return unicode(self.name)

    def delete(self, *args, **kwargs):
        '''
        Overides the standard delete method; sets effective_to as the
        current date and time. The current() method on the model manager
        is used to return a queryset of "undeleted" objects.
        '''
        self.effective_to = datetime.now()
        super(Region, self).save(*args, **kwargs)

class Region(RegionAbstract):
    '''
    Subclass the RegionAbstract model, to represent DEC regions.
    '''
    pass

class District(RegionAbstract):
    '''
    Subclass the RegionAbstract model, to represent DEC districts.
    '''
    region = models.ForeignKey(Region, help_text='The region to which this district belongs.')

class RegionAdmin(AuditAdmin):
    '''
    A ModelAdmin class for the Region and District model types.
    Subclasses the AuditAdmin class in restless.abstract2
    '''
    list_display = ('id','name','slug','modified','effective_to')
    raw_id_fields = ('creator','modifier')
    prepopulated_fields = {'slug':['name']}
    search_fields = ('name','slug','description')

admin.site.register(Region, RegionAdmin)
admin.site.register(District, RegionAdmin)
