import datetime

import pymongo
import pymongo.objectid
from pymongo.son_manipulator import SONManipulator

mongo_conn = pymongo.Connection()
cchdo = mongo_conn.cchdo


def timestamp():
    return datetime.datetime.now()


class mongodoc(dict):
    def copy_keys_from(self, o, keys):
        if not o:
            return
        for key in keys:
            try:
                self[key] = o[key]
            except KeyError:
                pass


class collectablemongodoc(mongodoc):
    _mongo_collection = cchdo.collectables

    def from_mongo(self, doc):
        pass

    def save(self):
        self._mongo_collection.save(self)

    def remove(self):
        self._mongo_collection.remove(self['_id'])

    @classmethod
    def map_mongo(cls, cursor):
        return [cls().from_mongo(x) for x in cursor]

    @classmethod
    def all(cls):
        return cls._mongo_collection.find()

    @classmethod
    def find(cls, *args, **kwargs):
        return cls._mongo_collection.find(*args, **kwargs)


class Stamp(mongodoc):
    def __init__(self, person=None):
        self['timestamp'] = timestamp()
        # TODO
        self['person'] = person


class Note(mongodoc):
    def __init__(self, action=None, data_type=None, subject=None, body=None):
        self['action'] = action
        self['data_type'] = data_type
        self['subject'] = subject
        self['body'] = body


class _Change(collectablemongodoc):
    _mongo_collection = cchdo.changes

    def __init__(self, note=None):
        self['creation_stamp'] = Stamp()
        self['pending_stamp'] = None
        self['judgment_stamp'] = None
        self['accepted'] = False
        self['note'] = note

    def from_mongo(self, doc):
        super(_Change, self).from_mongo(doc)
        self.copy_keys_from(doc, ('_id', 'creation_stamp',
                                  'pending_stamp', 'judgment_stamp',
                                  'accepted', 'note', ))
        return self

    def is_judged(self):
        return self['judgment_stamp'] is not None

    def is_acknowledged(self):
        return self['pending_stamp'] is not None

    def is_accepted(self):
        return self.is_judged() and self['accepted']

    def is_rejected(self):
        return self.is_judged() and not self['accepted']

    def accept(self):
        self['judgment_stamp'] = Stamp()
        self['accepted'] = True
        self.save()

    def acknowledge(self):
        if not self['pending_stamp']:
            self['pending_stamp'] = Stamp()
            self.save()
            return True
        else:
            return False

    def reject(self):
        self['judgment_stamp'] = Stamp()
        self['accepted'] = False
        self.save()


class _AttrList(list):
    def __init__(self, L=None):
        if L:
            # TODO
            pass


class Attr(_Change):
    _mongo_collection = cchdo.attrs
    accepted_value = None

    def __init__(self, key=None, value=None, obj=None, note=None,
                 deleted=False):
        super(Attr, self).__init__()
        self['key'] = key
        self['value'] = value
        self['deleted'] = deleted
        self['obj'] = obj
        self['note'] = note

    def from_mongo(self, doc):
        super(Attr, self).from_mongo(doc)
        self.copy_keys_from(doc, ('key', 'value', 'obj', 'note', 'deleted', ))
        return self


class _Attrs(dict):
    def __init__(self, obj):
        self._obj = obj

    def history(self, key=None, **kwargs):
        query = {'obj': self._obj['_id']}
        query.update(**kwargs)
        if key:
            query['key'] = key
        return Attr.find(query)

    @property
    def unacknowledged_changes(self):
        return Attr.map_mongo(Attr.find({
            'obj': self._obj['_id'], 'pending_stamp': None,
            'judgment_stamp': None}).sort(
            'creation_stamp.timestamp', pymongo.DESCENDING))

    @property
    def pending_changes(self):
        return Attr.map_mongo(Attr.find({
            'obj': self._obj['_id'], 'judgment_stamp': None,
            'accepted': False}))

    @property
    def accepted_changes(self):
        return Attr.map_mongo(Attr.find(
            {'obj': self._obj['_id'], 'accepted': True}).sort(
            'judgment_stamp.timestamp', pymongo.DESCENDING))

    def __getitem__(self, key):
        attrs = self.history(key, accepted=True).sort(
            'judgment_stamp.timestamp', pymongo.DESCENDING)
        if attrs.count(True) > 0:
            attr = Attr.map_mongo(attrs.limit(1))[0]
            if attr['deleted']:
                raise KeyError(key)
            return attr['value']
        raise KeyError(key)

    def __setitem__(self, key, value, note=None):
        if type(value) == _AttrList:
            pass
        elif type(value) == list:
            value = _AttrList(value)

        attr = Attr(key, value, self._obj['_id'], note)
        attr.save()

    def __delitem__(self, key, note=None):
        attr = Attr(key, None, self._obj['_id'], note, deleted=True)
        attr.save()


class Obj(_Change):
    _mongo_collection = cchdo.objs

    def __init__(self, doc=None):
        super(Obj, self).__init__(doc)
        self['_obj_type'] = type(self).__name__
        self.copy_keys_from(doc, ('_obj_type', ))

    @property
    def attrs(self):
        try:
            return self['_attrs']
        except KeyError:
            self['_attrs'] = _Attrs(self)
            return self['_attrs']

    def remove(self):
        super(Obj, self).remove()
        for attr in Attr.map_mongo(self.attrs.history()):
            attr.remove()


class Data(Attr):
    pass


class Person(Obj):
    def __init__(self):
        self['obj_type'] = 'person'
        self['name_first'] = None
        self['name_last'] = None
        self['institution'] = None
        self['country'] = None
        self['email'] = None
