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

import unittest, doctest
from decimal import Decimal
from pprint import pprint
from datetime import datetime

from zope.annotation.interfaces import IAttributeAnnotatable
from zope.intid.interfaces import IIntIds
from zope.keyreference.interfaces import IKeyReference
from zope.app.testing import setup
from zope.component import getUtility, provideAdapter, provideUtility
from zope.component import adapter
from zope.container import btree
from zope.interface import implements, alsoProvides, classImplements
from zope.location.interfaces import ILocation
from zope.location.location import locate
from zope.publisher.browser import TestRequest
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.schema.interfaces import IVocabularyFactory
from zope.security.proxy import removeSecurityProxy
from zope.traversing.browser.interfaces import IAbsoluteURL
from zope.ucol.localeadapter import LocaleCollator
from zope.i18n.interfaces.locales import ICollator
from zope.i18n import translate

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
from schooltool.gradebook.gradebook import (
    getActivityScore,
    getLinkedActivityScore,
    getWorksheetAverageScore,
    )
from schooltool.gradebook.gradebook import (Gradebook, getWorksheetSection,
    getGradebookSection)
from schooltool.gradebook.gradebook_init import (setUpGradebookRoot, 
    getGradebookRoot, ReportLayout, ReportColumn, OutlineActivity)
from schooltool.gradebook.interfaces import (IGradebookRoot, IGradebook,
    IActivities, IWorksheet, ISectionJournalData)
from schooltool.lyceum.journal.journal import LyceumJournalContainer
from schooltool.gradebook.browser.pdf_views import (StudentReportCardPDFView,
    GroupReportCardPDFView, StudentDetailPDFView, GroupDetailPDFView,
    FailingReportPDFView, AbsencesByDayPDFView, SectionAbsencesPDFView,
    GradebookPDFView)
from schooltool.requirement.evaluation import Evaluation, getEvaluations
from schooltool.requirement.interfaces import (IScoreSystemContainer,
    IEvaluations, IHaveEvaluations)
from schooltool.requirement.scoresystem import (AmericanLetterScoreSystem,
    DiscreteScoreSystemsVocabulary, DiscreteValuesScoreSystem,
    getScoreSystemContainer, ScoreSystemAppStartup)


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


class PeriodStub(object):
    def __init__(self, title):
        self.title = title


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


class FakeURL:
    def __init__(self, context, request):
        pass
    def __call__(self):
        return self.__str__()
    def __str__(self):
        return "http://localhost"


class ApplicationStub(btree.BTreeContainer):
    implements(ISchoolToolApplication, IAttributeAnnotatable)

    def __init__(self):
        super(ApplicationStub, self).__init__()
        int_ids = getUtility(IIntIds)

        self.syc = self[SCHOOLYEAR_CONTAINER_KEY] = SchoolYearContainer()
        self['schooltool.course.course'] = CourseContainerContainer()
        self['schooltool.course.section'] = SectionContainerContainer()
        self['schooltool.lyceum.journal'] = LyceumJournalContainer()
        self['schooltool.group'] = GroupContainerContainer()
        self['persons'] = PersonContainer()

        self['persons']['aelkner'] = aelkner
        self['persons']['thoffman'] = thoffman

        self.schoolyear = self.syc['2009'] = SchoolYear('2009', BEGIN_2009,
            END_2009)
        self.term = self.schoolyear['term'] = Term('Term', BEGIN_2009,
            END_2009)
        int_ids.register(self.term)

        setUpGradebookRoot(self)
        ScoreSystemAppStartup(self)()


class DateManagerStub(object):
    implements(IDateManager)

    def __init__(self):
        app = ISchoolToolApplication(None)
        self.current_term = app[SCHOOLYEAR_CONTAINER_KEY]['2009']['term']
        self.today = BEGIN_2009


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

    scores = [
        ('A', u'', Decimal(4), Decimal(75)),
        ('B', u'', Decimal(3), Decimal(50)),
        ('C', u'', Decimal(2), Decimal(25)),
        ('D', u'', Decimal(1), Decimal(0)),
        ]
    maxss = DiscreteValuesScoreSystem('Max', '', scores, 'A', 'C', True)
    activity2 = worksheet['Activity-2'] = Activity('Activity 2', 'max', maxss)

    evaluations = IEvaluations(aelkner)
    evaluation = Evaluation(activity, ss, 'F', thoffman)
    evaluations.addEvaluation(evaluation)
    evaluation = Evaluation(activity2, maxss, 'C', thoffman)
    evaluations.addEvaluation(evaluation)

    jd = ISectionJournalData(section1)
    calendar = ISchoolToolCalendar(section1)
    meeting = MeetingStub()
    meeting.unique_id = "unique-id-2009-01-01"
    meeting.meeting_id = "unique-id-2009-01-01"
    meeting.dtstart = datetime(2009, 1, 1, 10, 15)
    meeting.period = PeriodStub("Period A")
    calendar.addEvent(meeting)
    if jd:
        jd.setGrade(aelkner, meeting, 'n')


