#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2005 Shuttleworth Foundation
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
Level-related Tests
"""

__docformat__ = 'restructuredtext'

import unittest, doctest
from pprint import pprint

from zope.app.testing import setup

from schooltool.requirement import testing

def setUp(test):
    setup.placefulSetUp()
    testing.setUpRequirement()
    testing.setUpScoreSystem()
    testing.setUpEvaluation()
    testing.fixDecimal()


def tearDown(test):
    setup.placefulTearDown()


def test_suite():
    return unittest.TestSuite((
        doctest.DocFileSuite('README.txt',
                             setUp=setUp, tearDown=tearDown,
                             globs={'pprint': pprint},
                             optionflags=doctest.NORMALIZE_WHITESPACE|
                                         doctest.ELLIPSIS|
                                         doctest.REPORT_ONLY_FIRST_FAILURE),
        doctest.DocFileSuite('grades.txt',
                             setUp=setUp, tearDown=tearDown,
                             globs={'pprint': pprint},
                             optionflags=doctest.NORMALIZE_WHITESPACE|
                                         doctest.ELLIPSIS|
                                         doctest.REPORT_ONLY_FIRST_FAILURE),
        ))

if __name__ == '__main__':
    unittest.main(default='test_suite')
