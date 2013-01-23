import json as JSON
import datetime

from sqlalchemy.ext.associationproxy import _AssociationList

from pyramid.response import Response

from pycchdo.models import (
    Obj, Participants, Participant,
    Institution,
    )


class CustomJSONEncoder(JSON.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.date):
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
    def _render(value, system):
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'application/json'
        return unicode(JSON.dumps(value, cls=CustomJSONEncoder))
    return _render
