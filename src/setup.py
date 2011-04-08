#!/usr/bin/env python

from setuptools import setup

version = "0.8.0b1"

setup(name = 'ispncon',
      version = version,
      description = 'Infinispan Console',
      author = 'Michal Linhard',
      author_email = 'michal@linhard.sk',
      py_modules = ['ispncon.console', 'ispncon.client'],
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
      long_description = "See `Infinispan Console <https://github.com/mlinhard/ispncon>`_ for more information."
      )