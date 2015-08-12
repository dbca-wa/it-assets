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

from __future__ import print_function
import hashlib
from decimal import Decimal

# Standard model imports
from django.db import transaction, IntegrityError
from uni_form.helpers import FormHelper, Button
from django.contrib.auth.models import User
from django import forms
from django.utils.safestring import mark_safe
# GIS model imports
from django.contrib.gis import admin
from django.contrib.gis.db import models
# Standard libraries
from datetime import datetime, timedelta, date, time
from django.template.loader import render_to_string
from string import Template

from django.utils import simplejson as json
from django.conf import settings

from restless.fields import UTCCreatedField, UTCLastModifiedField, JSONField, JSONEncoder

try:
    import cPickle as pickle
except ImportError:
    import pickle

# Errors

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class AuditError(Error):
    """Exception raised for errors in Audit

    Attributes:
        value -- explanation of the error
    """

    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class AuditCollision(AuditError):
    pass

class SelectAutoComplete(forms.Select):
    '''
    Needs jquery UI, jLinq
    '''
    def render(self, name, value, attrs=None, choices=(), label = None):
        if hasattr(self, "initial"):
            value = self.initial
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        final_attrs["size"] = 4
        output = [u'<input%s />' % forms.util.flatatt(final_attrs)]
        choiceArray = []
        for val, lbl in self.choices:
            choiceArray.append({"label":lbl, "value":val})
            if val == value:
                label = lbl
        if len(choiceArray) > 200:
            delay, minLength = 500, 4
        else:
            delay, minLength = 100, 1
        output.append(u'''
            <label for="{1[id]}-lbl">{5}</label>
            <script type="text/javascript">
                $("input#{1[id]}").autocomplete({{
                    source: {0},
                    delay: {3},
                    select: function(event, ui) {{
                        $("label[for={1[id]}-lbl]").text(ui.item.label)
                    }},
                    minLength: {4}
                }}).val({2})
            </script>
        '''.format(json.dumps(choiceArray).replace("&", "&amp;"), final_attrs, value, delay, minLength, label))
        return mark_safe(u'\n'.join(output))

class AuditManager(models.GeoManager):
    '''
    For versioning (in Audit) and naturalkey functions
    must override natural key funcs with appropriate
    unique constraints
    '''
    def get_by_natural_key(self, effective_to):
        return self.get(effective_to = effective_to)

    def natural_key_set(self, effective_to):
        return self.filter()
    
    def current(self):
        return self.filter(effective_to = None)

