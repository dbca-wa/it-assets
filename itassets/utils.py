from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from djqscsv import render_to_csv_response
import logging
from msal import ConfidentialClientApplication
import os
import re
from restless.dj import DjangoResource
import subprocess
import simdjson


def ms_graph_client_token():
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["MS_GRAPH_API_CLIENT_ID"]
    client_secret = os.environ["MS_GRAPH_API_CLIENT_SECRET"]
    context = ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority="https://login.microsoftonline.com/{}".format(azure_tenant_id),
    )
    scope = "https://graph.microsoft.com/.default"
    return context.acquire_token_for_client(scope)


class ModelDescMixin(object):
    """A small mixin for the ModelAdmin class to add a description of the model to the
    admin changelist view context.

    In order to then display this description above the list view, you then need to
    override the relevant change_list.html template.
    """

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if hasattr(self, "model_description"):
            extra_context["model_description"] = self.model_description
        return super().changelist_view(request, extra_context=extra_context)


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


class LogRecordIterator(object):
    """
    for azlog dump file
    """
    block_size = 1024 * 512  # Read 512k

    def __init__(self, input_file):
        self._input_file = input_file
        self._f = None
        self._index = None
        self._data_block = None
        self._read = True

    def _close(self):
        try:
            if self._f:
                self._f.close()
        except:
            pass
        finally:
            self._f = None

    first_record_start_re = re.compile("^\s*\[\s*\{\s*\n")
    record_sep_re = re.compile("\n\s*}\s*,\s*{\s*\n")
    last_record_end_re = re.compile("\n\s*}\s*\,?\s*\]\s*$")

    def _next_record(self):
        if not self._f:
            raise StopIteration("No more records")

        while (self._f):
            if self._read:
                data = self._f.read(self.block_size)
                self._read = False
                if data:
                    if self._data_block:
                        self._data_block += data
                    else:
                        self._data_block = data
                else:
                    #end of file
                    self._close()
                    if self._data_block:
                        m = self.last_record_end_re.search(self._data_block)
                        if m:
                            self._index += 1
                            json_str = "{{\n{}\n}}".format(self._data_block[:m.start()])
                            self._data_block = None
                            return simdjson.loads(json_str)
                        else:
                            raise Exception("The last record is incomplete in file({}).".format(self._input_file))
                    else:
                        raise StopIteration("No more records")

            if self._index is None:
                m = self.first_record_start_re.search(self._data_block)
                if m:
                    self._data_block = self._data_block[m.end():]
                    self._index = -1
                elif self._data_block.strip():
                    raise Exception("The file({}) is an invalid json file".format(self._input_file))
                else:
                    self._data_block = None
                    self._read = True
            else:
                m = self.record_sep_re.search(self._data_block)
                if m:
                    self._index += 1
                    json_str = "{{\n{}\n}}".format(self._data_block[:m.start()])
                    self._data_block = self._data_block[m.end():]
                    return simdjson.loads(json_str)
                else:
                    self._read = True

    def __iter__(self):
        self._close()

        self._index = None
        self._data_block = None
        self._read = True

        self._f = open(self._input_file, 'r')
        return self

    def __next__(self):
        return self._next_record()
