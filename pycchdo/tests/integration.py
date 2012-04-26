import unittest

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPUnauthorized, HTTPNoContent
from pyramid import testing

from . import *
from pycchdo import models


class TestView(unittest.TestCase):
    setUp = global_setUp
    tearDown = global_tearDown

    def test_home_view(self):
        from pycchdo.views.toplevel import home
        request = testing.DummyRequest()
        result = home(request)
        self.assertEqual(result, {'updated': [], 'upcoming': []})

    def test_data_permissions(self):
        """ When accessing data, make sure the session is authorized to see it.

            1. If there are no requirements, the session is authorized
               This includes the case where no user is signed in.
            2. If there are requirements, test if the session is authorized

        """
        from pycchdo.views.toplevel import data
        request = testing.DummyRequest()

        person = request.user = models.Person('person')
        person.save()

        data_attr = models._Attr(person, None)
        data_attr.permissions = {}
        data_attr.save()
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

        data_attr.permissions = {
            'read': ['argo', ],
            'write': ['notargo', ],
        }
        data_attr.save()

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
        person.save()
        try:
            data(request)
        except HTTPNoContent:
            pass
        
        # Staff users have super powers
        # argo group required, has staff permission -> ok
        person.permissions = ['argo']
        person.save()
        try:
            data(request)
        except HTTPNoContent:
            pass

        data_attr.remove()
        person.remove()