def setupGradebook(app):
    root = IGradebookRoot(app)

    worksheet = root.deployed['Worksheet'] = Worksheet('Worksheet')
    worksheet['Activity'] = Activity('Activity', 'exam',
                                     AmericanLetterScoreSystem)

    scores = [
        ('A', u'', Decimal(4), Decimal(75)),
        ('B', u'', Decimal(3), Decimal(50)),
        ('C', u'', Decimal(2), Decimal(25)),
        ('D', u'', Decimal(1), Decimal(0)),
        ]
    maxss = DiscreteValuesScoreSystem('Max', '', scores, 'A', 'C', True)
    worksheet['Activity-2'] = Activity('Activity 2', 'max', maxss)

    source = 'Term|Worksheet|Activity'
    layout = root.layouts[app.schoolyear.__name__] = ReportLayout()
    layout.columns = [ReportColumn(source, '')]
    layout.outline_activities = [OutlineActivity(source, '')]


def doctest_StudentReportCardPDFView():
    r"""Tests for StudentReportCardPDFView.

        >>> request = TestRequest()
        >>> view = StudentReportCardPDFView(aelkner, request)

    The view has a title:

        >>> print translate(view.title(), context=request)
        Report Card: 2009

    The data used by the template is returned by the students() method:

        >>> students = view.students()
        >>> for student in students:
        ...     student['title'] = translate(student['title'], context=request)
        >>> pprint(students)
        [{'grid': {'headings': ['Activ'],
                   'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                   'widths': '8.2cm,1.6cm'},
          'outline': [{'heading': 'Term - Section 1',
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

        >>> print translate(view.title(), context=request)
        Report Card: 2009

    The data used by the template is returned by the students() method:

        >>> students = view.students()
        >>> for student in students:
        ...     student['title'] = translate(student['title'], context=request)
        >>> pprint(students)
        [{'grid': {'headings': ['Activ'],
                   'rows': [{'scores': [u'F'], 'title': 'Course 1 (Tom Hoffman)'}],
                   'widths': '8.2cm,1.6cm'},
          'outline': [{'heading': 'Term - Section 1',
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

        >>> print translate(view.title(), context=request)
        Detailed Student Report: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'attendance': {'headings': ['Period A'],
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

        >>> print translate(view.title(), context=request)
        Detailed Student Report: 2009

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'attendance': {'headings': ['Period A'],
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

        >>> print translate(view.title(), context=request)
        Failures by Term Report: Term

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'name': 'Alan Elkner',
          'rows': [{'course': 'Course 1', 'grade': 'F', 'teacher': 'Tom Hoffman'}]}]

    If we specify a minumum passing score of 'F', nothing will fail.
    
        >>> request.form['min'] = 'F'
        >>> view = FailingReportPDFView(app.term, request)
        >>> pprint(view.students())
        []

    For the max passing score system activity, specifying a higher max passing
    score will result in more failures.

        >>> request.form['activity'] = 'Term|Worksheet|Activity-2'

        >>> request.form['min'] = 'B'
        >>> view = FailingReportPDFView(app.term, request)
        >>> pprint(view.students())
        []

        >>> request.form['min'] = 'C'
        >>> view = FailingReportPDFView(app.term, request)
        >>> pprint(view.students())
        []

        >>> request.form['min'] = 'D'
        >>> view = FailingReportPDFView(app.term, request)
        >>> pprint(view.students())
        [{'name': 'Alan Elkner',
          'rows': [{'course': 'Course 1', 'grade': 'C', 'teacher': 'Tom Hoffman'}]}]
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

        >>> print translate(view.title(), context=request)
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

        >>> print translate(view.title(), context=request)
        Absences by Section Report

    The data used by the template is returned by the students() method:

        >>> pprint(view.students())
        [{'absences': 1, 'name': 'Alan Elkner', 'tardies': 0, 'total': 1}]
    """


