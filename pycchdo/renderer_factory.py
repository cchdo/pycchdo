import json as JSON
import datetime

from pyramid.response import Response

from pycchdo.models import Obj


class CustomJSONEncoder(JSON.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return str(obj)
        elif isinstance(obj, datetime.date):
            return str(obj)
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
