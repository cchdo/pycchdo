from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPUnauthorized, HTTPNoContent
from pyramid import testing

from . import *
from pycchdo import models


class TestView(BaseTest):
    def test_home_view(self):
        from pycchdo.views.toplevel import home
        request = testing.DummyRequest()
        result = home(request)
        self.assertEqual(result, {'updated': [], 'upcoming': []})

    def test_data_permissions(self):
        """ When accessing data, make sure the session is authorized to see it.

        Data permissions may be specified read or write.

        1. If there are no requirements, the session is authorized
           This includes the case where no user is signed in.
        2. If there are requirements, test if the session is authorized
        3. In addition to the requirements, there are also restrictions on
           accessing data based on its status. If the data is pending or
           unjudged, it may only be accessed by signed in users.

        """
        from pycchdo.views.toplevel import data
        request = testing.DummyRequest()

        person = request.user = models.Person(identifier='person')
        cruise = models.Cruise(person)
        self.session.add(person)
        self.session.add(cruise)

        data_attr = cruise.set_accept(
            'bottle_exchange',
            MockFieldStorage(MockFile('botex', 'bot_hy1.csv'), 'text/csv'),
            person)
        data_attr.permissions = {}

        self.session.flush()

        request.matchdict['data_id'] = data_attr.id

        # No permissions required, no user -> ok
        request.user = None

        try:
            data(request)
        except HTTPNoContent:
            pass
        request.user = person

        # No permissions required, has no permissions -> ok
        try:
            data(request)
        except HTTPNoContent:
            pass

        data_attr.permissions_read = ['argo']
        data_attr.permissions_write = ['notargo']
        self.session.flush()

        # argo group required, no user -> unauthorized
        request.user = None
        with self.assertRaises(HTTPUnauthorized):
            data(request)
        request.user = person

        # argo group required, has no permissions -> unauthorized
        with self.assertRaises(HTTPUnauthorized):
            data(request)

        # argo group required, has argo permission -> ok
        person.permissions = ['argo']
        try:
            data(request)
        except HTTPNoContent:
            pass
        
        # Staff users have super powers
        # argo group required, has staff permission -> ok
        person.permissions = ['staff']
        try:
            data(request)
        except HTTPNoContent:
            pass

        del data_attr.permissions 
        del data_attr.judgment_stamp
        # data is not judged, user -> ok
        try:
            data(request)
        except HTTPNoContent:
            pass

        # data is not judged, no user -> unauthorized
        request.user = None
        with self.assertRaises(HTTPUnauthorized):
            data(request)
