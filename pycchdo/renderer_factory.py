import json as JSON
from json import JSONEncoder
from decimal import Decimal
from datetime import datetime, date

from sqlalchemy.ext.associationproxy import _AssociationList

from pycchdo.models.serial import (
    Participants, Participant, Parameter,
    )


class CustomJSONEncoder(JSONEncoder):
    """Used by custom pyramid renderer.

    This is where you define how to convert objects to JSON representations.

    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        elif isinstance(obj, date):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif (  isinstance(obj, Participants) or
                isinstance(obj, Participant) or
                isinstance(obj, Parameter)):
            return obj.to_dict()
        elif isinstance(obj, str) or isinstance(obj, unicode):
            return obj
        elif (  isinstance(obj, _AssociationList) or
                isinstance(obj, list)):
            return [self.default(x) for x in obj]
        return JSONEncoder.default(self, obj)


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
