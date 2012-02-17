import os
import sys

from setuptools import setup, find_packages, Command

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

_importer_requires = [
#    'libcchdo',
    'paramiko',
    'geoalchemy',
    ]

requires = [
    'repoze.tm2',
    'pyramid_jinja2',
    'pyramid_mailer',
    'webhelpers',
    'WebError',
    'pymongo',
    'pyKML',
    'whoosh',
    'waitress',
    'geojson',
    'shapely',
    ] + _importer_requires

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')


class SearchIndexCommand(Command):
    description = "Rebuilds the search index"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        pass

setup(
    name='pycchdo',
    version='0.7',
    description='pycchdo',
    long_description=README + '\n\n' +  CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author='CCHDO',
    author_email='cchdo@ucsd.edu',
    url='',
    keywords='web wsgi bfg pyramid',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    test_suite='pycchdo.tests',
    install_requires = requires,
    entry_points = {
        'paste.app_factory': [
            'main = pycchdo:main',
        ],
    }
)
