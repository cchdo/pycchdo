from pyramid import testing
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPUnauthorized, HTTPNoContent

from pycchdo.tests import RequestBaseTest, MockFieldStorage, MockFile
from pycchdo.models.serial import DBSession, Cruise, Person, FSFile


class ViewIntegrationTests(RequestBaseTest):
    def setUp(self):
        """This sets up the application registry with the registrations your
        application declares in its ``includeme`` function.

        """
        super(ViewIntegrationTests, self).setUp()
        self.config = testing.setUp()
#        self.config.include('pycchdo.home')

    def tearDown(self):
        """Clear out the application registry."""
        super(ViewIntegrationTests, self).tearDown()
        testing.tearDown()

    def test_empty_login_redirects(self):
        from pycchdo.views import session
        pass

    def test_data_permissions(self):
        """When accessing data, make sure the session is authorized to see it.

        Data permissions may be specified read or write.

        1. If there are no requirements, the session is authorized
           This includes the case where no user is signed in.
        2. If there are requirements, test if the session is authorized
        3. In addition to the requirements, there are also restrictions on
           accessing data based on its status. If the data is pending or
           unjudged, it may only be accessed by signed in users.

        """
        from pycchdo.views.toplevel import data
        person = self.request.user = Person.create().obj
        person.set_id_names(identifier=u'person')

        cruise = Cruise.create(person).obj
        data_attr = cruise.set(
            person, u'bottle_exchange',
            FSFile.from_fieldstorage(
                MockFieldStorage(MockFile('botex', 'bot_hy1.csv'), 'text/csv')))
        data_attr.permissions = {}
        DBSession.flush()

        self.request.matchdict['data_id'] = 'c{0}'.format(data_attr.id)

        # No permissions required, no user -> ok
        self.request.user = None

        try:
            data(self.request)
        except HTTPNoContent:
            pass
        self.request.user = person

        # No permissions required, has no permissions -> ok
        try:
            data(self.request)
        except HTTPNoContent:
            pass

        data_attr.permissions_read = [u'argo']
        data_attr.permissions_write = [u'notargo']
        DBSession.flush()

        # argo group required, no user -> unauthorized
        self.request.user = None
        with self.assertRaises(HTTPUnauthorized):
            data(self.request)
        self.request.user = person

        # argo group required, has no permissions -> unauthorized
        with self.assertRaises(HTTPUnauthorized):
            data(self.request)

        # argo group required, has argo permission -> ok
        person.permissions = [u'argo']
        try:
            data(self.request)
        except HTTPNoContent:
            pass
        
        # Staff users have super powers
        # argo group required, has staff permission -> ok
        person.permissions = [u'staff']
        try:
            data(self.request)
        except HTTPNoContent:
            pass

        del data_attr.permissions 
        del data_attr.ts_j
        # data is not judged, user -> ok
        try:
            data(self.request)
        except HTTPNoContent:
            pass

        # data is not judged, no user -> unauthorized
        self.request.user = None
        with self.assertRaises(HTTPUnauthorized):
            data(self.request)
