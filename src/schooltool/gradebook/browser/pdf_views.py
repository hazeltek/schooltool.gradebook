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
PDF Views
"""

from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getUtility
from zope.traversing.browser.absoluteurl import absoluteURL

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.browser.report import ReportPDFView
from schooltool.common import SchoolToolMessage as _
from schooltool.course.interfaces import ILearner
from schooltool.gradebook.browser.report_card import (ABSENT_HEADING,
    TARDY_HEADING, ABSENT_KEY, TARDY_KEY)
from schooltool.gradebook.browser.report_utils import buildHTMLParagraphs
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.lyceum.journal.interfaces import ISectionJournalData
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import ITerm, IDateManager


class BasePDFView(ReportPDFView):
    """A base class for all PDF views"""

    def noCurrentTerm(self):
        self.current_term = getUtility(IDateManager).current_term
        if self.current_term is None:
            next_url = absoluteURL(ISchoolToolApplication(None), self.request)
            next_url += '/no_current_term.html'
            self.request.response.redirect(next_url)
            return True
        self.schoolyear = ISchoolYear(self.current_term)
        return False


class BaseReportCardPDFView(BasePDFView):
    """The report card (PDF) base class"""

    template=ViewPageTemplateFile('report_card_rml.pt')

    def __call__(self):
        """Make sure there is a current term."""
        if self.noCurrentTerm():
            return
        return super(BaseReportCardPDFView, self).__call__()

    def isJournalSource(self, layout):
        return layout.source in [ABSENT_KEY, TARDY_KEY]

    def getJournalScore(self, student, section, layout):
        jd = ISectionJournalData(section)
        result = 0
        for meeting in jd.recordedMeetings(student):
            grade = jd.getGrade(student, meeting)
            if grade == 'n' and layout.source == ABSENT_KEY:
                result += 1
            if grade == 'p' and layout.source == TARDY_KEY:
                result += 1
        return result or None

    def getActivity(self, section, layout):
        termName, worksheetName, activityName = layout.source.split('|')
        activities = IActivities(section)
        if worksheetName in activities:
            return activities[worksheetName][activityName]
        return None

    def getLayoutActivityHeading(self, layout, truncate=True):
        if layout.source == ABSENT_KEY:
            return ABSENT_HEADING
        if layout.source == TARDY_KEY:
            return TARDY_HEADING
        termName, worksheetName, activityName = layout.source.split('|')
        root = IGradebookRoot(ISchoolToolApplication(None))
        heading = root.deployed[worksheetName][activityName].title
        if len(layout.heading):
            heading = layout.heading
        if truncate:
            heading = heading[:5]
        return heading

    def getCourseTitle(self, course, sections):
        teachers = []
        for section in sections:
            if course == tuple(section.courses):
                for teacher in section.instructors:
                    if teacher not in teachers:
                        teachers.append(teacher)
        courseTitles = ', '.join(c.title for c in course)
        teacherNames = ['%s %s' % (teacher.first_name, teacher.last_name) 
            for teacher in teachers]
        teacherNames = ', '.join(teacherNames)
        return '%s (%s)' % (courseTitles, teacherNames)

    @property
    def title(self):
        return _('Report Card') + ': ' + self.schoolyear.title

    @property
    def course_heading(self):
        return _('Courses')

    @property
    def students(self):
        results = []
        for student in self.collectStudents():
            student_name = u'%s %s' % (
                student.first_name, student.last_name)
            student_title = _('Student') + ': ' + student_name

            sections = [section for section in ILearner(student).sections()
                        if ISchoolYear(ITerm(section)) == self.schoolyear]

            result = {
                'title': student_title,
                'grid': self.getGrid(student, sections),
                'outline': self.getOutline(student, sections),
                }

            results.append(result)
        return results

    def getGrid(self, student, sections):
        root = IGradebookRoot(ISchoolToolApplication(None))
        if self.schoolyear.__name__ in root.layouts:
            layouts = root.layouts[self.schoolyear.__name__].columns
        else:
            layouts = []

        courses = []
        for section in sections:
            course = tuple(section.courses)
            if course not in courses:
                courses.append(course)

        scores = {}
        evaluations = IEvaluations(student)
        for layout in layouts:
            byCourse = {}
            for section in sections:
                course = tuple(section.courses)
                if self.isJournalSource(layout):
                    score = self.getJournalScore(student, section, layout)
                    if score is not None:
                        if course in byCourse:
                            score += int(byCourse[course])
                        byCourse[course] = unicode(score)
                else:
                    activity = self.getActivity(section, layout)
                    if activity is None:
                        continue
                    score = evaluations.get(activity, None)
                    if score is not None and score.value is not UNSCORED:
                        byCourse[course] = unicode(score.value)
            if len(byCourse):
                scores[layout.source] = byCourse

        scoredLayouts = [l for l in layouts if l.source in scores]

        headings = []
        for layout in scoredLayouts:
            headings.append(self.getLayoutActivityHeading(layout))

        rows = []
        for course in courses:
            grid_scores = []
            for layout in scoredLayouts:
                byCourse = scores[layout.source]
                score = byCourse.get(course, '')
                grid_scores.append(score)

            row = {
                'title': self.getCourseTitle(course, sections),
                'scores': grid_scores,
                }
            rows.append(row)

        return {
            'headings': headings,
            'widths': '8.2cm' + ',1.6cm' * len(scoredLayouts),
            'rows': rows,
            }

    def getOutline(self, student, sections):
        root = IGradebookRoot(ISchoolToolApplication(None))
        if self.schoolyear.__name__ in root.layouts:
            layouts = root.layouts[self.schoolyear.__name__].outline_activities
        else:
            layouts = []
        evaluations = IEvaluations(student)

        section_list = []
        for section in sections:
            worksheets = []
            for layout in layouts:
                termName, worksheetName, activityName = layout.source.split('|')
                activities = IActivities(section)
                if worksheetName not in activities:
                    continue
                if activityName not in activities[worksheetName]:
                    continue
                activity = activities[worksheetName][activityName]

                score = evaluations.get(activity, None)
                if score is None or score.value is UNSCORED:
                    continue

                for worksheet in worksheets:
                    if worksheet['name'] == worksheetName:
                        break
                else:
                    worksheet = {
                        'name': worksheetName,
                        'heading': activities[worksheetName].title,
                        'activities': [],
                        }
                    worksheets.append(worksheet)

                heading = self.getLayoutActivityHeading(layout, truncate=False)
                activity_result = {
                    'heading': heading,
                    'value': buildHTMLParagraphs(unicode(score.value)),
                    }

                worksheet['activities'].append(activity_result)

            if len(worksheets):
                section_result = {
                    'heading': section.title,
                    'worksheets': worksheets,
                    }
                section_list.append(section_result)

        return section_list


class StudentReportCardPDFView(BaseReportCardPDFView):
    """A view for printing a report card for a student"""

    def collectStudents(self):
        return [self.context]


class GroupReportCardPDFView(BaseReportCardPDFView):
    """A view for printing a report card for each person in a group"""

    def collectStudents(self):
        return list(self.context.members)


class BaseStudentDetailPDFView(BasePDFView):
    """The report card (PDF) base class"""

    template=ViewPageTemplateFile('student_detail_rml.pt')

    def __call__(self):
        """Make sure there is a current term."""
        if self.noCurrentTerm():
            return
        return super(BaseStudentDetailPDFView, self).__call__()

    @property
    def title(self):
        return _('Student Detail Report') + ': ' + self.schoolyear.title

    @property
    def grades_heading(self):
        return _('Grade Detail')

    @property
    def course_heading(self):
        return _('Courses')

    @property
    def attendance_heading(self):
        return _('Attendance Detail')

    @property
    def date_heading(self):
        return _('Dates')

    def grades(self):
        return {
            'widths': '4cm,1cm,1cm',
            'headings': ['1', '2'],
            'rows': [
                {
                    'title': 'English I',
                    'scores': ['A', ''],
                },
                {
                    'title': 'Algebra II',
                    'scores': ['', 'B'],
                },
            ]
        }

    def attendance(self):
        return {
            'widths': '4cm,1cm,1cm',
            'headings': ['A', 'B'],
            'rows': [
                {
                    'title': '9/27/09',
                    'scores': ['', 'A1'],
                },
                {
                    'title': '10/1/09',
                    'scores': ['T2', ''],
                },
            ]
        }


class StudentDetailPDFView(BaseStudentDetailPDFView):
    """A view for printing a report card for a student"""

    def students(self):
        #return [self.context]
        return [
            {
                'name_heading': _('Student Name'),
                'name': 'Alan Elkner',
                'userid_heading': _('User Id'),
                'userid': 'aelkner',
                'grades': self.grades(),
                'attendance': self.attendance(),
            }
        ]


class GroupDetailPDFView(BaseStudentDetailPDFView):
    """A view for printing a report card for each person in a group"""


    def students(self):
        #return list(self.context.members)
        return [
            {
                'name_heading': _('Student Name'),
                'name': 'Alan Elkner',
                'userid_heading': _('User Id'),
                'userid': 'aelkner',
                'grades': self.grades(),
                'attendance': self.attendance(),
            }
        ]


class FailingReportPDFView(BasePDFView):
    """A view for printing a report of all the students failing an activity"""

    template=ViewPageTemplateFile('failing_report_rml.pt')

    def __call__(self):
        self.schoolyear = self.context
        return super(FailingReportPDFView, self).__call__()

    @property
    def title(self):
        return _('Failing Report') + ': ' + self.schoolyear.title

    @property
    def heading_message(self):
        return _('The following students are at risk of failing the following courses:')

    @property
    def name_heading(self):
        return _('Student')

    @property
    def course_heading(self):
        return _('Course')

    @property
    def teacher_heading(self):
        return _('Teacher(s)')

    @property
    def grade_heading(self):
        return _('Grade')

    def students(self):
        return [
            {
                'name': 'Alan Elkner',
                'rows': [
                    {
                        'course': 'English I',
                        'teacher': 'Tom Hoffman',
                        'grade': 'A',
                    },
                    {
                        'course': 'Algebra II',
                        'teacher': 'Jeff Elkner',
                        'grade': 'B',
                    },
                ],
            },
        ]


class AbsencesByDayPDFView(BasePDFView):
    """A view for printing a report with those students absent on a given day"""

    template=ViewPageTemplateFile('absences_by_day_rml.pt')

    def __call__(self):
        self.schoolyear = self.context
        return super(AbsencesByDayPDFView, self).__call__()

    @property
    def title(self):
        return _('Student Absence Report')

    @property
    def periods_heading(self):
        return _('Period Number')

    @property
    def name_heading(self):
        return _('Student')

    @property
    def widths(self):
        return '8cm' + ',1cm' * 8

    @property
    def periods(self):
        return ['1', '2', '3', '4', '5', '6', '7', '8']

    @property
    def students(self):
        return [
            {
                'name': 'Alan Elkner',
                'periods': ['1', '2', '3', '4', '5', '', '7', ''],
            },
            {
                'name': 'Tom Hoffman',
                'periods': ['', '2', '', '4', '5', '', '7', '4'],
            },
        ]


class SectionAbsencesPDFView(BasePDFView):
    """A view for printing a report with absences for a given section"""

    template=ViewPageTemplateFile('section_absences_rml.pt')

    def __call__(self):
        self.section = self.context
        return super(SectionAbsencesPDFView, self).__call__()

    @property
    def title(self):
        return _('Section Absences Report')

    @property
    def course_heading(self):
        return _('Course')

    @property
    def course(self):
        return ', '.join([course.title for course in self.section.courses])

    @property
    def teacher_heading(self):
        return _('Teacher')

    @property
    def teacher(self):
        return ', '.join(['%s %s' % (teacher.first_name, teacher.last_name)
                          for teacher in self.section.instructors])

    @property
    def student_heading(self):
        return _('Student')

    @property
    def attendance_heading(self):
        return _('Attendance types and number of occurrences')

    @property
    def total_heading(self):
        return _('Total')

    @property
    def students(self):
        return [
            {
                'name': 'Alan Elkner',
                'attendance': 'A 5',
                'total': '5',
            },
            {
                'name': 'Tom Hoffman',
                'attendance': 'T 3',
                'total': '3',
            },
        ]

