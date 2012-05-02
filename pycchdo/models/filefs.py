import os
from uuid import uuid4
from datetime import datetime
from tempfile import mkdtemp


def copy_file_obj(src, dest, blocksize=2 ** 20):
    data = src.read(blocksize)
    while data:
        dest.write(data)
        data = src.read(blocksize)
    dest.flush()


class NoFile(IOError):
    pass


class FileOut:
    """ A file wrapper for FileFS that acts similarly to gridfs' GridOut.

    """
    def __init__(self, file, id, name, content_type, upload_date):
        self._id = id
        self._file = file
        self._name = name
        self._contentType = content_type
        self._uploadDate = upload_date

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def content_type(self):
        return self._contentType

    @property
    def upload_date(self):
        return self._uploadDate

    def __iter__(self):
        return iter(self._file)

    def read(self, size=-1):
        return self._file.read(size)

    def readline(self, size=-1):
        return self._file.readline(size)

    def seek(self, pos, whence=0):
        self._file.seek(pos, whence)

    def tell(self):
        return self._file.tell()

    def close(self):
        self._file.close()
        

class FileFS:
    def __init__(self, connection, root=None):
        """ A filesystem backed file storage.
        
            connection is a temporary for-development connection to a database
            in which id-location mappings are stored.

            root - the directory in which the files are placed.

        """
        self.connection = connection
        # XXX In the case of MongoDB, the connection will be the cchdo database.
        # TODO in other cases, the connection might be something else
        self.map = connection.filefs

        if root:
            self.root = root
        else:
            self.root = mkdtemp()

    def _file_path(self, id):
        # Put the file in a leader directory to prevent large amounts of files
        # in one directory
        leader = id[:2]
        return os.path.join(self.root, leader, id)

    def put(self, file, filename=None, contentType=None):
        """ Store a file-like object along with some other attributes

        """
        id = str(uuid4())
        path = self._file_path(id)
        while os.path.isfile(path):
            id = str(uuid4())
            path = self._file_path(id)

        try:
            os.mkdir(os.path.dirname(path))
        except OSError:
            pass

        with open(path, 'w') as destobj:
            copy_file_obj(file, destobj)

        self.map.insert({
            '_id': id,
            'name': filename,
            'contentType': contentType,
            'uploadDate': datetime.utcnow(),
        })

        return id

    def get(self, id):
        """ Returns a file-like object representing the data stored under id.

            The file-like object has the additional attributes stored in put()
            as attributes.

        """
        doc = self.map.find_one({'_id': id})
        if doc:
            try:
                return FileOut(
                    open(self._file_path(id), 'r'), id,
                    doc['name'], doc['contentType'], doc['uploadDate'])
            except OSError:
                self.map.remove(id)
        raise NoFile()

    def delete(self, id):
        """ Remove the data stored under id

        """
        self.map.remove(id)
        try:
            path = self._file_path(id)
            os.unlink(path)
            # Remove the leader directory if empty
            try:
                os.rmdir(os.path.dirname(path))
            except OSError:
                pass
        except OSError:
            raise NoFile()
