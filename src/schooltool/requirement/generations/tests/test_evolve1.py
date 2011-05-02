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
Unit tests for schooltool.requirement.generations.evolve1
"""

import unittest, doctest

from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup

from schooltool.requirement.generations.tests import (ContextStub,
    provideAdapters, provideUtilities)
from schooltool.requirement.generations.evolve1 import evolve


def doctest_evolve1():
    """Evolution to generation 1.

    First, we'll set up the app object:

        >>> provideAdapters()
        >>> provideUtilities()
        >>> context = ContextStub()
        >>> app = getRootFolder(context)

        >>> from zope.site import LocalSiteManager
        >>> app.setSiteManager(LocalSiteManager(app))

    We'll set up our test with data that will be effected by running the
    evolve script:

        >>> from schooltool.requirement.interfaces import ICustomScoreSystem
        >>> from schooltool.requirement.scoresystem import (PassFail,
        ...     AmericanLetterScoreSystem, ExtendedAmericanLetterScoreSystem,
        ...     CustomScoreSystem)
        >>> for ss in [PassFail, AmericanLetterScoreSystem, 
        ...            ExtendedAmericanLetterScoreSystem]:
        ...     custom_ss = CustomScoreSystem(ss.title, ss.description,
        ...         ss.scores, ss._bestScore, ss._minPassingScore)
        ...     app.getSiteManager().registerUtility(custom_ss,
        ...          ICustomScoreSystem, name=custom_ss.title)

    Finally, we'll run the evolve script, testing the effected values before and
    after:

        >>> from schooltool.requirement.scoresystem import (
        ...     SCORESYSTEM_CONTAINER_KEY)
        >>> SCORESYSTEM_CONTAINER_KEY in app
        False
        >>> sorted(app.getSiteManager().getUtilitiesFor(ICustomScoreSystem))
        [(u'Extended Letter Grade',
             <CustomScoreSystem u'Extended Letter Grade'>),
         (u'Letter Grade', <CustomScoreSystem u'Letter Grade'>),
         (u'Pass/Fail', <CustomScoreSystem u'Pass/Fail'>)]

        >>> evolve(context)

        >>> [ss for ss in app[SCORESYSTEM_CONTAINER_KEY].values()]
        [<CustomScoreSystem u'Letter Grade'>, <CustomScoreSystem u'Pass/Fail'>,
         <CustomScoreSystem u'Extended Letter Grade'>]
        >>> sorted(app.getSiteManager().getUtilitiesFor(ICustomScoreSystem))
        []
    """


def setUp(test):
    setup.placefulSetUp()
    setup.setUpTraversal()


def tearDown(test):
    setup.placefulTearDown()


def test_suite():
    optionflags = (doctest.ELLIPSIS |
                   doctest.NORMALIZE_WHITESPACE |
                   doctest.REPORT_ONLY_FIRST_FAILURE)
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=optionflags)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

