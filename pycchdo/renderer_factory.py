import json as JSON
from datetime import datetime, date

from sqlalchemy.ext.associationproxy import _AssociationList

from pycchdo.models import (
    Participants, Participant,
    )


class CustomJSONEncoder(JSON.JSONEncoder):
    """Used by custom pyramid renderer."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        elif isinstance(obj, date):
            return str(obj)
        elif isinstance(obj, Participants):
            return self.default(list(obj))
        elif isinstance(obj, Participant):
            return JSON.dumps({
                'person': obj.person_id,
                'institution': obj.institution_id,
                'role': obj.role})
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
        return unicode(JSON.dumps(value, cls=CustomJSONEncoder))
    return _render
