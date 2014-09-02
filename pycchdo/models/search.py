"""Indexing and search capabilities.

The index should be updated each time some object or note is edited or removed.

Fully re-indexing is also supported via rebuild_index.

"""
import os
from datetime import datetime
from contextlib import contextmanager
from re import compile as re_compile
from traceback import format_exc

from sqlalchemy.orm import noload, joinedload, subqueryload

from whoosh import index
from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, DATETIME, BOOLEAN
from whoosh.writing import BufferedWriter, IndexingError
from whoosh.qparser import (
    QueryParser, MultifieldParser, AndGroup, FieldAliasPlugin,
    )
from whoosh.qparser.dateparse import DateParserPlugin

from pycchdo.models import triggers
from pycchdo.log import getLogger, ERROR, INFO, DEBUG
from pycchdo.models.serial import (
    DBSession,
    Cruise, Person, Ship, Country, Institution, Collection, Note,
    )


log = getLogger(__name__)
log.setLevel(DEBUG)


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
        subject=TEXT,
        mtime=STORED,
        id=ID(stored=True, unique=True),
        ),
}


_field_aliases = {
    'cruise': {
        'names': ['cruise', 'expocode', 'alias', 'aliases', ],
        'date_start': ['from', 'start'],
        'date_end': ['to', 'end'],
    },
    'person': {'name': ['people', 'person', ], },
    'ship': {'name': ['ship', ], },
    'country': {'names': ['country', ], },
    'institution': {'name': ['institution', ], },
    'collection': {'names': ['group', 'line', 'collection', ], },
    'note': {},
}


_model_id_to_index_id = unicode


_cruise_load_options = [
        subqueryload('ship'), subqueryload('_aliases'),
        subqueryload('_statuses'), joinedload('files'),
        subqueryload('country'), subqueryload('collections'),
        noload('participants.person._permissions'),
        noload('participants.institution'), noload('institutions')
]


_cruises_load_options = [
    subqueryload('cruises.collections'), joinedload('cruises'),
    subqueryload('cruises._aliases'), subqueryload('cruises.ship'),
    subqueryload('cruises.country'),
    noload('cruises.institutions'),
    noload('cruises.participants.person._permissions'),
    noload('cruises.participants.institution'),
]


model_options = {
    Cruise: _cruise_load_options,
    Institution: _cruises_load_options,
    Collection: _cruises_load_options + [
        noload('_oceans'), noload('institution'), noload('country')
    ],
    Ship: _cruises_load_options,
    Country: _cruises_load_options,
    Person: [
        noload('country'), noload('institution'),
        noload('_permissions'),
        joinedload('participants.cruise'), noload('participants.institution'),
        joinedload('participants.cruise.ship'), 
    ],
}


def _create_parsers(schemas):
    parsers = {}
    for name, schema in schemas.items():
        fields = list(set(schema.names()) - set(('id', 'mtime', )))
        if len(fields) > 1:
            parser = MultifieldParser(fields, schema=schema, group=AndGroup)
        elif len(fields) == 1:
            parser = QueryParser(fields[0], schema=schema, group=AndGroup)
        else:
            continue
        parser.add_plugin(FieldAliasPlugin(_field_aliases[name]))
        if name == 'cruise':
            parser.add_plugin(DateParserPlugin())
        parsers[name] = parser
    return parsers


_parsers = _create_parsers(_schemas)


def rewrite_woce_line(parts):
    """Turn the separate parts into a woce line."""
    return u'{0}{1}'.format(parts[0], parts[1].zfill(2))


r_woceline = re_compile("(.*[A-Za-z]+)(\d+[^\s]*)")


def adapt_query_string_for_woce_line(qstr):
    parts = r_woceline.search(qstr)
    if parts:
        log.info(parts.start())
        log.info(parts.end())
        log.info(parts.groups())
        woce_line_query = u'({0} OR {1})'.format(
            ''.join(parts.groups()), rewrite_woce_line(parts.groups()))
        return qstr[:parts.start()] + woce_line_query + qstr[parts.end():]
    return qstr


class SearchResult(dict):
    """Search results are returned as a dictionary mapping the group type.

    * Cruises and Notes are returned in a list
    * Everything else, e.g. Ship, Country, etc. is returned in a dictionary
        The dictionary maps the ship/country/etc id to its cruises

    """
    def __nonzero__(self):
        """The SearchResult is Falsey if all of its groups are empty."""
        for val in self.values():
            if val:
                return True
        return False


