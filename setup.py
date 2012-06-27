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
    'SQLAlchemy',
    'transaction',
    'pyramid_tm',
    'zope.sqlalchemy',
]
_requires_app = [
    'webhelpers',
    'pyKML',
    'whoosh',
    'geojson',
    'shapely',
]
_requires_importer = [
#    'libcchdo',
    'paramiko',
    'geoalchemy',
]
requires = \
    _requires_framework + \
    _requires_framework_db + \
    _requires_app + \
    _requires_importer


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
        'console_scripts': [
            'pycchdo_initialize_db = pycchdo.scripts.initializedb:main',
            'pycchdo_import = pycchdo.importer:do_import',
        ],
    }
)
