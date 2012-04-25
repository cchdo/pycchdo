import unittest

from pyramid.config import Configurator
from pyramid.exceptions import Forbidden
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
        result = data(request)
        self.assertNotEqual(Forbidden, type(result))
        request.user = person

        # No permissions required, has no permissions -> ok
        result = data(request)
        self.assertNotEqual(Forbidden, type(result))

        data_attr.permissions = {
            'read': ['argo', ],
            'write': ['notargo', ],
        }
        data_attr.save()

        # argo group required, no user -> unauthorized
        request.user = None
        result = data(request)
        self.assertEqual(Forbidden, type(result))
        request.user = person

        # argo group required, has no permissions -> unauthorized
        result = data(request)
        self.assertEquals(Forbidden, type(result))

        # argo group required, has argo permission -> ok
        person.permissions = ['argo']
        person.save()
        result = data(request)
        self.assertNotEquals(Forbidden, type(result))
        
        # Staff users have super powers
        # argo group required, has staff permission -> ok
        person.permissions = ['argo']
        person.save()
        result = data(request)
        self.assertNotEquals(Forbidden, type(result))

        data_attr.remove()
        person.remove()
