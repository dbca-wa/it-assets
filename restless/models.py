'''
Models for restless to store app links & tests::

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

import binascii
import struct
import hashlib
import requests
import time

from reversion import revision
from taggit.managers import TaggableManager
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import slugify

from restless.fields import JSONField
from restless.abstract2 import models, Audit, AuditAdmin, get_locals, UTCLastModifiedField

from model_utils import Choices

def shorthash(obj):
    return slugify(binascii.b2a_base64(struct.pack('l', hash(obj)))[:-2])

class Job(models.Model):
    STATES = Choices("queued", "running", "completed")
    name = models.CharField(max_length=320, unique=True)
    args = models.TextField(null=True, blank=True)
    output = models.TextField(null=True, blank=True)
    state = models.CharField(choices=STATES, default=STATES.queued, max_length=64)

class Role(Audit):
    name = models.CharField(max_length=320, unique=True)
    description = models.TextField(null=True, blank=True)

    def natural_key(self):
        return (self.name, )
    def get_by_natural_key(self, name):
        return self.get(name=name)

class RoleLink(Audit):
    '''
    Attaches roles to a user using middleware
    '''
    role = models.ForeignKey(Role, help_text="Role to automatically append to users/groups (uses restless middleware)")
    users = models.ManyToManyField(User, blank=True)
    groups = models.ManyToManyField(Group, blank=True)
    anonymous = models.BooleanField(default=False, help_text="Do all anonymous users belong to this role?")
    authenticated = models.BooleanField(default=False, help_text="Do all authenticated users belong to this role?")

    class admin_config(Audit.admin_config):
        filter_horizontal = ('users', 'groups')

    def __unicode__(self):
        return unicode('Role:{0}, anon:{1}, auth:{2}'.format(self.role.name, self.anonymous, self.authenticated))

class ContentPermission(Audit):
    '''
    Role based permission for a content type
    '''
    PERMISSIONS = Choices("add", "read", "read_created", "read_modified", "change", "change_created", "change_modified", "delete", "delete_created", "delete_modified")
    name = models.CharField(choices=PERMISSIONS, default=PERMISSIONS.read, max_length=64)
    role = models.ManyToManyField(Role, blank=True)
    content = models.ForeignKey(ContentType, help_text="Content this permission applies to")

    def natural_key(self):
        return (self.name, self.content.natural_key())
    natural_key.dependencies = ['contenttypes.contenttype']
    def get_by_natural_key(self, name, contenttype):
        return self.get(name=name, content=ContentType.get_by_natural_key(contenttype))

    class Meta:
        unique_together = ("name", "content")

    class admin_config(Audit.admin_config):
        filter_horizontal = ('role', )

    def __unicode__(self):
        return unicode('Content type:{0}, permission:{1}'.format(self.content, self.name))

class Permission(Audit):
    '''
    Role based permission for an object, make sure model has "permission" attribute
    otherwise will always return true
    use abstract2's audit base class to get
    a has_permission function
    '''
    PERMISSIONS = Choices("read", "change", "delete")
    name = models.CharField(choices=PERMISSIONS, default=PERMISSIONS.read, max_length=64)
    role = models.ForeignKey(Role)

    def natural_key(self):
        return (self.name, self.role.natural_key())
    natural_key.dependencies = ['restless.role']
    def get_by_natural_key(self, name, role):
        return self.get(name=name, role=Role.get_by_natural_key(role))

    class Meta:
        unique_together = ("name", "role")

    def __unicode__(self):
        return "{0}({1})".format(self.role.name, self.name)

def get_roles(user):
    '''
    Gets a users roles or returns already retrieved roles
    '''
    if hasattr(user, "roles"):
        return user.roles
    try:
        user.roles = set(Role.objects.filter(
                    Q(rolelink__authenticated = True) |
                    Q(rolelink__users = user) |
                    Q(rolelink__groups__in = user.groups.all())
                ).distinct()
            )
    except TypeError:
        user.roles = set(Role.objects.filter(rolelink__anonymous = True).distinct())
    return user.roles

def get_permissions(user, obj=None):
    '''
    gets a users content permissions
    or permissions for a specific object
    '''
    if obj:
        get_roles(user)
        return obj.get_permissions(user)
    else:
        return set(ContentPermission.objects.filter(role__in = get_roles(user)))

def has_permission(content, permission, user):
    '''
    Checks role based permission for content
    returns queryset of content user has access to
    or true if user has access to single content object
    or false if user has no access
    '''
    # Short-circuit: if the user.is_superuser() returns True, they are an
    # admininstrator.
    if user.is_superuser:
        return True
    get_roles(user)
    modelclass, modelinstance = False, False
    if isinstance(content, Audit):
        modelinstance = content
        content = ContentType.objects.get_for_model(content)
        modelclass = content.model_class()
    elif issubclass(content, Audit):
        modelclass = content
        content = ContentType.objects.get_for_model(content)
    elif isinstance(content, ContentType):
        modelclass = content.model_class()
    else:
        raise ValueError("Please pass a ContentType, Object or ModelClass for the content parameter")
    if not ContentPermission.objects.filter(content=content, name__startswith = permission).exists() and hasattr(modelinstance, "permissions"):
        '''
        check individual object permissions if no
        content permissions
        '''
        if not modelinstance:
            # return queryset of objects with permission
            return modelclass.objects.filter(permissions__role__in = get_roles(user), permissions__name=permission).distinct()
        if modelinstance.permissions.count() == 0:
            return False
        if modelinstance.permissions.filter(role__in = get_roles(user), name=permission).exists():
            return True
        return False
    permissions = ContentPermission.objects.filter(content=content, role__in = get_roles(user), name__startswith = permission)
    if permissions.filter(name = permission).exists():
        if modelinstance:
            return modelclass.objects.filter(pk=modelinstance.pk).exists()
        return modelclass.objects.all()
    query = Q()
    if permissions.filter(name = permission + "_created").exists():
        query = query | Q(creator = user)
    if permissions.filter(name = permission + "_modified").exists():
        query = query | Q(modifier = user)
    if query:
        # uses extra queryset to get instance permissions as well as overall permissions
        try:
            extra = modelclass.objects.filter(permissions__role__in = get_roles(user), permissions__name=permission)
        except Exception as e:
            print(e)
            extra = False
        if extra:
            results = modelclass.objects.filter(query) | extra
        else:
            results = modelclass.objects.filter(query)
        if modelinstance:
            return results.filter(pk=modelinstance.pk).exists()
        return results.distinct()
    else:
        if not modelinstance and hasattr(modelclass, "permissions"):
            # return queryset of objects with permission
            return modelclass.objects.filter(permissions__role__in = get_roles(user), permissions__name=permission).distinct()
        return False

class ApplicationLink(Audit):
    AUTH_METHOD = Choices('basic', 'md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512')
    client_name = models.CharField(max_length=320, help_text="project/host of client, this app is {0}".format(settings.SITE_NAME))
    server_name = models.CharField(max_length=320, help_text="project/host of server, this app is {0}".format(settings.SITE_NAME))
    server_url = models.TextField(help_text="URL service backend requests should be made to")
    identifier = models.CharField(max_length=320, help_text="IP or Hostname, optional for added security (unimplemented)", null=True, blank=True)
    secret = models.CharField(max_length=320, help_text="Application Secret")
    timeout = models.IntegerField(default=600, help_text="Timeout of oauth tokens in seconds")
    auth_method = models.CharField(choices=AUTH_METHOD, default=AUTH_METHOD.sha256, max_length=20)

    def natural_key(self):
        return (self.client_name, self.server_name)
    def get_by_natural_key(self, client_name, server_name):
        return self.get(client_name=client_name, server_name=server_name)

    def get_access_token(self, username, expires=600):
        '''
        expires is in seconds
        '''
        url = self.server_url + "/api/restless/v1/{0}/request_token".format(self.server_name)
        nonce = int(time.time())
        client_secret = self.get_client_secret(username, nonce)
        r = requests.get(url, params= {
            "user_id": username,
            "nonce": nonce,
            "client_secret": client_secret,
            "client_id": self.client_name,
            "expires": expires })
        if r.ok:
            return r.content
        else:
            print(r.content)
            r.raise_for_status()

    def get_client_secret(self, userid, nonce):
        # concat client secret, username, nonce and hash, and check matches client hash (client_secret in request)
        stringtohash = "{0}{1}{2}".format(self.secret, userid, nonce)
        # client_secret should be hexdigest, hash algorithm selected based on applink
        return getattr(hashlib, self.auth_method)(stringtohash).hexdigest()

    class Meta(Audit.Meta):
        unique_together = ("client_name", "server_name")


class Token(models.Model):
    link = models.ForeignKey(ApplicationLink)
    user = models.ForeignKey(User, help_text="User token authenticates as")
    url = models.TextField(help_text="Suburl this token is restricted to, relative e.g. (/my/single/service/entrypoint)", default="/")
    secret = models.CharField(max_length=320, help_text="Token Secret", unique=True)
    modified = UTCLastModifiedField(editable=False)
    timeout = models.IntegerField(default=600, help_text="Timeout token in seconds, 0 means never times out")


    def save(self, *args, **kwargs):
        try:
            revision.unregister(self.__class__)
        except:
            pass
        super(Token, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.secret)
    def get_by_natural_key(self, secret):
        return self.get(secret=secret)


    def __unicode__(self):
        return "{0} - {1}:{2}@{3}".format(self.pk, self.user, self.secret, self.link.client_name)[:320]
