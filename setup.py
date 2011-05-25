#!/usr/bin/env python
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008, 2009, 2010 Shuttleworth Foundation,
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
SchoolTool Gradebook setup script.
"""

import os
from setuptools import setup, find_packages

if os.path.exists("version.txt"):
    version = open("version.txt").read().strip()
else:
    version = open("version.txt.in").read().strip()

def read(*rnames):
    text = open(os.path.join(os.path.dirname(__file__), *rnames)).read()
    return text

setup(
    name="schooltool.gradebook",
    description="A gradebook component for SchoolTool",
    long_description=(
        read('README.txt')
        + '\n\n' +
        read('CHANGES.txt')
        ),
    version=version,
    url='http://www.schooltool.org',
    license="GPL",
    maintainer="SchoolTool Developers",
    maintainer_email="schooltool-developers@lists.launchpad.net",
    platforms=["any"],
    classifiers=["Development Status :: 4 - Beta",
    "Environment :: Web Environment",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Zope",
    "Topic :: Education",
    "Topic :: Office/Business :: Scheduling"],
    package_dir={'': 'src'},
    namespace_packages=["schooltool"],
    packages=find_packages('src'),
    install_requires=['schooltool>=1.6.0b1',
                      'rwproperty',
                      'setuptools',
                      'xlwt',
                      'z3c.form',
                      'z3c.optionstorage',
                      'ZODB3',
                      'zope.annotation',
                      'zope.app.form',
                      'zope.app.generations>=3.5',
                      'zope.browser',
                      'zope.browserpage>=3.10.1',
                      'zope.component',
                      'zope.componentvocabulary',
                      'zope.container',
                      'zope.event',
                      'zope.formlib>=4',
                      'zope.html',
                      'zope.i18n',
                      'zope.i18nmessageid',
                      'zope.interface',
                      'zope.keyreference',
                      'zope.lifecycleevent',
                      'zope.location',
                      'zope.publisher',
                      'zope.schema',
                      'zope.security',
                      'zope.traversing',
                      'zope.viewlet'],
    extras_require={'test': ['zope.app.publication',
                             'zope.app.testing',
                             'zope.intid',
                             'zope.site',
                             'zope.testbrowser',
                             'zope.ucol',
                             'schooltool.lyceum.journal'],
                    'journal': ['schooltool.lyceum.journal'],
                    },
    include_package_data=True,
    zip_safe=False,
    entry_points="""
        [z3c.autoinclude.plugin]
        target = schooltool
        """,
    )
