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

from datetime import datetime
from decimal import Decimal
from copy import deepcopy

from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getUtility
from zope.security.proxy import removeSecurityProxy
from zope.traversing.browser.absoluteurl import absoluteURL

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.browser.report import ReportPDFView
from schooltool.course.interfaces import ILearner, ISectionContainer
from schooltool.course.interfaces import ISection
from schooltool.person.interfaces import IPerson
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import ITerm, IDateManager

from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook.browser.gradebook import GradebookOverview
from schooltool.gradebook.browser.report_card import (ABSENT_HEADING,
    TARDY_HEADING, ABSENT_ABBREVIATION, TARDY_ABBREVIATION, ABSENT_KEY,
    TARDY_KEY)
from schooltool.gradebook.browser.report_utils import buildHTMLParagraphs
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.gradebook.interfaces import IGradebook
from schooltool.gradebook.interfaces import ISectionJournalData
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.scoresystem import UNSCORED


class BasePDFView(ReportPDFView):
    """A base class for all PDF views"""

    def __init__(self, context, request):
        super(BasePDFView, self).__init__(context, request)
        self.current_term = getUtility(IDateManager).current_term
        if self.current_term is None:
            self.schoolyear = None
        else:
            self.schoolyear = ISchoolYear(self.current_term)
        if 'term' in self.request:
            self.term = self.schoolyear[self.request['term']]
        else:
            self.term = None


class BaseStudentPDFView(BasePDFView):
    """A base class for all student PDF views"""

    def isJournalSource(self, layout):
        return layout.source in [ABSENT_KEY, TARDY_KEY]

    def getJournalScore(self, student, section, layout):
        jd = ISectionJournalData(section, None)
        if jd is None:
            return None
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


class BaseReportCardPDFView(BaseStudentPDFView):
    """The report card (PDF) base class"""

    template=ViewPageTemplateFile('rml/report_card_rml.pt')

    def __call__(self):
        """Make sure there is a current term."""
        if self.current_term is None:
            template = ViewPageTemplateFile('templates/no_current_term.pt')
            return template(self)
        return super(BaseReportCardPDFView, self).__call__()

    def title(self):
        return _('Report Card: ${schoolyear}',
                 mapping={'schoolyear': self.schoolyear.title})

    def course_heading(self):
        return _('Courses')

    def students(self):
        results = []
        for student in self.collectStudents():
            student_name = u'%s %s' % (
                student.first_name, student.last_name)
            student_title = _('Student: ${student}',
                              mapping={'student': student_name})

            sections = []
            for section in ILearner(student).sections():
                term = ITerm(section)
                schoolyear = ISchoolYear(term)
                if schoolyear != self.schoolyear:
                    continue
                if self.term is not None and term != self.term:
                    continue
                sections.append(section)

            result = {
                'title': student_title,
                'grid': self.getGrid(student, sections),
                'outline': self.getOutline(student, sections),
                }

            results.append(result)
        return results

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
            term = ITerm(section)
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
                    'heading': "%s - %s" % (term.title, section.title),
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


