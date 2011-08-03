""" Indexing/search capabilities

Theoretically the index should be updated each time some object or note is
edited or removed. Fully indexing is also supported.
"""
import os
import logging

from whoosh import index
from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, DATETIME
from whoosh.writing import BufferedWriter
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup

import triggers
import models


logging.basicConfig(level=logging.NOTSET)


# Not Windows compatible
_index_root = '/var/cache'


_index_dir = os.path.join(_index_root, 'pycchdo_search_index')


_index_dir_checked_exists = False


_name_model = {
    'cruise': models.Cruise,
    'person': models.Person,
    'ship': models.Ship,
    'country': models.Country,
    'institution': models.Institution,
    'collection': models.Collection,
    'note': models.Attr,
}


_schemas = {
    'cruise': Schema(
        names=KEYWORD(lowercase=True),
        date_start=DATETIME,
        date_end=DATETIME,
        status=KEYWORD(lowercase=True),
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'person': Schema(
        name=TEXT,
        email=TEXT,
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'ship': Schema(
        name=TEXT,
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'country': Schema(
        names=KEYWORD(lowercase=True),
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'institution': Schema(
        name=TEXT,
        uri=TEXT,
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'collection': Schema(
        names=KEYWORD(lowercase=True),
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
    'note': Schema(
        body=TEXT,
        action=TEXT,
        data_type=TEXT,
        summary=TEXT,
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
}


def _ensure_index_dir():
    global _index_dir_checked_exists
    if _index_dir_checked_exists:
        return
    try:
        os.makedirs(_index_dir)
        _index_dir_checked_exists = True
    except os.error, e:
        # Ignore if existing
        if not os.path.isdir(_index_dir):
            logging.critical(
                'Ensure that %s is writeable by you.' % _index_dir)
            raise e
        else:
            _index_dir_checked_exists = True


def open_or_create_index(name, force_create=False):
    """ Opens or creates and opens an index in the main directory. """
    if not force_create and index.exists_in(_index_dir, indexname=name):
        ix = index.open_dir(_index_dir, indexname=name)
    else:
        try:
            ix = index.create_in(_index_dir, _schemas[name], indexname=name)
        except KeyError:
            raise ValueError('Invalid index name %s' % name)
    return ix


def ensure_index(name):
    open_or_create_index(name).close()


def ensure_indices():
    try:
        os.makedirs(_index_dir)
        os.chmod(_index_dir, 0700)
    except OSError:
        pass
    except IOError, e:
        print "Unable to access/create search index"
        raise e

    for name in _schemas.keys():
        ensure_index(name)


_model_id_to_index_id = unicode


def save_obj(obj, writer=None):
    name = obj.type.lower()
    if not writer:
        ix = open_or_create_index(name)
        ixw = ix.writer()
    else:
        ixw = writer

    doc = {}

    if name == 'cruise':
        names = filter(None, [obj.expocode()] + obj.attrs.get('aliases', []))
        doc['names'] = ','.join(names)
        doc['date_start'] = obj.date_start()
        doc['date_end'] = obj.date_end()
        doc['status'] = ','.join(obj.attrs.get('statuses', []))
    elif name == 'person':
        doc['name'] = obj.full_name()
        doc['email'] = obj.attrs.get('email', None)
    elif name == 'ship':
        doc['name'] = obj.name()
    elif name == 'country':
        names = filter(None, [obj.name(), obj.iso_code(), obj.iso_code(3)])
        doc['names'] = ','.join(names)
    elif name == 'institution':
        doc['name'] = obj.attrs.get('name', None)
        doc['uri'] = obj.attrs.get('uri', None)
    elif name == 'collection':
        doc['names'] = ','.join(obj.names())
    else:
        ixw.cancel()
        ix.close()
        return

    doc['mtime'] = obj.mtime()
    doc['id'] = _model_id_to_index_id(obj.id)
    ixw.update_document(**doc)
    if not writer:
        ixw.commit()
        ix.close()


def save_note(note, writer=None):
    if not writer:
        ix = open_or_create_index('note')
        ixw = ix.writer()
    else:
        ixw = writer
    ixw.update_document(
        body=note.get('body', None),
        action=note.get('action', None),
        data_type=note.get('data_type', None),
        summary=note.get('subject', None),
        mtime=note.creation_stamp.timestamp,
        id=_model_id_to_index_id(note.id))
    if not writer:
        ixw.commit()
        ix.close()


def remove_obj(obj, writer=None):
    name = obj.type.lower()
    if not writer:
        ix = open_or_create_index(name)
        ixw = ix.writer()
    else:
        ixw = writer
    ixw.delete_by_term('id', obj.id)
    if not writer:
        ixw.commit()
        ix.close()


def remove_note(note, writer=None):
    if not writer:
        ix = open_or_create_index('note')
        ixw = ix.writer()
    else:
        ixw = writer
    ixw.delete_by_term('id', note.id)
    if not writer:
        ixw.commit()
        ix.close()


def rebuild_index(clear=False):
    """ Indexes all Objs and Notes.
        If clear is set, the indices are cleared and optimizations are made to
        avoid trying to figure out which ones are already indexed and skipping.

        If an index is known to be bad, it's best to clear it and rebuild the
        index using this function.

    """
    logging.info('Rebuilding search index')
    logging.info('Clear index first? %r' % clear)
    for name in _schemas.keys():
        logging.info('Indexing %s' % name)
        ix = open_or_create_index(name, force_create=clear)
        ixw = BufferedWriter(ix)

        model = _name_model[name]

        indexed_ids = set()
        to_index = set()

        if not clear:
            logging.info('Cleaning index and collecting indexed docs')
            ixs = ix.searcher()

            # Walk each index
            for fields in ixs.all_stored_fields():
                indexed_id = fields['id']
                indexed_ids.add(indexed_id)

                logging.debug('Check if %s still exists' % indexed_id)

                # for missing docs
                obj = model.get_id(indexed_id)
                if not obj:
                    logging.debug('Remove missing id %s' % indexed_id)
                    ixw.delete_by_term('id', indexed_id)
                # and modified docs
                else:
                    logging.debug('Check mtime for %s' % indexed_id)
                    indexed_time = fields['mtime']
                    mtime = obj.mtime()
                    if mtime > indexed_time:
                        logging.debug('%s has been modified' % indexed_id)
                        to_index.add(indexed_id)
            ixw.commit()

        logging.debug(repr(indexed_ids))
        logging.debug(repr(to_index))

        if model is models.Attr:
            objs = model.map_mongo(model.all_notes())
        else:
            objs = model.map_mongo(model.all())

        logging.debug(repr(objs))

        logging.info('Indexing new and modified docs')
        for obj in objs:
            # Index modified and new docs
            if obj.id in to_index or obj.id not in indexed_ids:
                logging.debug('Indexing %s' % obj.id)
                if model is models.Attr:
                    save_note(obj, ixw)
                else:
                    save_obj(obj, ixw)

        ixw.commit()
        ixw.close()
        ix.close()
    logging.info('Finished indexing')


def search(query_string):
    """ Performs search based on a query string

        Returns:
        A bunch of Objs
    """
    results = {}
    for name, schema in _schemas.items():
        fields = list(set(schema.names()) - set(('id', 'mtime', )))
        if len(fields) > 1:
            parser = MultifieldParser(fields, schema=schema, group=OrGroup)
        elif len(fields) is 1:
            parser = QueryParser(fields[0], schema=schema, group=OrGroup)
        else:
            return None
        q = parser.parse(query_string)
        ix = open_or_create_index(name)
        with ix.searcher() as searcher:
            try:
                results[name] = searcher.search(q)
            except NotImplementedError:
                pass
    return results


_ensure_index_dir()
triggers.saved_obj_actions.append(save_obj)
triggers.removed_obj_actions.append(remove_obj)
triggers.saved_note_actions.append(save_note)
triggers.removed_note_actions.append(remove_note)
