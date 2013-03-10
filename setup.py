import os.path
from sys import version_info

from setuptools import setup, find_packages, Command

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()


_requires_framework = [
    'pyramid',
    'pyramid_jinja2',
    'pyramid_mailer',
    'pyramid_webassets',
]
if version_info[:3] < (2,5,0):
    _requires_framework.append('pysqlite')
_requires_db_fs = [
    'psycopg2',
    'SQLAlchemy>=0.8.0b2',
    'geoalchemy',
    'transaction',
    'pyramid_tm',
    'zope.sqlalchemy',
    'django',
]
_requires_assets = [
    'cssmin',
    'closure',
]
_requires_app = [
    'webhelpers',
    'pyKML',
    'whoosh',
    'geojson',
    'shapely',
    'libcchdo',
]
requires = \
    _requires_framework + \
    _requires_db_fs + \
    _requires_assets + \
    _requires_app


extras_require = {
    'dev': [
        'pyramid_debugtoolbar',
        'WebError',
        'waitress',
    ],
    'importer': ['paramiko'],
}


dependency_links = [
    #'hg+http://hg.sqlalchemy.org/sqlalchemy/@rel_0_8_8b2#egg=SQLAlchemy-0.8.8b2',
    #'http://hg.sqlalchemy.org/sqlalchemy/archive/8d82961d3464.tar.gz#egg=SQLAlchemy-0.8.0b2',
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
    extras_require=extras_require,
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
