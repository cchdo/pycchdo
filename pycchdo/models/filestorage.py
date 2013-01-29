from tempfile import SpooledTemporaryFile

from django.core.files.base import File

from pycchdo.log import ColoredLogger, INFO, DEBUG


log = ColoredLogger(__name__)
log.setLevel(DEBUG)


class CachingFile(File):
    def __init__(self, *args, **kwargs):
        super(CachingFile, self).__init__(*args, **kwargs)
        cache = SpooledTemporaryFile()
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
        log.error(u'Unable to determine file size {0!r}: '
                  '{1!r}'.format(file, e))


def copy_chunked(infile, outfile, chunk=2**9):
    """Copies the file-like in to out in chunks."""
    try:
        cpos = infile.tell()
    except Exception:
        cpos = None
    data = infile.read(chunk)
    while data:
        outfile.write(data)
        data = infile.read(chunk)
    if cpos is not None:
        infile.seek(cpos)
    outfile.flush()
    outfile.seek(0)
