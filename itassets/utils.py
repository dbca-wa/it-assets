from django.http import HttpResponse
from djqscsv import render_to_csv_response
from restless.dj import DjangoResource


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
