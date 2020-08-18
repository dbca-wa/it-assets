from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from djqscsv import render_to_csv_response
import logging
import re
from restless.dj import DjangoResource
import subprocess


def logger_setup(name):
    # Ensure that the logs dir is present.
    subprocess.check_call(['mkdir', '-p', 'logs'])
    # Set up logging in a standardised way.
    logger = logging.getLogger(name)
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:  # Log at a higher level when not in debug mode.
        logger.setLevel(logging.INFO)
    if not len(logger.handlers):  # Avoid creating duplicate handlers.
        fh = logging.handlers.RotatingFileHandler(
            'logs/{}.log'.format(name), maxBytes=5 * 1024 * 1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def breadcrumbs_list(links):
    """Returns a list of links to render as breadcrumbs inside a <ul> element in a HTML template.
    ``links`` should be a iterable of tuples (URL, text).
    """
    crumbs = ""
    li_str = '<li class="breadcrumb-item"><a href="{}">{}</a></li>'
    li_str_active = '<li class="breadcrumb-item active"><span>{}</span></li>'
    # Iterate over the list, except for the last item.
    if len(links) > 1:
        for i in links[:-1]:
            crumbs += li_str.format(i[0], i[1])
    # Add the final "active" item.
    crumbs += li_str_active.format(links[-1][1])
    return crumbs


def get_query(query_string, search_fields):
    """Returns a query which is a combination of Q objects. That combination
    aims to search keywords within a model by testing the given search fields.

    Splits the query string into individual keywords, getting rid of unecessary
    spaces and grouping quoted words together.
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r"\s{2,}").sub
    query = None  # Query to search for every search term
    terms = [normspace(" ", (t[0] or t[1]).strip()) for t in findterms(query_string)]
    for term in terms:
        or_query = None  # Query to search for a given term in each field
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


class CSVDjangoResource(DjangoResource):
    """Extend the restless DjangoResource class to add a CSV export endpoint.
    """
    @classmethod
    def as_csv(self, request):
        resource = self()
        if not hasattr(resource, "list_qs"):
            return HttpResponse(
                "list_qs not implemented for {}".format(self.__name__))
        resource.request = request
        return render_to_csv_response(
            resource.list_qs(), field_order=resource.VALUES_ARGS)


class FieldsFormatter(object):
    """
    A formatter object to format specified fields with a configured formatter
    object. This takes a
        ``request`` parameter , a http request object
        ``formatters`` parameter: a dictionary of keys (a dotted lookup path to
        the desired attribute/key on the object) and values(a formatter object).

    For properties without a configured formatter method, return the raw value
    directly.

    This method will replace the old value with formatted value.

    Example::
        preparer = FieldsFormatter(request, fields={
            # ``user`` is the key the client will see.
            # ``author.pk`` is the dotted path lookup ``FieldsPreparer``
            # will traverse on the data to return a value.
            'photo': format_fileField,
        })
    """
    def __init__(self, formatters):
        super(FieldsFormatter, self).__init__()
        self._formatters = formatters

    def format(self, request, data):
        """
        format data with configured formatter object
        data can be a list or a single object
        """
        if data:
            if isinstance(data, list):
                # list object
                for row in data:
                    self.format_object(request, row)
            else:
                # a single object
                self.format_object(request, data)

        return data

    def format_object(self, request, data):
        """
        format a simgle object.

        Uses the ``lookup_data`` method to traverse dotted paths.

        Replace the value with formatted value, if required.

        """
        if not self._formatters:
            # No fields specified. Serialize everything.
            return data

        for lookup, formatter in self._formatters.items():
            if not formatter:
                continue
            data = self.format_data(request, lookup, data, formatter)

        return data

    def format_data(self, request, lookup, data, formatter):
        """
        Given a lookup string, attempts to descend through nested data looking for
        the value ,format the value and then replace the old value with formatted value.

        Can work with either dictionary-alikes or objects (or any combination of
        those).

        Lookups should be a string. If it is a dotted path, it will be split on
        ``.`` & it will traverse through to find the final value. If not, it will
        simply attempt to find either a key or attribute of that name & return it.

        Example::

            >>> data = {
            ...     'type': 'message',
            ...     'greeting': {
            ...         'en': 'hello',
            ...         'fr': 'bonjour',
            ...         'es': 'hola',
            ...     },
            ...     'person': Person(
            ...         name='daniel'
            ...     )
            ... }
            >>> lookup_data('type', data)
            'message'
            >>> lookup_data('greeting.en', data)
            'hello'
            >>> lookup_data('person.name', data)
            'daniel'

        """
        parts = lookup.split('.')

        if not parts or not parts[0]:
            return formatter(request, data)

        part = parts[0]
        remaining_lookup = '.'.join(parts[1:])

        if hasattr(data, 'keys') and hasattr(data, '__getitem__'):
            # Dictionary enough for us.
            try:
                value = data[part]
                if remaining_lookup:
                    # is an object
                    self.format_data(
                        request, remaining_lookup, value, formatter)
                else:
                    # is a simple type value
                    data[part] = formatter(request, value)
            except:
                # format failed, ignore
                pass
        else:
            try:
                value = getattr(data, part)
                # Assume it's an object.
                if remaining_lookup:
                    # is an object
                    self.format_data(
                        request, remaining_lookup, value, formatter)
                else:
                    # is a simple type value
                    setattr(data, part, formatter(request, value))
            except:
                # format failed, ignore
                pass

        return data
