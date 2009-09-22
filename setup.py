#!/usr/bin/env python
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008    Shuttleworth Foundation,
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
SchoolTool US Gradebook setup script.
"""


# Check python version
import sys
if sys.version_info < (2, 4):
    print >> sys.stderr, '%s: need Python 2.4 or later.' % sys.argv[0]
    print >> sys.stderr, 'Your python is %s' % sys.version
    sys.exit(1)

import pkg_resources
pkg_resources.require("setuptools>=0.6a11")

import glob
import os
from setuptools import setup, find_packages
from distutils import log
from distutils.util import newer
from distutils.spawn import find_executable

def compile_translations(locales_dir):
    "Compile *.po files to *.mo files in the same directory."
    for po in glob.glob('%s/*/LC_MESSAGES/*.po' % locales_dir):
        mo = po[:-3] + '.mo'
        if newer(po, mo):
            log.info('Compile: %s -> %s' % (po, mo))
            os.system('msgfmt -o %s %s' % (mo, po))

if sys.argv[1] in ('build', 'install'):
    if not find_executable('msgfmt'):
        log.warn("GNU gettext msgfmt utility not found!")
        log.warn("Skip compiling po files.")
    else:
        compile_translations('src/schooltool/gradebook/locales')

if sys.argv[1] == 'clean':
    locales_dir = 'src/schooltool/gradebook/locales'
    for mo in glob.glob('%s/*/LC_MESSAGES/*.mo' % locales_dir):
        os.unlink(mo)

if os.path.exists("version.txt"):
    version = open("version.txt").read().strip()
else:
    version = open("version.txt.in").read().strip()

setup(
    name="schooltool.gradebook",
    description="SchoolTool US Gradebook package.",
    long_description="""TODO""",
    version=version,
    url='http://www.schooltool.org',
    license="GPL",
    maintainer="SchoolTool development team",
    maintainer_email="schooltool-dev@schooltool.org",
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
    install_requires=['schooltool',
                      'setuptools'],
    dependency_links=['http://ftp.schooltool.org/schooltool/releases/nightly/'],
    include_package_data=True,
    zip_safe=False
    )