class Audit(models.Model):
    '''
    Contains the effective_from, effective_to,
    visible_from and visible_to fields.
    Used by other tables to enable historical data entry.
    Contains the date_created and date_modified fields.
    Used by other tables to Display datetime information.
    Uses lots of natural keys, requires:
        natural_key()
        _default_manager.get_by_natural_key()
        _default_manager.natural_key_set()
    '''
    created_by = models.ForeignKey(
        User, default=1,
        related_name='%(app_label)s_%(class)s_created', 
        db_index=True)
    date_created = UTCCreatedField(db_index=True)
    modified_by = models.ForeignKey(
        User, default=1,
        related_name='%(app_label)s_%(class)s_modified', 
        db_index=True)
    date_modified = UTCLastModifiedField(db_index=True)
    effective_from = models.DateTimeField(db_index=True)
    effective_to = models.DateTimeField(db_index=True, null=True, blank=True)

    @transaction.commit_manually
    def fix_versions(self):
        nkey = self.natural_key()
        versions = self._default_manager.natural_key_set(*nkey)
        resetnone = False
        if len(versions.filter(effective_to = None)) > 1:
            print("multiple active records, trying to adjust effective_to's")
            resetnone = True
        if len(versions.filter(effective_from = self.effective_from)) > 1:
            print([v.pk for v in versions])
        for version in versions:
            if version.effective_to != None and version.effective_from > version.effective_to:
                print(version.effective_to - version.effective_from)
                version.effective_to = version.effective_from
                version.save()
                transaction.commit()
            if resetnone and version.effective_to == None:
                fixed = False
                hop = 1
                while not fixed:
                    try:
                        version.effective_to = version.get_version(version.effective_from, "next")
                        version.save()
                        fixed = True
                    except:
                        transaction.rollback()
                        try:
                            version.effective_from += timedelta(seconds=hop)
                            version.effective_to = version.get_version(version.effective_from, "next")
                            version.save()
                            fixed = True
                        except Exception, e:
                            transaction.rollback()
                            hop += 1
                            print(`e`, hop)
        transaction.commit()
        print('.', end="")

    def get_version(self, fromdate = None, todate = None):
        '''
        gets latest version of itself (single object)
        specials = ["all", "oldest", "newest")
        if fromdate passed gets version valid for that date (single object)
        if todate passed, gets queryset of version valid between fromdate and todate
        '''
        nkey = self.natural_key()
        versions = self._default_manager.natural_key_set(*nkey)
        if fromdate == "all":
            return versions
        if fromdate == "oldest":
            return versions.order_by("effective_from")[0]
        if fromdate == "newest":
            return versions.latest("effective_from")
        if isinstance(fromdate, datetime):
            if todate == "next":
                return versions.filter(effective_from__gt = fromdate).order_by("effective_from")[0]
            if isinstance(todate, datetime):
                history = versions.filter(effective_from__lte = fromdate, effective_to__gt = todate)
                latest = versions.filter(effective_from__lte = fromdate, effective_to = None)
                return history | latest
            latest = versions.latest("effective_from")
            if latest.effective_from < fromdate and latest.effective_to is None:
                return latest
            else:
                return versions.get(effective_from__lte = fromdate, effective_to__gt = fromdate)
        if fromdate is None and todate is None:
            try:
                return versions.get(effective_to = None)
            except:
                if versions.filter(effective_to = None):
                    raise AuditError(
                        "oh no multiple active versions detected\n"
                        "please run object.fix_versions()\n"
                        "{0}".format(nkey)
                    )
                else:
                    raise
        raise AuditError("bad input, args: " + unicode(fromdate) + ', ' + unicode(todate))
       
    def compare(self, other):
        '''
        Compares self to another object using fields minus the audit fields
        '''
        same = True
        ignorefields = ['effective_from', 'effective_to', 
            'created_by', 'modified_by', 'date_modified', 
            'date_created', 'id']
        for field in self.__class__._meta.fields:
            if field.name not in ignorefields:
                other_value = getattr(other, field.name)
                try:
                    self_value = getattr(self, field.name)
                except field.rel.to.DoesNotExist: # catches one2one relationships that don't exist yet
                    test = True
                else:
                    if isinstance(other_value, dict): # if its a json field handle specially
                        jf = JSONField()
                        test = (other_value == jf.to_python(jf.from_python(self_value)))
                    else:
                        test = (self_value == other_value)
                if not test:
                    same = False
                    break
        return same

    def insert_version_after(self, previous, user):
        '''
        inserts a record after the given record
        using user to set modified on previous
        '''
        self.effective_to = None
        if not isinstance(previous.effective_to, datetime):
            pass
        elif previous.effective_to < self.effective_from:
            if self.natural_key() == previous.natural_key(): 
                raise AuditError("duplicate natural key: ".format(self.natural_key()))
            self.clear_cache()
            self.save()
            return
        else:
            try:
                # if theres another record, use its effective from
                next = self.get_version(self.effective_from, "next")
                if next != previous:
                    self.effective_to = next.effective_from
            except IndexError: pass
        # adjust previous effective_to
        previous.end_version(self.effective_from, user)
        if self.natural_key() == previous.natural_key(): 
            raise AuditError("duplicate natural key: {0}".format(self.natural_key()))
        self.clear_cache()
        self.save()
        return

    @transaction.commit_on_success
    def save_version(self, user = None, effective_to = None, validate = True):
        '''
        If effective from is none, makes new instance
        or ends and adds an updated instance
        Otherwise inserts record into the timestream
        at point defined by effective_from

        >>> item = Association()
        >>> item.save()
        '''
        # invalidate id
        self.id = None
        self.effective_to = effective_to 
        if user:
            self.created_by = user
            self.modified_by = user

        now = self.effective_from or datetime.utcnow()

        # if effective_to, skip checks and just insert record
        # used for bulk loading records quickly
        # won't catch duplicate data but constraints
        # will catch identical records
        if self.effective_to and self.effective_from:
            self.clear_cache()
            self.save()
            return

        # insert between or create record if effective_from
        if self.effective_from:
            try:
                # retrieve version to insert after
                previous = self.get_version(self.effective_from)
            except self.DoesNotExist:
                previous = False
                # inserting first record
                try: 
                    self.effective_to = self.get_version(self.effective_from, "next").effective_from
                except IndexError: pass
            else:
                if validate:
                    if self.compare(previous):
                        self = previous
                        raise AuditCollision(unicode(previous) + ", " + unicode(self))
                self.insert_version_after(previous, user)
                return
          
        # try to get active record(s)
        try:
            active = self.get_version()
        except self.DoesNotExist:
            active = False

        if active and self.effective_to is None:
            if self.compare(active):
                raise AuditCollision(unicode(active) + ", " + unicode(self))
            active.end_version(now, user)
            if self.natural_key() == active.natural_key(): 
                raise AuditError("duplicate natural key: {0}".format(self.natural_key()))

        # add fields for new record
        self.effective_from = self.effective_from or now
        self.clear_cache()
        try:
            self.save()
        except IntegrityError, e:
            raise AuditCollision(unicode(e))
        return

    @transaction.commit_on_success
    def end_version(self, effective_to = None, user = None):
        effective_to = effective_to or datetime.utcnow()
        self.effective_to = effective_to
        if user:
            self.modified_by = user
        self.clear_cache()
        try:
            self.save()
        except IntegrityError, e:
            raise AuditCollision(unicode(e))
        return

    def tags_str(self):
        '''
        uses django-tagging
        '''
        # need to hide hidden tags
        return "".join("{0.name}, ".format(t) for t in self.tags)

    @transaction.commit_on_success
    def replace_tags(self, tags, user = None):
        '''
        tags can be space or comma separated
        checks tags are different
        ends current object
        creates new version
        assigns tags from tags string
        '''
        same_tags = True
        for tag in tags.split(","):
            tag = tag.strip()
            if tag and not self.tags.filter(name=tag.strip()):
                same_tags = False
        if same_tags:
            raise AuditCollision("same tags for {0}: {1}".format(self.pk, self.tags_str()))
        self.end_version(user = user)
        self.effective_from = None
        self.save_version(user = user)
        self.tags = tags
        return

    def append_tags(self, tags, user = None):
        '''
        tags must be comma separated
        extends existing objects tags with tags string
        calls replace_tags to create new version
        '''
        tags = self.tags_str() + tags
        self.replace_tags(tags, user = user)

    def natural_key_str(self):
        return json.dumps(self.natural_key(), cls=JSONEncoder)

    def as_dict(self):
        return self.natural_key_str()

    def sha1(self):
        '''
        unique hash for a version set of audit object
        '''
        return hashlib.sha1(json.dumps(self.natural_key()[1:], cls=JSONEncoder)).hexdigest()

    def clear_cache(self):
        cache.set(self.sha1(), None, 0)

    def __unicode__(self):
        return unicode(self.pk) + ":" + self.natural_key_str()

    class Meta:
            abstract = True

