from sqlalchemy_imageattach.entity import Image
from sqlalchemy_imageattach.context import current_store
from sqlalchemy_imageattach.stores.fs import FileSystemStore, guess_extension

from pycchdo.log import getLogger


log = getLogger(__name__)


class AdaptedFile(Image):
    """A base File for persisting to the database and storage system.

    This class derives from sqlalchemy_imageattach. It does not use the image
    capability and attempts to mask some of those features. These methods
    originated from ImageSet, a dynamic query class that allowed for multiple
    thumbnails per image. They are pulled here because the multiple file per
    item functionality is not needed.

    """
    @classmethod
    def from_raw_file(cls, raw_file, store=current_store, mimetype=None):
        """Similar to :meth:`from_file()` except it's lower than that.
        It assumes that ``raw_file`` is readable and seekable while
        :meth:`from_file()` only assumes the file is readable.
        Also it doesn't make any in-memory buffer while
        :meth:`from_file()` always makes an in-memory buffer and copy
        the file into the buffer.

        If ``mimetype`` is passed, it won't try to read File and will use that
        values instead.

        It's used for implementing :meth:`from_file()` and
        :meth:`from_blob()` methods that are higher than it.

        :param raw_file: the seekable and readable file of the file
        :type raw_file: file-like object, :class:`file`
        :param store: the storage to store the file.
                      :data:`~sqlalchemy_imageattach.context.current_store`
                      by default
        :type store: :class:`~sqlalchemy_imageattach.store.Store`
        :param mimetype: an optional mimetype of the file.
                         automatically detected if it's omitted
        :type mimetype: :class:`basestring`
        :returns: the created file instance
        :rtype: :class:`File`

        """
        # This method is simplified from imageattach because it is not necessary
        # to clean out old thumbnails.
        file = cls(mimetype=mimetype)
        raw_file.seek(0)
        file.file = raw_file
        file.store = store
        return file

    @classmethod
    def from_blob(cls, blob, store=current_store, mimetype=None):
        return ImageSet.from_raw_file(cls, blob, store, mimetype=mimetype)

    @classmethod
    def from_file(cls, file, store=current_store, mimetype=None):
        return ImageSet.from_raw_file(cls, file, store, mimetype=mimetype)


# Disable some imageattach based functionality
Image.width = '0'
Image.height = '0'
Image.original = True


class FSStore(FileSystemStore):
    def get_path(self, object_type, object_id, width, height, mimetype):
        id_segment_a = str(object_id % 1000)
        id_segment_b = str(object_id // 1000)
        suffix = guess_extension(mimetype)
        # apparently the guess for text/plain changes
        # This is a known issue python-Bugs-1043134
        if mimetype == 'text/plain':
            suffix = '.txt'
        filename = '.'.join(filter(None, [str(object_id), suffix]))
        return id_segment_a, id_segment_b, filename
