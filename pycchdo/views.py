from pyramid.view import view_config

from pycchdo.models import DBSession
from pycchdo.models import MyModel

def my_view(request):
    dbsession = DBSession()
    root = dbsession.query(MyModel).filter(MyModel.name==u'root').first()
    return {'root':root, 'project':'pycchdo'}

def home(request):
    return {'project': 'pycchdo'}
