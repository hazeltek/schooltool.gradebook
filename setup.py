#!/usr/bin/env python
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008-2013 Shuttleworth Foundation
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
    description="Gradebook plugin for SchoolTool",
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
    classifiers=["Development Status :: 5 - Production/Stable",
    "Environment :: Web Environment",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License (GPL)",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Zope",
    "Topic :: Education"],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    namespace_packages=["schooltool"],
    install_requires=['schooltool>=2.6',
                      'lxml',
                      'pytz',
                      'setuptools',
                      'xlwt',
                      'z3c.form',
                      'z3c.optionstorage', # BBB
                      'zc.table',
                      'ZODB3',
                      'zope.annotation',
                      'zope.app.form',
                      'zope.app.generations>=3.5',
                      'zope.browser',
                      'zope.browserpage>=3.10.1',
                      'zope.cachedescriptors',
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
                             'zc.datetimewidget',
                             'schooltool.lyceum.journal>=2.5.2',
                             'schooltool.devtools>=0.6'],
                    'journal': ['schooltool.lyceum.journal>=2.5.2'],
                    },
    include_package_data=True,
    zip_safe=False,
    entry_points="""
        [z3c.autoinclude.plugin]
        target = schooltool
        """,
    )
