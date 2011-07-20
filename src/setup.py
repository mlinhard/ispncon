#!/usr/bin/env python

from setuptools import setup
from ispncon import ISPNCON_VERSION

setup(name = 'ispncon',
      version = ISPNCON_VERSION,
      description = 'Infinispan Console',
      author = 'Michal Linhard',
      author_email = 'michal@linhard.sk',
      py_modules = ['ispncon.console', 'ispncon.client', 'ispncon.codec' ],
      classifiers = [
          "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
          "Programming Language :: Python",
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Topic :: Software Development :: Libraries :: Python Modules",
      ],
      keywords = 'infinispan hotrod memcached rest nosql datagrid console',
      license = 'LGPL',
      install_requires = [
        'setuptools',
        'greenlet',
        'infinispan',
        'python-memcached'
      ],
      long_description = "See `Infinispan Console <https://github.com/infinispan/ispncon>`_ for more information."
      )
