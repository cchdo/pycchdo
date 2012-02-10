pycchdo README

Installation
============

$ python setup.py install

Dependencies
------------
python setup.py install will take care of most of these for you with the
exception of 

 * libcchdo

Setup
-----
A mongodb should be available. Please specify the database's URI in your
deployment config file e.g. production.ini.

Add both 

        db_uri = mongodb://host:port/?journal=true&w=1

and

        db_name = cchdo

A search index is also used courtesy of whoosh. Configure where the index
should be stored by setting

        db_search_index_path = /var/cache/pycchdo_search_index

Building up history
-------------------
In order to draw in data from the legacy CCHDO and Seahunt sites, run

$ sudo python pycchdo/importer.py

Refer to 

$ python pycchdo/importer.py --help

for more information.

This script needs to be run as root in order to correctly import file
permissions. This script will also write out the search index. Keep in mind
that the permissions for the search index need to be read/writeable by the user
that will run the WSGI app.

Development
===========
pycchdo is a WSGI application built using Pyramid.
