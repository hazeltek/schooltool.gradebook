# coding=UTF8
#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008 Shuttleworth Foundation
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
Unit tests for schooltool.gradebook.generations.evolve2
"""

import unittest

from zope.app.zopeappgenerations import getRootFolder
from zope.interface import implements
from zope.testing import doctest

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook.generations.tests import ContextStub
from schooltool.gradebook.generations.tests import provideAdapters
from schooltool.gradebook.generations.evolve2 import evolve
from schooltool.requirement.interfaces import ICustomScoreSystem


class CustomScoreSystemStub(object):
    implements(ICustomScoreSystem)

    scores = [('A', 0, 0), ('B', 0, 0)]
    title = 'stub'
    hidden = False


def doctest_evolve2():
    """Evolution to generation 2.

    First, we'll set up the app object:

        >>> provideAdapters()
        >>> context = ContextStub()
        >>> app = getRootFolder(context)

        >>> from zope.app.component.site import LocalSiteManager
        >>> app.setSiteManager(LocalSiteManager(app))

    We'll set up our test with data that will be effected by running the
    evolve script:

        >>> from schooltool.requirement.interfaces import IScoreSystemsProxy
        >>> proxy = IScoreSystemsProxy(app)
        >>> custom_ss = CustomScoreSystemStub()
        >>> proxy.addScoreSystem(custom_ss)

    Finally, we'll run the evolve script, testing the effected values before and
    after:

        >>> custom_ss.scores
        [('A', 0, 0), ('B', 0, 0)]

        >>> evolve(context)

        >>> custom_ss.scores
        [['A', '', 0, 0], ['B', '', 0, 0]]
    """


def test_suite():
    return unittest.TestSuite([
        doctest.DocTestSuite(optionflags=doctest.ELLIPSIS
                                         | doctest.NORMALIZE_WHITESPACE
                                         | doctest.REPORT_NDIFF
                                         | doctest.REPORT_ONLY_FIRST_FAILURE),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

