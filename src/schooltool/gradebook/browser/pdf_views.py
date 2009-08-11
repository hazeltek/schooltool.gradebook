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
from schooltool.gradebook.browser.report_utils import buildHTMLParagraphs
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import ITerm, IDateManager


class BasePDFView(ReportPDFView):
    """The report card (PDF) base class"""

    template=ViewPageTemplateFile('report_card_rml.pt')

    def __call__(self):
        """Make sure there is a current term."""
        current_term = getUtility(IDateManager).current_term
        if current_term is None:
            next_url = absoluteURL(ISchoolToolApplication(None), self.request)
            next_url += '/no_current_term.html'
            self.request.response.redirect(next_url)
            return
        self.schoolyear = ISchoolYear(current_term)
        return super(BasePDFView, self).__call__()

    def getActivity(self, section, layout):
        termName, worksheetName, activityName = layout.source.split('|')
        activities = IActivities(section)
        if worksheetName in activities:
            return activities[worksheetName][activityName]
        return None

    def getLayoutActivityHeading(self, layout, truncate=True):
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

        evaluations = IEvaluations(student)
        courses = []
        for section in sections:
            course = tuple(section.courses)
            if course not in courses:
                courses.append(course)

        scores = {}
        for layout in layouts:
            byCourse = {}
            for section in sections:
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
            'widths': '8.2cm' + ',1.2cm' * len(scoredLayouts),
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


class StudentReportCardPDFView(BasePDFView):
    """A view for printing a report card for a student"""

    def collectStudents(self):
        return [self.context]


class GroupReportCardPDFView(BasePDFView):
    """A view for printing a report card for each person in a group"""

    def collectStudents(self):
        return list(self.context.members)

