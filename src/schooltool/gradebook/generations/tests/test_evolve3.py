# SchoolTool - common information systems platform for school administration
# Copyright (c) 2011 Shuttleworth Foundation
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
Unit tests for schooltool.gradebook.generations.evolve1
"""

import unittest, doctest

from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup
from zope.component import provideHandler
from zope.interface import implements
from zope.lifecycleevent.interfaces import IObjectMovedEvent
from zope.site import LocalSiteManager

from schooltool.gradebook.generations.tests import ContextStub
from schooltool.gradebook.generations.evolve3 import evolve
from schooltool.gradebook.generations.evolve3 import GRADEBOOK_ROOT_KEY
from schooltool.gradebook.interfaces import IGradebookRoot
from schooltool.gradebook.gradebook_init import GradebookTemplates
from schooltool.gradebook.gradebook_init import GradebookDeployed
from schooltool.gradebook.gradebook_init import GradebookLayouts


class GradebookRoot_gen2(object):
    """Root of gradebook data"""

    implements(IGradebookRoot)

    def __init__(self):
        self.templates = GradebookTemplates(u'Report Sheet Templates')
        self.deployed = GradebookDeployed(u'Deployed Report Sheets')
        self.layouts = GradebookLayouts(u'Report Card Layouts')


def doctest_evolve3():
    r"""Evolution to generation 3.

    First, we'll set up the app object:

        >>> context = ContextStub()
        >>> app = getRootFolder(context)
        >>> app.setSiteManager(LocalSiteManager(app))

    And add the old gradebook.

        >>> app[GRADEBOOK_ROOT_KEY] = GradebookRoot_gen2()

        >>> def onMoved(e):
        ...     print 'Moved %s\n  __parent__: %s\n  __name__: %s' % (
        ...         e.object, e.object.__parent__, e.object.__name__)

        >>> provideHandler(onMoved, [IObjectMovedEvent])

    This evolution script locates several objects in gradebook root.

        >>> evolve(context)
        Moved GradebookTemplates(u'Report Sheet Templates')
          __parent__: <...GradebookRoot_gen2 ...>
          __name__: templates
        Moved GradebookDeployed(u'Deployed Report Sheets')
          __parent__: <...GradebookRoot_gen2 ...>
          __name__: deployed
        Moved GradebookLayouts(u'Report Card Layouts')
          __parent__: <...GradebookRoot_gen2 ...>
          __name__: layouts

    """


def setUp(test):
    setup.placelessSetUp()
    setup.setUpTraversal()

def tearDown(test):
    setup.placelessTearDown()


def test_suite():
    return unittest.TestSuite([
        doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                             optionflags=doctest.ELLIPSIS
                                         | doctest.NORMALIZE_WHITESPACE
                                         | doctest.REPORT_NDIFF
                                         | doctest.REPORT_ONLY_FIRST_FAILURE),
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
