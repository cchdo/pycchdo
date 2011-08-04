#XXX 2011-08-01 11:37:33 ayshen
import os

from pyramid.httpexceptions import HTTPNotFound
import pycchdo.models


def by_ocean_index(request):
    """There's no index page for oceans."""
    return HTTPNotFound()


def by_ocean_show(request):
    AllowedBasins = ('arctic', 'atlantic', 'indian', 'pacific', 'southern', )

    basin = request.matchdict['basin']
    if basin.lower() not in AllowedBasins:
        return HTTPNotFound()

    # TODO get the search-by-position API for Cruises and use it here
    results = models.Cruise.all()
    #results = models.Cruise.find_by_position(NotImplemented)
    if not results:
        return HTTPNotFound()

    return results
