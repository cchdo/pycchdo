import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

_importer_requires = [
#    'libcchdo',
    'paramiko',
    ]

requires = [
    'repoze.tm2',
    'pyramid_jinja2',
    'pyramid_mailer',
    'webhelpers',
    'WebError',
    'pymongo',
    'whoosh',
    'geojson',
    'shapely',
    ] + _importer_requires

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='pycchdo',
      version='0.0',
      description='pycchdo',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='pycchdo.tests',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = pycchdo:main
      """,
      paster_plugins=['pyramid'],
      )

