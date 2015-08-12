'''
Useful fields for auditing::

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
import ast
import json
from datetime import datetime
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.timezone import utc, get_current_timezone
#from south.modelsinspector import add_introspection_rules


class UTCCreatedField(models.DateTimeField):
    """
    A DateTimeField that automatically populates itself at
    object creation.

    By default, sets editable=False, default=datetime.utcnow.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        super(UTCCreatedField, self).__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        value = datetime.utcnow().replace(tzinfo=utc)
        setattr(model_instance, self.attname, value)
        return value

#add_introspection_rules([], ["^restless\.fields\.UTCCreatedField"])


class UTCLastModifiedField(UTCCreatedField):
    """
    A DateTimeField that updates itself on each save() of the model.

    By default, sets editable=False and default=datetime.utcnow.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        super(UTCCreatedField, self).__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        value = datetime.utcnow().replace(tzinfo=utc)
        setattr(model_instance, self.attname, value)
        return value

#add_introspection_rules([], ["^restless\.fields\.UTCLastModifiedField"])


def maybe_call(x):
    if callable(x): return x()
    return x


class JSONEncoder(DjangoJSONEncoder):
    '''An extended JSON encoder to handle some additional cases.

    The Django encoder already deals with date/datetime objects.
    Additionally, this encoder uses an 'as_dict' or 'as_list' attribute or
    method of an object, if provided. It also makes lists from QuerySets.
    '''
    def default(self, obj):
        if hasattr(obj, 'as_dict'):
            return maybe_call(obj.as_dict)
        elif hasattr(obj, 'as_list'):
            return maybe_call(obj.as_list)
        elif isinstance(obj, models.query.QuerySet):
            return list(obj)
        return super(JSONEncoder, self).default(obj)


class JSONField(models.TextField):
    """JSONField is a generic textfield that neatly serializes/unserializes
    JSON objects seamlessly"""

    # Used so to_python() is called
    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        """Convert our string value to JSON after we load it from the DB"""

        if value == "":
            return None

        try:
            if isinstance(value, basestring):
                return json.loads(value)
        except ValueError:
            pass

        return value

    def from_python(self, value):
        """Convert our JSON object to a string before we save"""

        if value == "":
            return None

        if isinstance(value, basestring):
            try:
                json.loads(value) #just checks its a valid dict
            except: # handles python string reps
                value = json.dumps(ast.literal_eval(value), cls=JSONEncoder)
        else: #otherwise make whatever it is a string
            value = json.dumps(value, cls=JSONEncoder)

        return value

    def get_db_prep_save(self, value):

        value = self.from_python(value)

        return super(JSONField, self).get_db_prep_save(value)

#add_introspection_rules([], ["^restless\.fields\.JSONField"])
