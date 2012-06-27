import warnings


def flatten(l):
    return [item for sublist in l for item in sublist]


def str2uni(x):
    if type(x) is str:
        return unicode(x)
    return x


def is_valid_ipv4(ip):
    try:
        return socket.inet_pton(socket.AF_INET, ip)
    except AttributeError: # no inet_pton here, sorry
        try:
            return socket.inet_aton(ip)
        except socket.error:
            return False
    except socket.error:
        return False


def is_valid_ipv6(ip):
    try:
        return socket.inet_pton(socket.AF_INET6, ip)
    except socket.error:
        return False


def is_valid_ip(ip):
    return is_valid_ipv4(ip) or is_valid_ipv6(ip)


class FileProxyMixin(object):
    """A mixin class used to forward file methods to an underlaying file object.
    The internal file object has to be called "file"::

        class FileProxy(FileProxyMixin):
            def __init__(self, file):
                self.file = file

    Snagged from django.core.files.utils

    """

    encoding = property(lambda self: self.file.encoding)
    fileno = property(lambda self: self.file.fileno)
    flush = property(lambda self: self.file.flush)
    isatty = property(lambda self: self.file.isatty)
    newlines = property(lambda self: self.file.newlines)
    read = property(lambda self: self.file.read)
    readinto = property(lambda self: self.file.readinto)
    readline = property(lambda self: self.file.readline)
    readlines = property(lambda self: self.file.readlines)
    seek = property(lambda self: self.file.seek)
    softspace = property(lambda self: self.file.softspace)
    tell = property(lambda self: self.file.tell)
    truncate = property(lambda self: self.file.truncate)
    write = property(lambda self: self.file.write)
    writelines = property(lambda self: self.file.writelines)
    xreadlines = property(lambda self: self.file.xreadlines)

    @property
    def closed(self):
        try:
            return self.file.closed
        except AttributeError:
            return False

    def __iter__(self):
        return iter(self.file)


def deprecated(message=''):
    """This is a decorator which can be used to mark functions as deprecated.

    It will result in a warning being emitted when the function is used.

    http://wiki.python.org/moin/PythonDecoratorLibrary#
        Generating_Deprecation_Warnings
    
    """
    def deprecated(func):
        msg = '{}() is deprecated: {}'.format(func.__name__, message)
        def new_func(*args, **kwargs):
            warnings.warn(msg, category=DeprecationWarning)
            return func(*args, **kwargs)
        new_func.__name__ = func.__name__
        new_func.__doc__ = func.__doc__
        new_func.__dict__.update(func.__dict__)
        return new_func
    return deprecated
