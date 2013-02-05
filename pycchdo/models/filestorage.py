import os.path
from tempfile import SpooledTemporaryFile

from django.core.files.base import File
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import SuspiciousOperation
from django.utils._os import safe_join

from pycchdo.models import log


class CachingFile(File):
    def __init__(self, *args, **kwargs):
        super(CachingFile, self).__init__(*args, **kwargs)
        cache = SpooledTemporaryFile(max_size=2 ** 20)
        try:
            cache.name = self.file.name
        except AttributeError:
            pass
        copy_chunked(self.file, cache)
        self.file = cache

    @property
    def size(self):
        return seek_size(self.file)

    def __del__(self):
        if self.file:
            del self.file


def seek_size(file):
    """Return the size of the file by seeking."""
    try:
        cpos = file.tell()
        file.seek(0, 2)
        size = file.tell()
        if not file.isatty():
            file.seek(cpos)
        return size
    except IOError, e:
        log.error(
            u'Unable to determine file size {0!r}: {1!r}'.format(file, e))


def copy_chunked(infile, outfile, chunk=2**9):
    """Copies the file-like in to out in chunks."""
    try:
        cipos = infile.tell()
    except Exception:
        cipos = None
    try:
        copos = outfile.tell()
    except Exception:
        copos = None
    log.debug('copying {0} -> {1}'.format(infile, outfile))
    i = 0
    data = infile.read(chunk)
    while data:
        outfile.write(data)
        data = infile.read(chunk)
        i += 1
        if i % 1000 == 0:
            log.debug('{0} chunks'.format(i))
    log.debug('copied {0} chunks'.format(i))
    if cipos is not None:
        infile.seek(cipos)
    outfile.flush()
    if copos is not None:
        outfile.seek(copos)
    log.debug('copy complete {0} -> {1}'.format(infile, outfile))


class DirFileSystemStorage(FileSystemStorage):
    def path(self, name):
        try:
            fragments = [name[:2], name[2:4], name[4:6]]
        except TypeError:
            fragments = []
        fragments.append(name)
        try:
            path = safe_join(self.location, *fragments)
        except (TypeError, ValueError):
            raise SuspiciousOperation("Attempted access to '%s' denied." % name)
        return os.path.normpath(path)
