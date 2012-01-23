from pycchdo.importers import *
import pycchdo.models as models


__all__ = ['_import_Collection', ]


def _import_Collection(importer, name, type):
    """ A Collection also will include a type as part of its identifier to
    differentiate between the fields it came from in the original database.
    """
    collections = models.Collection.get_by_attrs(names=[name], type=type)
    if len(collections) > 0:
        implog.info('Updating Collection %s %s' % (name, type))
        collection = collections[0]
    else:
        implog.info('Creating Collection %s %s' % (name, type))
        collection = models.Collection(importer)
        collection.accept(importer)
        collection.save()
        collection.set_accept('names', [name], importer)
        collection.set_accept('type', type, importer)
    return collection

