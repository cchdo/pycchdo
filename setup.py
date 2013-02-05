import os
import sys

from setuptools import setup, find_packages, Command

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()


_requires_framework = [
    'repoze.tm2',
    'pyramid',
    'pyramid_jinja2',
    'pyramid_mailer',
    'WebError',
    'waitress',
]
if sys.version_info[:3] < (2,5,0):
    _requires_framework.append('pysqlite')
_requires_framework_db = [
    'SQLAlchemy>=0.8.0b2',
    'transaction',
    'pyramid_tm',
    'django',
    'zope.sqlalchemy',
]
_requires_app = [
    'webhelpers',
    'pyKML',
    'whoosh',
    'geoalchemy',
    'geojson',
    'shapely',
    'libcchdo',
]
_requires_importer = [
    'paramiko',
]
requires = \
    _requires_framework + \
    _requires_framework_db + \
    _requires_app + \
    _requires_importer


dependency_links = [
    #'hg+http://hg.sqlalchemy.org/sqlalchemy/@rel_0_8_8b2#egg=SQLAlchemy-0.8.8b2',
    #'http://hg.sqlalchemy.org/sqlalchemy/archive/8d82961d3464.tar.gz#egg=SQLAlchemy-0.8.0b2',
    #'git+git@bitbucket.org:ghdc/libcchdo.git#egg=libcchdo',
    'https://bitbucket.org/ghdc/libcchdo/get/master.tar.bz2#egg=libcchdo',
]

setup(
    name='pycchdo',
    version='0.8',
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
    install_requires=requires,
    dependency_links=dependency_links,
    entry_points = {
        'paste.app_factory': [
            'main = pycchdo:main',
        ],
        'console_scripts': [
            'pycchdo_initialize_db = pycchdo.scripts.initializedb:main',
            ('pycchdo_rebuild_search_index = '
             'pycchdo.scripts.rebuild_search_index:main'),
            'pycchdo_import = pycchdo.importer:do_import',
        ],
    }
)
