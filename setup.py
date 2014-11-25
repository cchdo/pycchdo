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
    'pyramid_exclog',
]
if version_info[:3] < (2,5,0):
    _requires_framework.append('pysqlite')
_requires_db_fs = [
    'psycopg2',
    'SQLAlchemy',
    'Geoalchemy2',
    'sqlalchemy_imageattach',
    'transaction',
    'pyramid_tm',
    'zope.sqlalchemy',
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
    'tempfilezipstream>=2.0',
    #'libcchdo>=0.8.2',
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
    extras_require=extras_require,
    entry_points = {
        'paste.app_factory': [
            'main = pycchdo:main',
        ],
        'console_scripts': [
            'pycchdo_initialize_db = pycchdo.scripts.initializedb:main',
            'pycchdo_clean_fs = pycchdo.scripts.clean_fs:main',
            ('pycchdo_rebuild_search_index = '
             'pycchdo.scripts.rebuild_search_index:main'),
            'pycchdo_import = pycchdo.importer:do_import',
            ('pycchdo_update_param_status_cache = '
             'pycchdo.scripts.update_param_status_cache:main'),
            ('pycchdo_edit_perms = '
             'pycchdo.scripts.edit_perms:main'),
        ],
    }
)
