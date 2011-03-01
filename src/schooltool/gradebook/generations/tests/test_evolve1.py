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
Unit tests for schooltool.gradebook.generations.evolve1
"""

import unittest, doctest

from zope.app.generations.utility import getRootFolder

from schooltool.gradebook.generations.tests import ContextStub
from schooltool.gradebook.generations.tests import provideAdapters
from schooltool.gradebook.generations.tests import provideUtilities
from schooltool.gradebook.generations.evolve1 import evolve


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

        >>> from schooltool.person.person import PersonContainer, Person
        >>> app['persons'] = PersonContainer()
        >>> student = Person('student')
        >>> app['persons']['student'] = student

        >>> from schooltool.course.section import SectionContainerContainer
        >>> from schooltool.course.section import SectionContainer, Section
        >>> app['schooltool.course.section'] = SectionContainerContainer()
        >>> app['schooltool.course.section']['1'] = SectionContainer()
        >>> section = Section('section')
        >>> app['schooltool.course.section']['1']['1'] = section

        >>> from schooltool.gradebook.gradebook_init import setUpGradebookRoot
        >>> from schooltool.gradebook.interfaces import IGradebookRoot
        >>> setUpGradebookRoot(app)
        >>> root = IGradebookRoot(app)

        >>> from schooltool.requirement.scoresystem import PassFail
        >>> from schooltool.requirement.scoresystem import AmericanLetterScoreSystem
        >>> from schooltool.gradebook.activity import ReportWorksheet
        >>> from schooltool.gradebook.activity import ReportActivity
        >>> root.templates['1'] = temp_ws = ReportWorksheet('1')
        >>> temp_ws['1'] = temp_act = ReportActivity('1', None, PassFail)
        >>> root.deployed['1'] = dep_ws = ReportWorksheet('1')
        >>> dep_ws['1'] = dep_act = ReportActivity('1', None, AmericanLetterScoreSystem)

        >>> from schooltool.gradebook.interfaces import IActivities
        >>> activities = IActivities(section)

        >>> from schooltool.requirement.scoresystem import ExtendedAmericanLetterScoreSystem
        >>> from schooltool.gradebook.activity import Worksheet, Activity
        >>> activities['1'] = worksheet = Worksheet('1')
        >>> worksheet['1'] = activity = Activity('1', None, ExtendedAmericanLetterScoreSystem)

        >>> from schooltool.requirement.interfaces import IHaveEvaluations
        >>> from schooltool.requirement.interfaces import IEvaluations
        >>> from zope.interface import alsoProvides
        >>> alsoProvides(student, IHaveEvaluations)
        >>> evaluations = IEvaluations(student)

        >>> from schooltool.requirement.evaluation import Evaluation
        >>> ev = Evaluation(activity, ExtendedAmericanLetterScoreSystem, 'A+', None)
        >>> evaluations.addEvaluation(ev)

    Finally, we'll run the evolve script, testing the effected values before and
    after:

        >>> from schooltool.requirement.interfaces import IScoreSystemsProxy
        >>> proxy = IScoreSystemsProxy(app)
        >>> proxy.getScoreSystems()
        []

        >>> temp_act.scoresystem
        <GlobalDiscreteValuesScoreSystem u'Pass/Fail'>
        >>> dep_act.scoresystem
        <GlobalDiscreteValuesScoreSystem u'Letter Grade'>
        >>> activity.scoresystem
        <GlobalDiscreteValuesScoreSystem u'Extended Letter Grade'>
        >>> ev.scoreSystem
        <GlobalDiscreteValuesScoreSystem u'Extended Letter Grade'>

        >>> evolve(context)

        >>> proxy.getScoreSystems()
        [(u'Extended Letter Grade', <CustomScoreSystem u'Extended Letter Grade'>),
         (u'Letter Grade', <CustomScoreSystem u'Letter Grade'>),
         (u'Pass/Fail', <CustomScoreSystem u'Pass/Fail'>)]

        >>> temp_act.scoresystem
        <CustomScoreSystem u'Pass/Fail'>
        >>> dep_act.scoresystem
        <CustomScoreSystem u'Letter Grade'>
        >>> activity.scoresystem
        <CustomScoreSystem u'Extended Letter Grade'>
        >>> ev.scoreSystem
        <CustomScoreSystem u'Extended Letter Grade'>
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