class LookupManager(AuditManager):
    '''
    For saveversion, getby (in Audit) and naturalkey functions
    '''
    def get_by_natural_key(self, effective_to, name):
        return self.get(effective_to = effective_to, name = name)

    def natural_key_set(self, effective_to, name):
        return self.filter(name = name)

class Lookup(Audit):
    name = models.CharField(max_length = 200, null=True, blank=True)
    description = models.CharField(max_length = 200)

    sort_field = 'description'
    headers = ['Name', 'Description', 'Effective From']
    objects = LookupManager()

    def as_td(self):
        template = Template('''
            <td><a href="$id/">$name</a></td>
            <td>$description</td>
            <td>$effective_from</td>
        ''')
        dict = self.__dict__
        dict['effective_from'] = self.effective_from.strftime("%d-%b-%Y")
        result = template.substitute(dict)
        return result
 

    def natural_key(self):
        return [self.effective_to, self.name]

    def __unicode__(self):
            return u"%s" % (self.description)

    class Meta:
        abstract = True
        unique_together = (("effective_from", "name"),
            ("effective_to", "name"))

class BaseForm(forms.ModelForm):
    '''
    Base form/modelform that can be used to make forms.
    Inherits from Audit model by default, excludes
    audit fields (so is a blank form). Javascripty
    
    Usage::
    
        class Form(BaseForm):
            class Meta(BaseForm.Meta):
                model = MyModel

        class Form(BaseForm):
            pass
    '''
    helper = FormHelper()

    # add in a submit and reset button
    submit = Button('Save','Save your changes')
    helper.add_input(submit)
    reset = Button('Cancel','Discard your changes')
    helper.add_input(reset)

    def update(self):
        self.helper.form_id = self.__class__.__name__
        self.helper.form_class = self.Meta.model._meta.app_label

    def as_html(self):
        return render_to_string('form.html', { 'form': self })

    def as_taconite(self, selector):
        return render_to_string('taconite_form.html', { 'jqueryselector': selector, 'form': self })

    class Meta:
        model = Audit
        exclude = ['effective_from','effective_to','created_by','modified_by']

# Messaging models.
def dict_fallback(self):
    return self.__dict__

User.as_dict = dict_fallback
