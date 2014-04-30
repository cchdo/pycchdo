import json as JSON
from decimal import Decimal
from datetime import datetime, date

from sqlalchemy.ext.associationproxy import _AssociationList

from pycchdo.models.serial import (
    Participants, Participant, Parameter,
    )


class CustomJSONEncoder(JSON.JSONEncoder):
    """Used by custom pyramid renderer.

    This is where you define how to convert objects to JSON representations.

    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        elif isinstance(obj, date):
            return str(obj)
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, Participants):
            return self.default(list(obj))
        elif isinstance(obj, Participant):
            return JSON.dumps({
                'person': obj.person_id,
                'institution': obj.institution_id,
                'role': obj.role})
        elif isinstance(obj, Parameter):
            parameter = obj
            response = {'parameter': {
                'name': parameter.get('name', ''),
                'aliases': filter(None,
                    [parameter.get('name_netcdf'),
                     parameter.get('full_name')] + parameter.aliases),
                'format': parameter.get('format', ''),
                'bounds': map(unicode, parameter.bounds),
                },
                'description': parameter.get('description', None),
            }
            units = parameter.units
            if units:
                response['parameter']['units'] = {
                    'unit': {
                        'def': units.get('name'),
                        'aliases': [
                            {'name': {'singular': units.get('mnemonic')}}
                        ]
                    }
                }
            return response
        elif isinstance(obj, list):
            return JSON.dumps([self.default(x) for x in obj])
        elif isinstance(obj, str) or isinstance(obj, unicode):
            return obj
        elif isinstance(obj, _AssociationList):
            return ''
            # TODO stale proxy?
            #return JSON.dumps([self.default(x) for x in obj])
        return JSON.JSONEncoder.default(self, obj)


def json(info):
    """Return a pyramid renderer for json."""
    def _render(value, system):
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'application/json'
        return unicode(
            JSON.dumps(value, cls=CustomJSONEncoder, ensure_ascii=False))
    return _render
