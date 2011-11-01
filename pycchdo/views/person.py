from pyramid.httpexceptions import HTTPNotFound

import pycchdo.models as models


def people_index(request):
    return {'people': models.Person.get_all()}


def person_show(request):
    coll_id = request.matchdict.get('person_id')
    person = models.Person.get_id(coll_id)
    if not person:
        return HTTPNotFound()
    return {'person': person}
