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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Unit tests for schooltool.gradebook.generations.evolve5
"""

import unittest, doctest
import datetime

from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup
from zope.component import provideHandler
from zope.interface import implements
from zope.lifecycleevent.interfaces import IObjectMovedEvent
from zope.site import LocalSiteManager

from schooltool.course.section import Section
from schooltool.schoolyear.schoolyear import SchoolYearContainer, SchoolYear
from schooltool.schoolyear.schoolyear import SCHOOLYEAR_CONTAINER_KEY
from schooltool.term.term import Term

from schooltool.gradebook.activity import Worksheet
from schooltool.gradebook.generations.tests import ContextStub
from schooltool.gradebook.generations.tests import provideAdapters
from schooltool.gradebook.generations.evolve5 import evolve
from schooltool.gradebook.gradebook_init import (GRADEBOOK_ROOT_KEY,
    GradebookRoot, ReportLayout, ReportColumn, OutlineActivity)
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities

from schooltool.gradebook import GradebookMessage as _


def doctest_evolve5():
    r"""Evolution to generation 5.

    First, we'll set up the app object:

        >>> provideAdapters()
        >>> context = ContextStub()
        >>> app = getRootFolder(context)
        >>> app.setSiteManager(LocalSiteManager(app))

    Next, we'll set up the year object with a couple terms:

        >>> years = app[SCHOOLYEAR_CONTAINER_KEY] = SchoolYearContainer()
        >>> year = years['2011'] = SchoolYear('2011',
        ...                                   datetime.date(2011, 1, 1),
        ...                                   datetime.date(2011, 12, 31))
        >>> term1 = year['term1'] = Term('Term1',
        ...                              datetime.date(2011, 1, 1),
        ...                              datetime.date(2011, 6, 30))
        >>> term2 = year['term2'] = Term('Term2',
        ...                              datetime.date(2011, 7, 1),
        ...                              datetime.date(2011, 12, 31))

    We'll set up a second year for which there is no other data to test
    that the evolve script can handle that.

        >>> years['2012'] = SchoolYear('2012',
        ...                            datetime.date(2012, 1, 1),
        ...                            datetime.date(2012, 12, 31))

    Add some sections to each term.

        >>> section1 = Section('Section1')
        >>> section2 = Section('Section2')
        >>> sections = {'1': section1, '2': section2}
        >>> app['schooltool.course.section'] = {'2011': sections}

    And add the gradebook root.

        >>> root = app[GRADEBOOK_ROOT_KEY] = GradebookRoot()

    Deploy some report sheets.

        >>> root.deployed[u'2011_term1'] = Worksheet('Sheet1')
        >>> root.deployed[u'2011_term1-2'] = Worksheet('Sheet2')
        >>> IActivities(section1)[u'2011_term1'] = Worksheet('Sheet1')
        >>> IActivities(section2)[u'2011_term1-2'] = Worksheet('Sheet2')

    Layout the report card.

        >>> layout = root.layouts[u'2011'] = ReportLayout()
        >>> layout.columns = [
        ...     ReportColumn('term1|2011_term1|1', ''),
        ...     ReportColumn('term1|2011_term1-2|1', '')]
        >>> layout.outline_activities = [
        ...     OutlineActivity('term1|2011_term1|1', ''),
        ...     OutlineActivity('term1|2011_term1-2|1', '')]

    This evolution script changes the keys of the deployed report sheets.

        >>> sorted([key for key in root.deployed])
        [u'2011_term1', u'2011_term1-2']
        >>> sorted([key for key in IActivities(section1)])
        [u'2011_term1']
        >>> sorted([key for key in IActivities(section2)])
        [u'2011_term1-2']
        >>> [column.source for column in layout.columns]
        ['term1|2011_term1|1', 'term1|2011_term1-2|1']
        >>> [activity.source for activity in layout.outline_activities]
        ['term1|2011_term1|1', 'term1|2011_term1-2|1']


        >>> evolve(context)

        >>> sorted([key for key in root.deployed])
        [u'2011_term1_1', u'2011_term1_2']
        >>> sorted([key for key in IActivities(section1)])
        [u'2011_term1_1']
        >>> sorted([key for key in IActivities(section2)])
        [u'2011_term1_2']
        >>> [column.source for column in layout.columns]
        [u'term1|2011_term1_1|1', u'term1|2011_term1_2|1']
        >>> [activity.source for activity in layout.outline_activities]
        [u'term1|2011_term1_1|1', u'term1|2011_term1_2|1']

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
