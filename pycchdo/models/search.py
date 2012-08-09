"""Indexing and search capabilities.

The index should be updated each time some object or note is edited or removed.

Fully re-indexing is also supported via rebuild_index.

"""
import os
from contextlib import contextmanager
from datetime import datetime

from whoosh import index
from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, DATETIME, BOOLEAN
from whoosh.writing import BufferedWriter
from whoosh.qparser import (
    QueryParser, MultifieldParser, AndGroup, FieldAliasPlugin,
    )
from whoosh.qparser.dateparse import DateParserPlugin

from pycchdo.models import triggers
from pycchdo.log import ColoredLogger
from pycchdo.models import (
    DBSession,
    Cruise, Person, Ship, Country, Institution, Collection, Note,
    )


log = ColoredLogger(__name__)


_name_model = {
    'cruise': Cruise,
    'person': Person,
    'ship': Ship,
    'country': Country,
    'institution': Institution,
    'collection': Collection,
    'note': Note,
}


_schemas = {
    'cruise': Schema(
        names=KEYWORD(lowercase=True, commas=True),
        date_start=DATETIME,
        date_end=DATETIME,
        ship=TEXT,
        country=TEXT,
        pis=KEYWORD(lowercase=True, commas=True),
        collections=KEYWORD(lowercase=True, commas=True),
        seahunt=BOOLEAN,
        status=KEYWORD(lowercase=True, commas=True),
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
        names=KEYWORD(lowercase=True, commas=True),
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
        names=KEYWORD(lowercase=True, commas=True),
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


_field_aliases = {
    'cruise': {
        'names': ['expocode', 'alias', 'aliases', ],
        'date_start': ['from', ],
        'date_end': ['to', ],
    },
    'person': {'name': ['people', 'person', ], },
    'ship': {'name': ['ship', ], },
    'country': {'names': ['country', ], },
    'institution': {'name': ['institution', ], },
    'collection': {'names': ['group', 'line', 'collection', ], },
    'note': {},
}


_model_id_to_index_id = unicode


def _create_parsers(schemas):
    parsers = {}
    for name, schema in schemas.items():
        fields = list(set(schema.names()) - set(('id', 'mtime', )))
        if len(fields) > 1:
            parser = MultifieldParser(fields, schema=schema, group=AndGroup)
        elif len(fields) is 1:
            parser = QueryParser(fields[0], schema=schema, group=AndGroup)
        else:
            continue
        parser.add_plugin(FieldAliasPlugin(_field_aliases[name]))
        if name == 'cruise':
            parser.add_plugin(DateParserPlugin())
        parsers[name] = parser
    return parsers


_parsers = _create_parsers(_schemas)


class SearchIndex(object):
    """Encapsulates a directory that is used as a Whoosh search index."""
    index_dir = '.'
    index_dir_checked_exists = False

    def __init__(self, index_dir=None):
        if index_dir is not None:
            self.index_dir = index_dir
        self._ensure_index_dir()
        self.register_triggers()

    def _ensure_index_dir(self):
        if self.index_dir_checked_exists:
            return
        try:
            os.makedirs(self.index_dir)
            self.index_dir_checked_exists = True
        except os.error, e:
            if not os.path.isdir(self.index_dir):
                log.critical(
                    'Ensure that %s is writeable by you.' % self.index_dir)
                raise e
            else:
                # Ignore os.error if directory exists
                self.index_dir_checked_exists = True

    def open_or_create_index(self, name, force_create=False):
        """Opens or creates and opens an index in the main directory."""
        if (    not force_create and
                index.exists_in(self.index_dir, indexname=name)):
            ix = index.open_dir(self.index_dir, indexname=name)
        else:
            try:
                ix = index.create_in(
                    self.index_dir, _schemas[name], indexname=name)
            except KeyError:
                raise ValueError('Invalid index name %s' % name)
        return ix

    def ensure_index(self, name):
        self.open_or_create_index(name).close()

    def ensure_indices(self):
        try:
            os.makedirs(self.index_dir)
            os.chmod(self.index_dir, 0700)
        except OSError:
            pass
        except IOError, e:
            log.error("Unable to access/create search index")
            raise e

        for name in _schemas.keys():
            self.ensure_index(name)

    @contextmanager
    def writer(self, index_name, writer=None, clear=False, buffered=False):
        if not writer:
            try:
                ix = self.open_or_create_index(index_name, clear)
            except ValueError:
                return
            if buffered:
                ixw = BufferedWriter(ix, period=60, limit=2**14)
            else:
                ixw = ix.writer()
        else:
            ixw = writer

        try:
            yield ixw
        finally:
            if not writer:
                if buffered:
                    ixw.close()
                else:
                    ixw.cancel()
                ix.close()


    def save_obj(self, obj, writer=None):
        try:
            obj.id
        except AttributeError:
            return
        name = obj.obj_type.lower()
        with self.writer(name, writer) as ixw:
            doc = {}

            if name == 'cruise':
                names = filter(None, [obj.expocode] + obj.aliases)
                doc['names'] = u','.join(names)
                if obj.date_start:
                    doc['date_start'] = obj.date_start
                    if type(doc['date_start']) is not datetime:
                        doc['date_start'] = None
                if obj.date_end:
                    doc['date_end'] = obj.date_end
                    if type(doc['date_end']) is not datetime:
                        doc['date_end'] = None
                if obj.ship:
                    doc['ship'] = unicode(obj.ship.name)
                if obj.country:
                    doc['country'] = unicode(obj.country.name)
                chiscis = obj.chief_scientists
                if chiscis:
                    doc['pis'] = u','.join(
                        [unicode(pi.person.full_name) for pi in chiscis])
                if obj.collections:
                    doc['collections'] = u','.join(
                        [unicode(c.name) for c in obj.collections])
                doc['status'] = u','.join(obj.statuses)
                doc['seahunt'] = not obj.accepted
            elif name == 'person':
                doc['name'] = unicode(obj.full_name)
                doc['email'] = unicode(obj.email)
            elif name == 'ship':
                doc['name'] = unicode(obj.name)
            elif name == 'country':
                names = filter(
                    None, [unicode(obj.name), obj.iso_code(), obj.iso_code(3)])
                names = [name.strip() for name in names]
                doc['names'] = u','.join(names)
            elif name == 'institution':
                doc['name'] = unicode(obj.name)
                doc['uri'] = unicode(obj.get('url', None))
            elif name == 'collection':
                doc['names'] = u','.join(filter(None, obj.names))
            else:
                ixw.cancel()
                ix.close()
                return

            doc['mtime'] = obj.mtime
            doc['id'] = _model_id_to_index_id(obj.id)
            log.debug(u'saving {0!r}'.format(doc))
            ixw.update_document(**doc)


    def save_note(self, note, writer=None):
        try:
            note.id
        except AttributeError:
            return
        with self.writer('note', writer) as ixw:
            ixw.update_document(
                body=note.body,
                action=note.action,
                data_type=note.data_type,
                summary=note.subject,
                mtime=note.creation_timestamp,
                id=_model_id_to_index_id(note.id))


    def remove_obj(self, obj, writer=None):
        name = obj.obj_type.lower()
        with self.writer(name, writer) as ixw:
            ixw.delete_by_term('id', _model_id_to_index_id(obj.id))


    def remove_note(self, note, writer=None):
        with self.writer('note', writer) as ixw:
            ixw.delete_by_term('id', _model_id_to_index_id(note.id))


    def rebuild_index(self, clear=False):
        """Indexes all Objs and Notes.

        If clear is set, the indices are cleared and optimizations are made to
        avoid trying to figure out which ones are already indexed and skipping.

        If an index is known to be bad, it's best to clear it and rebuild the
        index using this function.

        """
        log.info('Rebuilding search index')
        log.info('Clear index first? %r' % clear)
        schemas = _schemas.keys()
        if 'note' in schemas:
            schemas.remove('note')
            schemas.append('note')
        for name in schemas:
            log.info('Indexing %s' % name)
            with self.writer(name, clear=clear, buffered=True) as ixw:
                model = _name_model[name]

                indexed_ids = set()
                to_index = set()

                if not clear:
                    log.info((u'Cleaning index and collecting indexed docs '
                              'for {}').format(name))
                    ixs = ixw.searcher()

                    # Walk each index
                    for fields in ixs.all_stored_fields():
                        indexed_id = fields['id']
                        indexed_ids.add(indexed_id)

                        log.debug('Check %s existance' % indexed_id)

                        # for missing docs
                        obj = DBSession.query(model).get(indexed_id)
                        if not obj:
                            log.debug('Remove missing id %s' % indexed_id)
                            ixw.delete_by_term('id', indexed_id)
                        # and modified docs
                        else:
                            log.debug('Check %s mtime' % indexed_id)
                            try:
                                indexed_time = fields['mtime']
                                try:
                                    mtime = obj.mtime
                                except AttributeError:
                                    # Notes don't have an mtime
                                    mtime = obj.ctime
                                if mtime > indexed_time:
                                    log.debug(
                                        '%s has been modified' % indexed_id)
                                    to_index.add(indexed_id)
                            except KeyError:
                                to_index.add(indexed_id)
                    ixw.commit()

                log.debug(repr(indexed_ids))
                log.debug(repr(to_index))

                objs = DBSession.query(model).all()

                #log.debug(repr(objs))

                log.info('Indexing new and modified docs for %s' % name)
                l = float(len(objs))
                for i, obj in enumerate(objs):
                    # Index modified and new docs
                    oid = unicode(obj.id)
                    if oid in to_index or oid not in indexed_ids:
                        log.debug('Indexing %s' % obj.id)
                        if model is Note:
                            self.save_note(obj, ixw)
                        else:
                            self.save_obj(obj, ixw)
                    if i % 50 == 0:
                        log.info('%d/%d = %3.4f' % (i, l, i / l))

                ixw.commit()
        log.info('Finished indexing')

    def search(self, query_string, limit=None, search_notes=False, ):
        """Performs search based on a query string.

        Parameters:
            query_string    The query string to search for.
            limit           The maximum number of results to get. Leave as None
                            to get all results.
            search_notes    Whether to search Notes. Set to True to search Notes
                            with query_string.

        Returns:
            A dict with each type of index and a dict mapping a bunch of Objs
            for each type to their cruises.

            WARNING: results IS NOT homogeneous! Cruise and Note results are
            stored in lists, but ALL OTHER results are stored in a dict that
            maps them to their associated cruises!

        """
        results = {}

        # Search each model.
        for model_name, model_schema in _schemas.items():
            # Skip Notes if they were not requested.
            if model_name is 'note' and not search_notes:
                continue

            # Parse the query string in the context of the given model, and get
            # the objects that we will need to search the model index.
            model_parser = _parsers.get(model_name)
            try:
                query = model_parser.parse(query_string)
            except Exception, e:
                log.error(
                    'Query parse failed for "%s": %s' % (query_string, e))
            index = self.open_or_create_index(model_name)

            with index.searcher() as searcher:
                try:
                    # Search the index.
                    raw = searcher.search(query, limit=limit)

                    # Obtain the identifier function for the model. The
                    # identifier function takes object IDs and maps them to
                    # their objects.
                    model = _name_model[model_name]
                    if model_name == 'note':
                        model = Note

                    # Extract the result objects from the raw search results.
                    field_numbers = range(raw.estimated_length())
                    idwrappers = map(raw.fields, field_numbers)
                    idparams = [wrapper['id'] for wrapper in idwrappers]
                    objects = model.by_ids(idparams).all()

                    if model_name is 'cruise' or model_name is 'note':
                        # Cruises and Notes are quite simple. They are not
                        # supposed to have cruises associated with them, so we
                        # just put them directly into the results.
                        results[model_name] = objects
                    else:
                        # Everything else can have associated cruises. We will
                        # map each Obj to its associated cruises in the results
                        container = {}
                        for obj in objects:
                            container[obj] = obj.cruises()
                        results[model_name] = container

                except NotImplementedError:
                    pass
                except AttributeError:
                    pass
                except Exception, e:
                    log.error(
                        'Search failed for "%s": %s' % (query_string, e))

        # WARNING: results IS NOT homogeneous! (see docstring for details.)
        return results

    def register_triggers(self):
        triggers.saved_obj_actions.append(triggers.saved_obj)
        triggers.deleted_obj_actions.append(triggers.deleted_obj)
        triggers.saved_note_actions.append(triggers.saved_note)
        triggers.deleted_note_actions.append(triggers.deleted_note)

    def unregister_triggers(self):
        if not triggers:
            return
        try:
            triggers.saved_obj_actions.remove(self.save_obj)
        except ValueError:
            pass
        try:
            triggers.deleted_obj_actions.remove(self.remove_obj)
        except ValueError:
            pass
        try:
            triggers.saved_note_actions.remove(self.save_note)
        except ValueError:
            pass
        try:
            triggers.deleted_note_actions.remove(self.remove_note)
        except ValueError:
            pass

    def __del__(self):
        self.unregister_triggers()


def compile_into_cruises(results):
    """Convert the results of a search() into a list of Cruises.

    Notes are excluded from this compilation.

    """
    cruises = []
    for key, objs in results.items():
        if key == 'note':
            continue
        if key == 'cruise':
            cruises.extend(objs)
        elif key in ('person', 'ship', 'country', 'institution',
                     'collection', ):
            for obj in objs:
                cruises.extend(obj.cruises())
    return cruises