class BaseStudentDetailPDFView(BaseStudentPDFView):
    """The report card (PDF) base class"""

    template=ViewPageTemplateFile('rml/student_detail_rml.pt')

    def __call__(self):
        """Make sure there is a current term."""
        if self.current_term is None:
            template = ViewPageTemplateFile('templates/no_current_term.pt')
            return template(self)
        return super(BaseStudentDetailPDFView, self).__call__()

    def title(self):
        return _('Detailed Student Report: ${schoolyear}',
                 mapping={'schoolyear': self.schoolyear.title})

    def grades_heading(self):
        return _('Grade Detail')

    def course_heading(self):
        return _('Courses')

    def attendance_heading(self):
        return _('Attendance Detail')

    def date_heading(self):
        return _('Dates')

    def name_heading(self):
        return _('Student Name')

    def userid_heading(self):
        return _('User Id')

    def grades(self, student):
        sections = []
        for section in ILearner(student).sections():
            term = ITerm(section)
            schoolyear = ISchoolYear(term)
            if schoolyear != self.schoolyear:
                continue
            if self.term is not None and term != self.term:
                continue
            sections.append(section)
        return self.getGrid(student, sections)

    def attendance(self, student):
        data = {}
        sections = []
        for section in ILearner(student).sections():
            term = ITerm(section)
            schoolyear = ISchoolYear(term)
            if schoolyear != self.schoolyear:
                continue
            if self.term is not None and term != self.term:
                continue
            sections.append(section)
        for section in sections:
            jd = ISectionJournalData(section, None)
            if jd is None:
                continue
            for meeting in jd.recordedMeetings(student):
                period = meeting.period_id[:5]
                day = meeting.dtstart
                grade = jd.getGrade(student, meeting)
                result = ''
                if grade == 'n':
                    result = ABSENT_ABBREVIATION
                if grade == 'p':
                    result = TARDY_ABBREVIATION
                if result:
                    data.setdefault(day, {})[period] = result

        periods = {}
        for day in data:
            for period in data[day]:
                periods[period] = 0
        periods = list(periods.keys())

        widths = '4cm' + ',1cm' * len(periods)
        rows = []
        for day in sorted(data):
            scores = [''] * len(periods)
            for period in data[day]:
                index = periods.index(period)
                scores[index] = data[day][period]
            row = {
                'title': day.strftime('%x'),
                'scores': scores,
                }
            rows.append(row)

        return {
            'widths': widths,
            'headings': periods,
            'rows': rows,
            }

    def students(self):
        results = []
        for student in self.collectStudents():
            name = u'%s %s' % (student.first_name, student.last_name)
            result = {
                'name': name,
                'userid': student.username,
                'grades': self.grades(student),
                'attendance': self.attendance(student),
                }
            results.append(result)
        return results


class StudentDetailPDFView(BaseStudentDetailPDFView):
    """A view for printing a report card for a student"""

    def collectStudents(self):
        return [self.context]


class GroupDetailPDFView(BaseStudentDetailPDFView):
    """A view for printing a report card for each person in a group"""

    def collectStudents(self):
        return list(self.context.members)


class FailingReportPDFView(BasePDFView):
    """A view for printing a report of all the students failing an activity"""

    template=ViewPageTemplateFile('rml/failing_report_rml.pt')

    def __init__(self, context, request):
        super(FailingReportPDFView, self).__init__(context, request)
        self.term = self.context
        self.activity = self.getActivity()
        self.score = self.request.get('min', None)

    def getActivity(self):
        source = self.request.get('activity', None)
        if source is None:
            return None
        termName, worksheetName, activityName = source.split('|')
        root = IGradebookRoot(ISchoolToolApplication(None))
        return root.deployed[worksheetName][activityName]

    def title(self):
        return _('Failures by Term Report: ${term}',
                 mapping={'term': self.term.title})

    def worksheet_heading(self):
        return _('Report Sheet:')

    def worksheet_value(self):
        return self.activity.__parent__.title

    def activity_heading(self):
        return _('Activity:')

    def activity_value(self):
        return self.activity.title

    def score_heading(self):
        return _('Passing Score:')

    def score_value(self):
        return self.request.get('min', '')

    def heading_message(self):
        return _('The following students are at risk of failing the following courses:')

    def name_heading(self):
        return _('Student')

    def course_heading(self):
        return _('Course')

    def teacher_heading(self):
        return _('Teacher(s)')

    def grade_heading(self):
        return _('Grade')

    def getSectionData(self, section):
        data = []
        for worksheet in IActivities(section).values():
            if worksheet.__name__ == self.activity.__parent__.__name__:
                gb = IGradebook(worksheet)
                activity = worksheet[self.activity.__name__]
                break
        else:
            return []
        for student in gb.students:
            score = gb.getScore(student, activity)
            if score is None or score.value is UNSCORED:
                continue
            failure = False
            if IDiscreteValuesScoreSystem.providedBy(score.scoreSystem):
                for definition in score.scoreSystem.scores:
                    if definition[0] == self.score:
                        passing_value = definition[2]
                    if definition[0] == score.value:
                        this_value = definition[2]
                if score.scoreSystem._isMaxPassingScore:
                    if this_value > passing_value:
                        failure = True
                elif this_value < passing_value:
                    failure = True
            else:
                passing_value = Decimal(self.score)
                this_value = score.value
                if this_value < passing_value:
                    failure = True
            if failure:
                data.append([student, score.value])
        return data

    def students(self):
        student_rows = {}
        for section in ISectionContainer(self.term).values():
            for student, value in self.getSectionData(section):
                rows = student_rows.setdefault(student, [])
                row = {
                    'section': section,
                    'grade': value,
                    }
                rows.append(row)

        results = []
        for student in sorted(student_rows,  key=lambda s: s.title):
            rows = []
            for student_row in student_rows[student]:
                teacher = list(student_row['section'].instructors)[0]
                name = '%s %s' % (teacher.first_name, teacher.last_name)
                row = {
                    'course': list(student_row['section'].courses)[0].title,
                    'teacher': name,
                    'grade': student_row['grade'],
                    }
                rows.append(row)
            result = {
                'name': '%s %s' % (student.first_name, student.last_name),
                'rows': rows,
                }
            results.append(result)
        return results


