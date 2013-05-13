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
XLS Views
"""

import xlwt
from StringIO import StringIO

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISectionContainer
from schooltool.export import export
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.skin import flourish
from schooltool.task.progress import normalized_progress

from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.gradebook.interfaces import ISectionJournalData
from schooltool.requirement.interfaces import IEvaluations

from schooltool.gradebook import GradebookMessage as _


class FlourishReportSheetsExportTermView(export.ExcelExportView,
                                         flourish.page.Page):
    """A view for exporting report sheets to an XLS file"""

    message_title = _('report sheets export')

    def print_headers(self, ws):
        headers = ['Section ID', 'Student ID', 'Absent', 'Tardy']
        for activity in self.activities:
            header = '%s / %s' % (activity.__parent__.title, activity.title)
            headers.append(header)
        for index, header in enumerate(headers):
            self.write_header(ws, 0, index, header)

    def print_student(self, ws, row, section, jd, activities, student):
        self.write(ws, row, 0, section.__name__)
        self.write(ws, row, 1, student.username)

        if jd is not None:
            absences, tardies = 0, 0
            for meeting in jd.recordedMeetings(student):
                grade = jd.getGrade(student, meeting)
                if grade == 'n':
                    absences += 1
                if grade == 'p':
                    tardies += 1
            if absences:
                self.write(ws, row, 2, unicode(absences))
            if tardies:
                self.write(ws, row, 3, unicode(tardies))
        evaluations = IEvaluations(student)
        for index, activity in enumerate(self.activities):
            worksheet = activities[activity.__parent__.__name__]
            activity = worksheet[activity.__name__]
            score = evaluations.get(activity, None)
            if score:
                self.write(ws, row, index + 4, unicode(score.value))

    def print_grades(self, ws, term_idx, total_terms):
        row = 1

        sections = ISectionContainer(self.term).values()
        for ns, section in enumerate(sections):
            jd = ISectionJournalData(section, None)
            activities = IActivities(section)
            students = sorted(section.members, key=lambda s: s.username)

            if not students:
                self.write(ws, row, 0, section.__name__)
                row += 1
            else:
                for nstud, student in enumerate(students):
                    self.print_student(ws, row, section, jd, activities,
                                       student)
                    row += 1
                    self.progress('worksheets', normalized_progress(
                            term_idx, total_terms,
                            ns, len(sections),
                            nstud, len(students),
                            ))
            self.progress('worksheets', normalized_progress(
                    term_idx, total_terms,
                    ns, len(sections),
                    ))

    def export_term(self, wb, idx, total_terms):
        self.progress('worksheets', normalized_progress(
                idx, total_terms,
                ))
        ws = wb.add_sheet(self.term.__name__)
        self.print_headers(ws)
        self.print_grades(ws, idx, total_terms)

    @property
    def base_filename(self):
        terms = self.getTerms()
        if not terms:
            return 'report_sheets'
        term = terms[-1]
        schoolyear = ISchoolYear(term)
        base_filename =  'report_sheets_%s_%s.xls' % (schoolyear.__name__,
                                                      term.__name__)
        return base_filename

    def getTerms(self):
        return [self.context]

    def getActivities(self):
        activities = []
        root = IGradebookRoot(ISchoolToolApplication(None))
        prefix = '%s_%s_' % (self.schoolyear.__name__, self.term.__name__)
        for key, sheet in root.deployed.items():
            if key.startswith(prefix) and key[len(prefix):].isdigit():
                activities.extend(sheet.values())
        return activities

    def export_terms(self, workbook, terms):
        terms = list(terms)
        for nt, self.term in enumerate(terms):
            self.schoolyear = ISchoolYear(self.term)
            self.activities = self.getActivities()
            self.export_term(workbook, nt, len(terms))

        self.finish('worksheets')

    def addImporters(self, progress):
        progress.add(
            'worksheets',
            title=_('Term Worksheets'), progress=0.0)

    def __call__(self):
        self.makeProgress()
        self.task_progress.title = _("Exporting worksheets")
        self.addImporters(self.task_progress)

        wb = xlwt.Workbook()

        self.export_terms(wb, self.getTerms())

        self.task_progress.title = _("Export complete")
        self.task_progress.force('worksheets', progress=1.0)
        return wb


class FlourishReportSheetsExportSchoolYearView(
    FlourishReportSheetsExportTermView):
    """A view for exporting report sheets to an XLS file,
       one sheet for each term of the school year."""

    @property
    def base_filename(self):
        terms = self.getTerms()
        if not terms:
            return 'report_sheets'
        schoolyear = ISchoolYear(terms[-1])
        return 'report_sheets_%s' % schoolyear.__name__

    def addImporters(self, progress):
        self.task_progress.add(
            'worksheets',
            title=_('School Year Worksheets'), progress=0.0)

    def getTerms(self):
        return self.context.values()

