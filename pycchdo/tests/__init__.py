from pyramid import testing

import pycchdo.models as M
from pycchdo.models.models import Person


__all__ = ['global_setUp', 'global_tearDown', '_mock_FieldStorage']


def global_setUp(self):
    """ Setup function to be called by all test classes """
    self.config = testing.setUp()
    M.init_conn({'db_uri': 'mongodb://sui.ucsd.edu:27018/?w=1&fsync=true',
                 'db_name': 'cchdo'})
    M.cchdo().objs.drop()
    M.cchdo().attrs.drop()
    self.testPerson = Person(identifier='testid', name_first='Testing', name_last='Tester')
    self.testPerson.save()


def global_tearDown(self):
    """ Tear down function to be called by all test classes """
    self.testPerson.remove()
    del self.testPerson
    testing.tearDown()


class _mock_FieldStorage:
    def __init__(self, filename, file, contentType):
        self.filename = filename
        self.file = file
        self.type = contentType