def doctest_GradebookPDFView():
    r"""Tests for GradebookPDFView.

        >>> request = TestRequest()
        >>> request.setPrincipal(thoffman)
        >>> app = ISchoolToolApplication(None)
        >>> section = ISectionContainer(app.term)['1']
        >>> activities = IActivities(section)
        >>> worksheet = activities['Worksheet']
        >>> gradebook = IGradebook(worksheet)
        >>> locate(gradebook, worksheet, 'gradebook')
        >>> alsoProvides(gradebook, ILocation)
        >>> view = GradebookPDFView(gradebook, request)

    The view has a title:

        >>> print translate(view.title(), context=request)
        Gradebook Report

    The data used by the template is returned by the table() method:

        >>> pprint(view.activities())
        [{'canDelete': True,
          'hash': 'Activity',
          'longTitle': 'Activity',
          'max': 'A',
          'moveLeft': False,
          'moveRight': True,
          'scorable': True,
          'shortTitle': 'Activ',
          'updateGrades': ''},
         {'canDelete': True,
          'hash': 'Activity-2',
          'longTitle': 'Activity 2',
          'max': 'A',
          'moveLeft': True,
          'moveRight': False,
          'scorable': True,
          'shortTitle': 'Activ',
          'updateGrades': ''}]

        >>> pprint(view.table())
        [{'absences': u'0',
          'average': '14.3%',
          'grades': [{'activity': 'Activity', 'editable': True, 'value': 'F'},
                     {'activity': 'Activity-2', 'editable': True, 'value': 'C'}],
          'raw_average': Decimal('14.28571428571428571428571429'),
          'student': {'gradeurl': 'http://localhost/schooltool.course.section/.../1/activities/Worksheet/gradebook/aelkner',
                      'id': 'aelkner',
                      'title': 'Elkner, Alan',
                      'url': 'http://localhost/persons/aelkner'},
          'tardies': u'0',
          'total': '1.0'}]
    """


def pdfSetUp(test=None):
    setup.placefulSetUp()
    setUpRelationships()

    provideAdapter(getSchoolYearForTerm, [ITerm], provides=ISchoolYear)
    provideAdapter(getSectionContainer, [ITerm], provides=ISectionContainer)

    provideAdapter(getCourseContainer, [ISchoolYear], provides=ICourseContainer)
    provideAdapter(getGroupContainer, [ISchoolYear], provides=IGroupContainer)

    provideAdapter(PersonLearnerAdapter, [IBasicPerson], provides=ILearner)
    classImplements(BasicPerson, IHaveEvaluations)
    provideAdapter(getEvaluations, [IBasicPerson], provides=IEvaluations)

    provideAdapter(getTermForSectionContainer, [ISectionContainer],
                   provides=ITerm)
    provideAdapter(getSectionActivities, [ISection], provides=IActivities)
    provideAdapter(getTermForSection, [ISection], provides=ITerm)

    from schooltool.gradebook.interfaces import ISectionJournalData
    from schooltool.gradebook.journal import getSectionJournalData
    provideAdapter(getSectionJournalData, [ISection],
                   provides=ISectionJournalData)

    from schooltool.lyceum.journal.interfaces import ISectionJournalData
    from schooltool.lyceum.journal.journal import getSectionJournalData
    from schooltool.lyceum.journal.journal import getSectionForSectionJournalData
    provideAdapter(getSectionJournalData, [ISection],
                   provides=ISectionJournalData)
    provideAdapter(getSectionForSectionJournalData, [ISectionJournalData],
                   provides=ISection)

    provideAdapter(getGradebookRoot, [ISchoolToolApplication],
                   provides=IGradebookRoot)
    provideAdapter(Gradebook, [IWorksheet], provides=IGradebook)
    provideAdapter(getWorksheetSection, [IWorksheet], provides=ISection)
    provideAdapter(getGradebookSection, [IGradebook], provides=ISection)
    provideAdapter(getSchoolYearContainer, [ISchoolToolApplication], 
                   provides=ISchoolYearContainer)

    provideAdapter(getActivityScore)
    provideAdapter(getLinkedActivityScore)
    provideAdapter(getWorksheetAverageScore)

    provideAdapter(getScoreSystemContainer, [ISchoolToolApplication],
                   provides=IScoreSystemContainer)

    provideAdapter(StupidKeyReference, [object], IKeyReference)
    provideAdapter(FakeURL, [ISchoolToolApplication, IBrowserRequest],
                   provides=IAbsoluteURL)
    provideUtility(IntIdsStub(), IIntIds, '')

    provideAdapter(getCalendar, [object], provides=ISchoolToolCalendar)

    provideAdapter(LocaleCollator, adapts=[None], provides=ICollator)

    app = ApplicationStub()
    provideAdapter(lambda x: app, [None], provides=ISchoolToolApplication)

    provideUtility(DateManagerStub(), IDateManager, '')

    provideUtility(DiscreteScoreSystemsVocabulary, IVocabularyFactory,
        'schooltool.requirement.discretescoresystems')

    setupSections(app)

    setupGradebook(app)


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