class AbsencesByDayPDFView(BasePDFView):
    """A view for printing a report with those students absent on a given day"""

    template=ViewPageTemplateFile('rml/absences_by_day_rml.pt')

    def __init__(self, context, request):
        super(AbsencesByDayPDFView, self).__init__(context, request)
        self.schoolyear = self.context

    def title(self):
        return _('Absences By Day Report')

    def getDay(self):
        day = self.request.get('day', None)
        if day is None:
            return datetime.date(datetime.now())
        try:
            year, month, day = [int(part) for part in day.split('-')]
            return datetime.date(datetime(year, month, day))
        except:
            return None

    def compareDates(self, first, second):
        return (first.year == second.year and first.month == second.month and
                first.day == second.day)

    def getData(self):
        day = self.getDay()
        if day is None:
            return []
        for term in self.schoolyear.values():
            if day in term:
                break
        else:
            return []

        data = {}
        for section in ISectionContainer(term).values():
            jd = ISectionJournalData(section, None)
            if jd is None:
                continue
            for student in section.members:
                for meeting in jd.recordedMeetings(student):
                    if not self.compareDates(meeting.dtstart, day):
                        continue
                    period = meeting.period_id[:5]
                    grade = jd.getGrade(student, meeting)
                    result = ''
                    if grade == 'n':
                        result = ABSENT_ABBREVIATION
                    if grade == 'p':
                        result = TARDY_ABBREVIATION
                    if result:
                        data.setdefault(student, {})[period] = result
        return data

    def getPeriods(self, data):
        periods = {}
        for student in data:
            for period in data[student]:
                periods[period] = 0
        return list(periods.keys())

    def date_heading(self):
        day = self.getDay()
        if day is None:
            return ''
        else:
            return day.strftime('%A %B %0d, %Y')

    def periods_heading(self):
        return _('Period Number')

    def name_heading(self):
        return _('Student')

    def widths(self):
        data = self.getData()
        periods = self.getPeriods(data)
        return '8cm' + ',1cm' * len(periods)

    def periods(self):
        data = self.getData()
        return self.getPeriods(data)

    def students(self):
        data = self.getData()
        periods = self.getPeriods(data)

        rows = []
        for student in sorted(data, key=lambda s: s.title):
            scores = [''] * len(periods)
            for period in data[student]:
                index = periods.index(period)
                scores[index] = data[student][period]
            row = {
                'name': '%s %s' % (student.first_name, student.last_name),
                'periods': scores,
                }
            rows.append(row)
        return rows


