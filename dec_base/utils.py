#Python3 compatibility
from __future__ import division, print_function, unicode_literals, absolute_import
import re
import string
import time
import gc
import logging
import inspect
from django.contrib.auth.models import User
from django.contrib import admin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django_auth_ldap.backend import LDAPBackend, _LDAPUser
from taggit.models import Tag
from taggit.utils import parse_tags
from HTMLParser import HTMLParser


def timedcall(fn, *args):
    '''Call function with args; return the time in seconds and results.'''
    t0 = time.clock()
    result = fn(*args)
    t1 = time.clock()
    return t1 - t0, result


def queryset_iterator(queryset, chunksize=1000):
    '''
    Iterate over a Django Queryset ordered by the primary key
    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.
    Note that the implementation of the iterator does not support ordered query sets.
    '''
    pk = 0
    last_pk = queryset.order_by('-pk')[0].pk
    queryset = queryset.order_by('pk')
    while pk < last_pk:
        for row in queryset.filter(pk__gt=pk)[:chunksize]:
            pk = row.pk
            yield row
        gc.collect()


def breadcrumb_trail(links, sep = ' > '):
    '''
    ``links`` must be a list of two-item tuples in the format (URL, Text).
    URL may be None, in which case the trail will contain the Text only.
    Returns a string of HTML.
    '''
    trail = ''
    url_str = '<a href="{0}">{1}</a>'
    # Iterate over the list, except for the last item.
    for i in links[:-1]:
        if i[0]:
            trail += url_str.format(i[0], i[1]) + sep
        else:
            trail += i[1] + sep
    # Add the list item on the list to the trail.
    if links[-1][0]:
        trail += url_str.format(links[-1][0], links[-1][1])
    else:
        trail += links[-1][1]
    return trail

def breadcrumbs_bootstrap(links, sep=' > '):
    '''
    '''
    trail = ''
    url_str = '<a href="{0}">{1}</a>'
    sep_str = '<span class="divider">{0}</span>'
    # Iterate over the list, except for the last item.
    for i in links[:-1]:
        if i[0]:
            trail += url_str.format(i[0], i[1]) + sep_str.format(sep)
        else:
            trail += i[1] + sep_str.format(sep)
    # Add the list item on the list to the trail.
    if links[-1][0]:
        trail += url_str.format(links[-1][0], links[-1][1])
    else:
        trail += links[-1][1]
    return trail

def add_contentious_tag(request, obj, tag_field='tags', tags=None, redirect_url='#'):
    '''
    '''
    try:
        obj_manager = getattr(obj, tag_field)
        tags = parse_tags(tags)
        for tag in tags:
            obj_manager.add(tag)
    except:
        # Called with an object that doesn't use tags?
        pass
    return redirect(redirect_url)

def remove_tag_from_object(request, model, object_id, tag_id):
    '''
    Removes a single tag from the specified object.
    '''
    obj = get_object_or_404(model, pk=object_id)
    # Called with an object that doesn't use tags? Redirect to get_absolute_url().
    if not hasattr(obj, tag_field):
        return redirect(obj.get_absolute_url())
    tag = Tag.objects.get(id=tag_id)
    obj.tags.remove(tag)
    return redirect(obj.get_absolute_url())

def sanitise_filename(f):
    '''
    Take a string, and return it without special characters, and spaces replaced by underscores.
    '''
    valid_chars = '-_. {0}{1}'.format(string.letters, string.digits)
    f = ''.join(c for c in f if c in valid_chars)
    return f.replace(' ', '_')

def smart_truncate(content, length=100, suffix='...(more)'):
    '''
    Small function to truncate a string in a sensible way, sourced from:
    http://stackoverflow.com/questions/250357/smart-truncate-in-python
    '''
    if len(content) <= length:
        return content
    else:
        return ' '.join(content[:length+1].split(' ')[0:-1]) + suffix


def get_or_create_local_user(username):
    '''Create a local user if the username exists in the configured LDAP server.
    Returns the updated or newly created local django.contrib.auth.models.User
    '''
    # instantiate the LDAPBackend model class
    # magically finds the LDAP server from settings.py
    ldap_backend = LDAPBackend()

    if len(User.objects.filter(username=username)) < 1:
        # if the user does not exist locally, create:
        ldap_backend.populate_user(username)
        # now the user exists locally

    # get the local user object
    local_user_object = User.objects.get(username=username)
    # using the Django user's id, get the ldap_user
    ldap_user_object = ldap_backend.get_user(local_user_object.id)
    return local_user_object

def get_local_user_by_email(email):
    '''Get a username from AD from an email address
    '''
    #Get the LDAPBackend and connection
    ldap_backend = LDAPBackend()
    ldap_user = _LDAPUser(ldap_backend, username="")

    return ldap_user.connection.search_s("dc=corporateict,dc=domain", scope=ldap_backend.ldap.SCOPE_SUBTREE,
            filterstr='(mail=' + email + ')',
            attrlist=[str("sAMAccountName").encode('ASCII')])[0][1]["sAMAccountName"][0].lower()

def normalise_query(query_string, findterms=re.compile(r'"([^"]+)"|(\S+)').findall, normspace=re.compile(r'\s{2,}').sub):
    '''
    Splits the query string in invidual keywords, getting rid of unecessary spaces
    and grouping quoted words together.

    Example:

    >>> normalise_query('  some random  words "with   quotes  " and   spaces')
    >>> ['some', 'random', 'words', 'with quotes', 'and', 'spaces']
    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]

def get_query(query_string, search_fields):
    '''
    Returns a query which is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.
    '''
    query = None # Query to search for every search term
    terms = normalise_query(query_string)
    for term in terms:
        or_query = None # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query

def filter_queryset(search_string, model, queryset):
    '''
    Function to dynamically filter a model queryset, based upon the search_fields defined in
    admin.py for that model. If search_fields is not defined, the queryset is returned unchanged.
    '''
    # Replace single-quotes with double-quotes
    search_string = search_string.replace("'",r'"')
    if admin.site._registry[model].search_fields:
        search_fields = admin.site._registry[model].search_fields
        entry_query = get_query(search_string, search_fields)
        queryset = queryset.filter(entry_query)
    return queryset


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_html_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def log_view(request):
    '''
    Function to log the current view and user.
    '''
    logger = logging.getLogger('view_stats')
    # Get the previous frame in the stack, otherwise it would be this function!
    func = inspect.currentframe().f_back.f_code
    # Dump the message + the name of this function to the log.
    if request.user.is_anonymous():
        logger.info('{{"username":"anonymous", "view":"{0}", "path":"{1}"}}'.format(func.co_name, request.path))
    else:
        logger.info('{{"username":"{0}", "view":"{1}", "path":"{2}"}}'.format(request.user.username, func.co_name, request.path))


def label_span(text, label_class=None):
    '''
    Return a Bootstrap span class for inline-labelled text.
    Pass in a valid Bootstrap label class as a string, if required.
    '''
    if label_class in ['success', 'warning', 'important', 'info', 'inverse']:
        return '<span class="label label-{0}">{1}</span>'.format(label_class, text)
    else:
        return '<span class="label">{0}</span>'.format(text)
