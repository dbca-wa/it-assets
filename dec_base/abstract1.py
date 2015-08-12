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
import os
logger = logging.getLogger("log." + __name__)
from datetime import datetime
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.gis.db import models
from restless.abstract2 import Audit, AuditAdmin, ActiveModelMixin
from unidecode import unidecode


class RegionAbstract(Audit, ActiveModelMixin):
    '''
    Abstract model to represent DEC regions and district areas, for use within other DEC corporate
    applications.
    '''
    name = models.CharField(max_length=320, unique=True)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(unique=True, help_text='Must be unique.')

    class Meta:
        abstract = True
        ordering = ['name']

    def __unicode__(self):
        return unicode(self.name)


class RegionAdmin(AuditAdmin):
    '''
    A ModelAdmin class for the Region and District model types.
    '''
    list_display = ('id', 'name', 'slug', 'modified', 'effective_to')
    raw_id_fields = ('creator', 'modifier')
    prepopulated_fields = {'slug': ['name']}
    search_fields = ('name', 'slug', 'description')


def content_filename(instance, filename):
    '''
    Decode unicode characters in file uploaded to ASCII-equivalents.
    Also replace spaces with underscores.
    '''
    path = 'uploads/{date}/{filename}'
    filename = unidecode(filename).replace(' ', '_')
    d = {'date': datetime.strftime(datetime.today(), '%Y/%m/%d'), 'filename': filename}
    return path.format(**d)


class DocumentAbstract(Audit, ActiveModelMixin):
    '''
    Generic class for supporting documents.
    '''
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    uploaded_file = models.FileField(
        # max_length is maximum full path and filename length:
        max_length=255,
        upload_to=content_filename)
        #upload_to='uploads/%Y/%m/%d')
    description = models.TextField(
        blank=True, null=True, help_text='Name and/or description of the supporting document.')

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(self.pk)

    @property
    def uploaded_file_name(self):
        '''
        Return the filename of the uploaded file, minus the server filepath.
        '''
        try:
            return self.uploaded_file.name.rsplit('/', 1)[-1]
        except:
            # If the file has been deleted/is missing, return a warning.
            return '<missing_file>'

    @property
    def uploaded_file_ext(self):
        '''
        Return the file extension of the uploaded file.
        '''
        try:
            ext = os.path.splitext(self.uploaded_file.name)[1]
            return ext.replace('.', '').upper()
        except:
            # If the file has been deleted/is missing, return an empty string.
            return ''

    @property
    def filesize_str(self):
        '''
        Return the filesize as a nicely human-readable string.
        '''
        try:
            num = self.uploaded_file.size
            for x in ['bytes', 'KB', 'MB', 'GB']:
                if num < 1024.0:
                    return '%3.1f%s' % (num, x)
                num /= 1024.0
        except:
            # If the file has been deleted/is missing, return an empty string.
            return ''
