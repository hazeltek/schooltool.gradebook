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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Tests for SchoolTool gradebook pdf views.

"""

import unittest
from pprint import pprint
from datetime import datetime

from zope.annotation.interfaces import IAttributeAnnotatable
from zope.intid.interfaces import IIntIds
from zope.keyreference.interfaces import IKeyReference
from zope.app.testing import setup
from zope.component import getUtility, provideAdapter, provideUtility
from zope.interface import implements
from zope.publisher.browser import TestRequest
from zope.security.proxy import removeSecurityProxy
from zope.testing import doctest

from schooltool.app.interfaces import (ISchoolToolApplication,
     ISchoolToolCalendar, ISchoolToolCalendarEvent)
from schooltool.app.cal import getCalendar
from schooltool.basicperson.interfaces import IBasicPerson
from schooltool.basicperson.person import BasicPerson
from schooltool.course.course import (CourseContainerContainer, Course,
    getCourseContainer)
from schooltool.course.interfaces import (ILearner, ISectionContainer, ISection,
    ICourseContainer)
from schooltool.course.section import (Section, SectionContainerContainer,
    getSectionContainer, PersonLearnerAdapter, getTermForSection,
    getTermForSectionContainer)
from schooltool.group.group import (GroupContainerContainer, Group,
     getGroupContainer)
from schooltool.group.interfaces import IGroupContainer
from schooltool.person.person import PersonContainer
from schooltool.relationship.tests import setUpRelationships
from schooltool.schoolyear.interfaces import ISchoolYear, ISchoolYearContainer
from schooltool.schoolyear.schoolyear import (SchoolYear, SchoolYearContainer,
    SCHOOLYEAR_CONTAINER_KEY, getSchoolYearContainer)
from schooltool.term.interfaces import ITerm, IDateManager
from schooltool.term.term import Term, getSchoolYearForTerm

from schooltool.gradebook.activity import (Worksheet, Activity,
    getSectionActivities)
from schooltool.gradebook.gradebook import Gradebook 
from schooltool.gradebook.gradebook_init import (setUpGradebookRoot, 
    getGradebookRoot, ReportLayout, ReportColumn, OutlineActivity)
from schooltool.gradebook.interfaces import (IGradebookRoot, IGradebook,
    IActivities, IWorksheet)
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.lyceum.journal.journal import (LyceumJournalContainer,
    getSectionJournalData, getSectionForSectionJournalData)
from schooltool.gradebook.browser.pdf_views import (StudentReportCardPDFView,
    GroupReportCardPDFView, StudentDetailPDFView, GroupDetailPDFView,
    FailingReportPDFView, AbsencesByDayPDFView, SectionAbsencesPDFView)
from schooltool.requirement.evaluation import Evaluation, getEvaluations
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.scoresystem import AmericanLetterScoreSystem


BEGIN_2009 = datetime.date(datetime(2009, 1, 1))
END_2009 = datetime.date(datetime(2009, 12, 31))


aelkner = BasicPerson('aelkner', 'Alan', 'Elkner')
thoffman = BasicPerson('thoffman', 'Tom', 'Hoffman')


_d = {}

class StupidKeyReference(object):
    implements(IKeyReference)
    key_type_id = 'StupidKeyReference'

    def __init__(self, ob):
        global _d
        self.id = id(ob)
        _d[self.id] = ob

    def __call__(self):
        return _d[self.id]

    def __hash__(self):
        return self.id

    def __cmp__(self, other):
        return cmp(hash(self), hash(other))


class MeetingStub(object):
    implements(ISchoolToolCalendarEvent)

    __parent__ = None
    resources = []


_int_ids = {}

class IntIdsStub(object):
    implements(IIntIds)

    def getObject(self, id):
        return _int_ids[id]

    def getId(self, obj):
        key = IKeyReference(obj)
        return key.__hash__()

    def register(self, obj):
        ob = removeSecurityProxy(obj)
        key = IKeyReference(obj).__hash__()
        if key not in _int_ids:
            _int_ids[key] = obj
        return key


class ApplicationStub(object):
    implements(ISchoolToolApplication, IAttributeAnnotatable)

    def __init__(self):
        int_ids = getUtility(IIntIds)

        self.dict = {}
        self.syc = self.dict[SCHOOLYEAR_CONTAINER_KEY] = SchoolYearContainer()
        self.dict['schooltool.course.course'] = CourseContainerContainer()
        self.dict['schooltool.course.section'] = SectionContainerContainer()
        self.dict['schooltool.lyceum.journal'] = LyceumJournalContainer()
        self.dict['schooltool.group'] = GroupContainerContainer()
        self.dict['persons'] = PersonContainer()

        self.dict['persons']['aelkner'] = aelkner
        self.dict['persons']['thoffman'] = thoffman

        self.schoolyear = self.syc['2009'] = SchoolYear('2009', BEGIN_2009,
            END_2009)
        self.term = self.schoolyear['term'] = Term('Term', BEGIN_2009,
            END_2009)
        int_ids.register(self.term)

        setUpGradebookRoot(self)
        root = IGradebookRoot(self)

        worksheet = root.deployed['Worksheet'] = Worksheet('Worksheet')
        worksheet['Activity'] = Activity('Activity', 'exam',
            AmericanLetterScoreSystem)

        source = 'Term|Worksheet|Activity'
        layout = root.layouts[self.schoolyear.__name__] = ReportLayout()
        layout.columns = [ReportColumn(source, '')]
        layout.outline_activities = [OutlineActivity(source, '')]

    def __getitem__(self, key):
        return self.dict[key]

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __contains__(self, key):
        return key in self.dict


class DateManagerStub(object):
    implements(IDateManager)

    def __init__(self):
        app = ISchoolToolApplication(None)
        self.current_term = app[SCHOOLYEAR_CONTAINER_KEY]['2009']['term']


def setupSections(app):
    int_ids = getUtility(IIntIds)

    courses = ICourseContainer(app.schoolyear)
    courses['1'] = course1 = Course('Course 1')

    groups = IGroupContainer(app.schoolyear)
    groups['students'] = students = Group('Students')
    students.members.add(aelkner)

    sections = ISectionContainer(app.term)
    int_ids.register(sections)

    section1 = Section('Section 1')
    int_ids.register(section1)
    section1.courses.add(course1)
    section1.instructors.add(thoffman)
    section1.members.add(aelkner)
    sections['1'] = section1

    ss = AmericanLetterScoreSystem
    activities = IActivities(section1)
    worksheet = activities['Worksheet'] = Worksheet('Worksheet')
    activity = worksheet['Activity'] = Activity('Activity', 'exam', ss)

    evaluations = IEvaluations(aelkner)
    evaluation = Evaluation(activity, ss, 'F', thoffman)
    evaluations.addEvaluation(evaluation)

    jd = ISectionJournalData(section1)
    calendar = ISchoolToolCalendar(section1)
    meeting = MeetingStub()
    meeting.unique_id = "unique-id-2009-01-01"
    meeting.dtstart = datetime(2009, 1, 1, 10, 15)
    meeting.period_id = "10:30-11:30"
    calendar.addEvent(meeting)
    jd.setGrade(aelkner, meeting, 'n')
    jd.setAbsence(aelkner, meeting, 'n')


def doctest_StudentReportCardPDFView():
    r"""Tests for StudentReportCardPDFView.

        >>> request = TestRequest()
        >>> view = StudentReportCardPDFView(aelkner, request)

    The view has a title:

        >>> print view.title()
        Report Card: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'grid': {'headings': ['Activ'],
                   'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                   'widths': '8.2cm,1.6cm'},
          'outline': [{'heading': 'Section 1',
                       'worksheets': [{'activities': [{'heading': 'Activity',
                                                       'value': [u'F']}],
                                       'heading': 'Worksheet',
                                       'name': 'Worksheet'}]}],
          'title': u'Student: Alan Elkner'}]
    """


def doctest_GroupReportCardPDFView():
    r"""Tests for GroupReportCardPDFView.

        >>> request = TestRequest()
        >>> app = ISchoolToolApplication(None)
        >>> groups = IGroupContainer(app.schoolyear)
        >>> students = groups['students']
        >>> view = GroupReportCardPDFView(students, request)

    The view has a title:

        >>> print view.title()
        Report Card: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'grid': {'headings': ['Activ'],
                   'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                   'widths': '8.2cm,1.6cm'},
          'outline': [{'heading': 'Section 1',
                       'worksheets': [{'activities': [{'heading': 'Activity',
                                                       'value': [u'F']}],
                                       'heading': 'Worksheet',
                                       'name': 'Worksheet'}]}],
          'title': u'Student: Alan Elkner'}]
    """


def doctest_StudentDetailPDFView():
    r"""Tests for StudentDetailPDFView.

        >>> request = TestRequest()
        >>> view = StudentDetailPDFView(aelkner, request)

    The view has a title:

        >>> print view.title()
        Detailed Student Report: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'attendance': {'headings': ['10:30'],
                         'rows': [{'scores': [u'A'], 'title': '01/01/09'}],
                         'widths': '4cm,1cm'},
          'grades': {'headings': ['Activ'],
                     'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                     'widths': '8.2cm,1.6cm'},
          'name': u'Alan Elkner',
          'userid': 'aelkner'}]
    """


def doctest_GroupDetailPDFView():
    r"""Tests for GroupDetailPDFView.

        >>> request = TestRequest()
        >>> app = ISchoolToolApplication(None)
        >>> groups = IGroupContainer(app.schoolyear)
        >>> students = groups['students']
        >>> view = GroupDetailPDFView(students, request)

    The view has a title:

        >>> print view.title()
        Detailed Student Report: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'attendance': {'headings': ['10:30'],
                         'rows': [{'scores': [u'A'], 'title': '01/01/09'}],
                         'widths': '4cm,1cm'},
          'grades': {'headings': ['Activ'],
                     'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                     'widths': '8.2cm,1.6cm'},
          'name': u'Alan Elkner',
          'userid': 'aelkner'}]
    """


def doctest_FailingReportPDFView():
    r"""Tests for FailingReportPDFView.

        >>> request = TestRequest()
        >>> app = ISchoolToolApplication(None)
        >>> request.form['activity'] = 'Term|Worksheet|Activity'
        >>> request.form['min'] = 'D'
        >>> view = FailingReportPDFView(app.term, request)

    The view has a title:

        >>> print view.title()
        Failures by Term Report: Term

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'name': 'Alan Elkner',
          'rows': [{'course': 'Course 1', 'grade': 'F', 'teacher': 'Tom Hoffman'}]}]
    """


def doctest_AbsencesByDayPDFView():
    r"""Tests for AbsencesByDayPDFView.

        >>> request = TestRequest()
        >>> app = ISchoolToolApplication(None)
        >>> tod = datetime(2009, 1, 1, 10, 15)
        >>> request.form['day'] = '%d-%02d-%02d' % (tod.year,
        ...    tod.month, tod.day)
        >>> view = AbsencesByDayPDFView(app.schoolyear, request)

    The view has a title:

        >>> print view.title()
        Absences By Day Report

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'name': 'Alan Elkner', 'periods': [u'A']}]
    """


def doctest_SectionAbsencesPDFView():
    r"""Tests for SectionAbsencesPDFView.

        >>> request = TestRequest()
        >>> app = ISchoolToolApplication(None)
        >>> sections = ISectionContainer(app.term)
        >>> view = SectionAbsencesPDFView(sections['1'], request)

    The view has a title:

        >>> print view.title()
        Absences by Section Report

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'absences': 1, 'name': 'Alan Elkner', 'tardies': 0, 'total': 1}]
    """


def pdfSetUp(test=None):
    setup.placefulSetUp()
    setUpRelationships()

    provideAdapter(getSchoolYearForTerm, [ITerm], provides=ISchoolYear)
    provideAdapter(getSectionContainer, [ITerm], provides=ISectionContainer)

    provideAdapter(getCourseContainer, [ISchoolYear], provides=ICourseContainer)
    provideAdapter(getGroupContainer, [ISchoolYear], provides=IGroupContainer)

    provideAdapter(PersonLearnerAdapter, [IBasicPerson], provides=ILearner)
    provideAdapter(getEvaluations, [IBasicPerson], provides=IEvaluations)

    provideAdapter(getTermForSectionContainer, [ISectionContainer],
                   provides=ITerm)
    provideAdapter(getSectionActivities, [ISection], provides=IActivities)
    provideAdapter(getTermForSection, [ISection], provides=ITerm)
    provideAdapter(getSectionJournalData, [ISection],
                   provides=ISectionJournalData)
    provideAdapter(getSectionForSectionJournalData, [ISectionJournalData],
                   provides=ISection)

    provideAdapter(getGradebookRoot, [ISchoolToolApplication],
                   provides=IGradebookRoot)
    provideAdapter(Gradebook, [IWorksheet], provides=IGradebook)
    provideAdapter(getSchoolYearContainer, [ISchoolToolApplication], 
                   provides=ISchoolYearContainer)

    provideAdapter(StupidKeyReference, [object], IKeyReference)
    provideUtility(IntIdsStub(), IIntIds, '')

    provideAdapter(getCalendar, [object], provides=ISchoolToolCalendar)

    app = ApplicationStub()
    provideAdapter(lambda x: app, [None], provides=ISchoolToolApplication)

    provideUtility(DateManagerStub(), IDateManager, '')

    setupSections(app)


def pdfTearDown(test=None):
    setup.placefulTearDown()


def test_suite():
    from schooltool.app.tests.test_pdf import tryToSetUpReportLab
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite('schooltool.app.browser.pdfcal'))
    success = tryToSetUpReportLab()
    if success:
        optionflags = (doctest.ELLIPSIS | doctest.REPORT_NDIFF
                       | doctest.NORMALIZE_WHITESPACE
                       | doctest.REPORT_ONLY_FIRST_FAILURE)
        docsuite = doctest.DocTestSuite(setUp=pdfSetUp, tearDown=pdfTearDown,
                                        optionflags=optionflags)
        suite.addTest(docsuite)
    else:
        import sys
        print >> sys.stderr, ("reportlab or TrueType fonts not found;"
                              " PDF generator tests skipped")

    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