class SectionAbsencesPDFView(BasePDFView):
    """A view for printing a report with absences for a given section"""

    template=ViewPageTemplateFile('rml/section_absences_rml.pt')

    def __init__(self, context, request):
        super(SectionAbsencesPDFView, self).__init__(context, request)
        self.section = self.context

    def title(self):
        return _('Absences by Section Report')

    def course_heading(self):
        return _('Course')

    def course(self):
        return ', '.join([course.title for course in self.section.courses])

    def teacher_heading(self):
        return _('Teacher')

    def teacher(self):
        return ', '.join(['%s %s' % (teacher.first_name, teacher.last_name)
                          for teacher in self.section.instructors])

    def student_heading(self):
        return _('Student')

    def absences_heading(self):
        return _('Absences')

    def tardies_heading(self):
        return _('Tardies')

    def total_heading(self):
        return _('Total')

    def getStudentData(self, jd, student):
        student_data = {}
        student_data['absences'] = 0
        student_data['tardies'] = 0
        for meeting in jd.recordedMeetings(student):
            grade = jd.getGrade(student, meeting)
            if grade == 'n':
                student_data['absences'] += 1
            if grade == 'p':
                student_data['tardies'] += 1
        return student_data

    def students(self):
        data = {}
        jd = ISectionJournalData(self.section, None)
        if jd is not None:
            for student in self.section.members:
                student_data = self.getStudentData(jd, student)
                if student_data['absences'] + student_data['tardies'] > 0:
                    data[student] = student_data

        rows = []
        for student in sorted(data, key=lambda s: s.title):
            row = {
                'name': '%s %s' % (student.first_name, student.last_name),
                'absences': data[student]['absences'],
                'tardies': data[student]['tardies'],
                'total': data[student]['absences'] + data[student]['tardies'],
                }
            rows.append(row)
        return rows


class GradebookPDFView(BasePDFView, GradebookOverview):
    """The gradebook pdf view class"""

    template=ViewPageTemplateFile('rml/gradebook_rml.pt')
    topMargin = 30
    leftMargin = 35

    def __init__(self, context, request):
        super(GradebookPDFView, self).__init__(context, request)
        self.person = IPerson(self.request.principal)
        self.sortKey = self.context.getSortKey(self.person)
        self.processColumnPreferences()
        self.worksheet = removeSecurityProxy(context).context
        self.section = ISection(self.worksheet)
        self.term = ITerm(self.section)

    def pages(self):
        results = []
        activities = list(self.activities())
        table = self.table()

        num_rows = len(table)
        num_cols = len(self.activities())
        start_row, start_col = 0, 0
        max_rows, max_cols = 34, 8
        if not self.absences_hide:
            max_cols -= 1
        if not self.tardies_hide:
            max_cols -= 1
        if not self.total_hide:
            max_cols -= 1
        if not self.average_hide:
            max_cols -= 1

        while True:
            end_row = start_row + max_rows
            if end_row > num_rows:
                end_row = num_rows
            next_row = start_row

            next_col = start_col + max_cols
            if next_col >= num_cols:
                end_col = num_cols
                next_col = 0
                next_row = end_row
            else:
                end_col = next_col

            rows = deepcopy(table)[start_row:end_row]
            for row in rows:
                row['grades'] = row['grades'][start_col:end_col]

            page = {
                'widths': self.widths(start_col, end_col),
                'rows': rows,
                'cols': deepcopy(activities)[start_col:end_col],
                }
            results.append(page)

            if next_row < num_rows:
                start_row, start_col = next_row, next_col
            else:
                break

        return results

    def title(self):
        return _('Gradebook Report')

    def term_heading(self):
        return _('Term')

    def section_heading(self):
        return _('Section')

    def worksheet_heading(self):
        return _('Worksheet')

    def student_heading(self):
        return _('Student')

    def widths(self, start_col, end_col):
        num_cols = end_col - start_col
        if not self.absences_hide:
            num_cols += 1
        if not self.tardies_hide:
            num_cols += 1
        if not self.total_hide:
            num_cols += 1
        if not self.average_hide:
            num_cols += 1
        return '6cm' +',1.6cm' * (num_cols)

