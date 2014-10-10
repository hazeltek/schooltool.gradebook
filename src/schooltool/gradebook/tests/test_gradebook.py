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
Gradebook-related Tests
"""
import unittest, doctest
from pprint import pprint

from transaction import abort
from zope.app.testing import setup
from zope.component import provideAdapter, provideUtility
from zope.container.btree import BTreeContainer
from zope.interface import classImplements
from zope.interface import Interface

from schooltool.course.interfaces import ICourse, ISection
from schooltool.person.person import Person
from schooltool.requirement import testing
from schooltool.requirement import evaluation
from schooltool.requirement.interfaces import IHaveEvaluations
from schooltool.requirement.interfaces import IEvaluations
from schooltool.term.interfaces import IDateManager
from schooltool.testing.setup import getIntegrationTestZCML
from schooltool.testing.stubs import AppStub

from schooltool.gradebook import activity, gradebook, interfaces
from schooltool.gradebook import category
from schooltool.gradebook.tests import stubs


def setUp(test):
    setup.placefulSetUp()
    provideAdapter(evaluation.getEvaluations,
                   (Interface,),
                   IEvaluations)
    testing.fixDecimal()

    provideAdapter(
        activity.getSectionActivities,
        (ISection,), interfaces.IActivities)
    provideAdapter(
        activity.getCourseActivities,
        (ICourse,), interfaces.ICourseActivities)
    provideAdapter(
        activity.getCourseDeployedWorksheets,
        (ICourse,), interfaces.ICourseDeployedWorksheets)

    provideAdapter(gradebook.Gradebook)

    provideAdapter(category.getCategories)

    provideAdapter(
        stubs.SomeProductStub,
        (ISection,), interfaces.IExternalActivities,
        name=u"someproduct")

    provideAdapter(
        stubs.ThirdPartyStub,
        (ISection,), interfaces.IExternalActivities,
        name=u"thirdparty")

    classImplements(Person, IHaveEvaluations)

    provideAdapter(gradebook.getActivityScore)
    provideAdapter(gradebook.getLinkedActivityScore)
    provideAdapter(gradebook.getWorksheetAverageScore)  

    provideUtility(stubs.DateManagerStub(), IDateManager, '')
    zcml = getIntegrationTestZCML()
    zcml.include('schooltool.schoolyear', file='schoolyear.zcml')
    app = test.globs['app'] = AppStub()
    app['persons'] = BTreeContainer()
    app['courses'] = BTreeContainer()
    app['sections'] = BTreeContainer()


def tearDown(test):
    setup.placefulTearDown()
    abort()


def test_suite():
    optionflags=(doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS|
                 doctest.REPORT_ONLY_FIRST_FAILURE)
    return unittest.TestSuite((
        doctest.DocFileSuite('../README.txt',
                             setUp=setUp, tearDown=tearDown,
                             globs={'pprint': pprint},
                             optionflags=optionflags),
        ))

if __name__ == '__main__':
    unittest.main(default='test_suite')