def _str_to_date(text, end=False):
    """Convert a string or unicode to a date."""
    try:
        return datetime.strptime(text, '%Y-%m-%d')
    except ValueError:
        if end:
            return _str_to_date('{0}-12-31'.format(text))
        else:
            return _str_to_date('{0}-01-01'.format(text))


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
                raise ValueError('No schema defined for index name %s' % name)
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
            except ValueError, e:
                log.error(u'Unable to open index {0}: {1!r}'.format(
                    index_name, e))
                yield None
                return
            if buffered:
                ixw = BufferedWriter(ix, period=60, limit=2**14)
            else:
                ixw = ix.writer()
        else:
            ixw = writer

        try:
            yield ixw
        except Exception, err:
            raise
        finally:
            if not writer:
                try:
                    ixw.commit()
                except IndexingError, err:
                    # According to whoosh, bufferedwriters can be committed
                    # multiple times. Not sure why this last call can result in
                    # already closed if a commit was already called.
                    if str(err) != 'This writer is closed':
                        raise
                if buffered:
                    ixw.close()
                ix.close()

    @contextmanager
    def searcher(self, index_name, index=None):
        if index is None:
            index = self.open_or_create_index(index_name)
        with index.searcher() as searcher:
            yield searcher

    def save_obj(self, obj, writer=None):
        try:
            obj.id
        except AttributeError:
            return
        name = obj.obj_type.lower()
        if name not in _schemas.keys():
            return
        with self.writer(name, writer) as ixw:
            if ixw is None:
                log.warn(
                    u'Unable to index obj {0!r}, could not open index {1}'.format(
                    obj, name))
                return
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
            if ixw is None:
                log.warn(u'Unable to index note {0!r}'.format(note))
                return
            doc = {}
            if note.body:
                doc['body'] = unicode(note.body)
            if note.action:
                doc['action'] = unicode(note.action)
            if note.data_type:
                doc['data_type'] = unicode(note.data_type)
            if note.subject:
                doc['subject'] = unicode(note.subject)
            doc['mtime'] = note.ts_c
            doc['id'] = _model_id_to_index_id(note.id)
            ixw.update_document(**doc)


    def remove_obj(self, obj, writer=None):
        name = obj.obj_type.lower()
        with self.writer(name, writer) as ixw:
            if ixw is None:
                log.warn(u'Unable to unindex obj {0!r}'.format(obj))
                return
            ixw.delete_by_term('id', _model_id_to_index_id(obj.id))


    def remove_note(self, note, writer=None):
        with self.writer('note', writer) as ixw:
            if ixw is None:
                log.warn(u'Unable to unindex note {0!r}'.format(note))
                return
            ixw.delete_by_term('id', _model_id_to_index_id(note.id))

    def _clean_index(self, ixw, model, indexed_ids, to_index):
        ixs = ixw.searcher()

        try:
            # Walk each index
            for fields in ixs.all_stored_fields():
                indexed_id = fields['id']
                indexed_ids.add(indexed_id)

                log.debug('Check %s existance' % indexed_id)

                # for missing docs
                obj = model.query().get(indexed_id)
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
                            pass
                        if not mtime:
                            mtime = obj.ctime
                        if mtime > indexed_time:
                            log.debug('%s has been modified' % indexed_id)
                            to_index.add(indexed_id)
                    except (KeyError, TypeError):
                        to_index.add(indexed_id)
        except Exception, err:
            log.error(repr(err))
        finally:
            ixs.close()

    def _rebuild_index(self, name, clear=False):
        with self.writer(name, clear=clear, buffered=True) as ixw:
            if ixw is None:
                log.warn(u'Unable to index {0!r}'.format(name))
                return
            model = _name_model[name]

            indexed_ids = set()
            to_index = set()

            if not clear:
                log.info(u'Cleaning index and collecting indexed docs for '
                         '{0}'.format(name))
                self._clean_index(ixw, model, indexed_ids, to_index)
                log.info('cleaned')
                ixw.commit()

            log.debug(repr(indexed_ids))
            log.debug(repr(to_index))

            objs = model.query().all()

            log.info('Indexing new and modified docs for %s' % name)
            l = float(len(objs))
            for i, obj in enumerate(objs):
                # Index modified and new docs
                oid = unicode(obj.id)
                if oid in to_index or oid not in indexed_ids:
                    log.debug('Indexing {0} {1}'.format(name, obj.id))
                    if model is Note:
                        self.save_note(obj, ixw)
                    else:
                        self.save_obj(obj, ixw)
                if i % 50 == 0:
                    log.info('%d/%d = %3.4f' % (i, l, i / l))

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
            self._rebuild_index(name, clear)
        log.info('Finished indexing')

    def _filter_seahunt_for_cruise_parser(self, query):
        """Remove seahunt term from cruise query.

        Don't know why this didn't used to be a problem but now queryparser
        inserts seahunt:True to all Cruise queries which causes all seahunt
        to be returned.

        """
        try:
            for iii, subq in enumerate(query.subqueries):
                self._filter_seahunt_for_cruise_parser(subq)
                try:
                    if subq.fieldname == 'seahunt':
                        del query.subqueries[iii]
                        break
                except AttributeError:
                    pass
        except AttributeError:
            pass

    def _model_query_string_to_query(self, model_name, qstring):
        """Parse the query string in the context of the given model. 
        Also get the objects that we will need to search the model index.

        """
        model_parser = _parsers.get(model_name)
        try:
            query = model_parser.parse(qstring)
            if model_name == 'cruise' and 'seahunt' not in qstring:
                self._filter_seahunt_for_cruise_parser(query)
            log.debug(u'Query: {0}\t{1!r}'.format(model_name, query))
        except Exception, err:
            log.error('Query parse failed for {0} {1!r}: {2}'.format(
                model_name, qstring, err))
            query = None
        return query

    def search(self, query_string, search_notes=False, **kwargs):
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
            i.e. 
            {
                'cruise': [],
                'note': [],
                'ship': {123: Cruise},
            }

        """
        results = SearchResult()

        query_string = adapt_query_string_for_woce_line(query_string)

        log.debug('New query: {0!r}'.format(query_string))
        # Search each model.
        for model_name, model_schema in _schemas.items():
            # Skip Notes if they were not requested.
            if model_name is 'note' and not search_notes:
                continue

            query = self._model_query_string_to_query(model_name, query_string)
            if not query:
                continue

            with self.searcher(model_name) as searcher:
                try:
                    # Search the index.
                    try:
                        kwargs['limit']
                    except KeyError:
                        kwargs['limit'] = None
                    raw = searcher.search(query, **kwargs)

                    log.debug('{0} results'.format(len(raw)))

                    # Obtain the identifier function for the model. The
                    # identifier function takes object IDs and maps them to
                    # their objects.
                    model = _name_model[model_name]

                    # Extract the result objects from the raw search results.
                    field_numbers = range(raw.estimated_length())
                    idwrappers = map(raw.fields, field_numbers)
                    idparams = [wrapper['id'] for wrapper in idwrappers]

                    if idparams:
                        load = model.query_all_by_ids(*idparams)
                        try:
                            options = model_options[model]
                            load = load.options(*options)
                        except KeyError:
                            pass
                        objects = load.all()
                    else:
                        objects = []

                    if model_name == 'cruise' or model_name == 'note':
                        # Cruises and Notes are quite simple. They are not
                        # supposed to have cruises associated with them, so we
                        # just put them directly into the results.
                        results[model_name] = objects
                    else:
                        # Everything else can have associated cruises. We will
                        # map each Obj to its associated cruises in the results
                        container = SearchResult()
                        for obj in objects:
                            container[obj] = obj.cruises
                        results[model_name] = container

                except NotImplementedError, err:
                    log.warn(repr(err))
                except Exception:
                    log.error(
                        'Search failed for {0!r}: {1}'.format(
                        query_string, format_exc()))

        # WARNING: results IS NOT homogeneous! (see docstring for details.)
        return results

    def register_triggers(self):
        # !!! Careful not to set these to trigger's eponymous functions or you
        # will infinite recurse.
        triggers.saved_obj_actions.append(self.save_obj)
        triggers.deleted_obj_actions.append(self.remove_obj)
        triggers.saved_note_actions.append(self.save_note)
        triggers.deleted_note_actions.append(self.remove_note)

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
                cruises.extend(obj.cruises)
    return cruises
