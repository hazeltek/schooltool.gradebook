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

from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.gradebook.interfaces import ISectionJournalData
from schooltool.requirement.interfaces import IEvaluations


class FlourishReportSheetsExportTermView(export.ExcelExportView,
                                         flourish.page.Page):
    """A view for exporting report sheets to an XLS file"""

    def print_headers(self, ws):
        headers = ['Section ID', 'Student ID', 'Absent', 'Tardy']
        for activity in self.activities:
            header = '%s / %s' % (activity.__parent__.title, activity.title)
            headers.append(header)
        for index, header in enumerate(headers):
            self.write_header(ws, 0, index, header)

    def print_student(self, ws, row, jd, activities, student):
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

    def print_grades(self, ws):
        row = 1
        for section in ISectionContainer(self.term).values():
            jd = ISectionJournalData(section, None)
            activities = IActivities(section)
            students = sorted(section.members, key=lambda s: s.username)

            self.write(ws, row, 0, section.__name__)
            if not students:
                row += 1
            else:
                for student in students:
                    self.print_student(ws, row, jd, activities, student)
                    row += 1

    def export_term(self, wb):
        ws = wb.add_sheet(self.term.__name__)
        self.print_headers(ws)
        self.print_grades(ws)

    def getFileName(self):
        return 'report_sheets_%s_%s.xls' % (self.schoolyear.__name__,
                                            self.term.__name__)

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

    def __call__(self):
        wb = xlwt.Workbook()

        for self.term in self.getTerms():
            self.schoolyear = ISchoolYear(self.term)
            self.activities = self.getActivities()
            self.export_term(wb)

        datafile = StringIO()
        wb.save(datafile)
        data = datafile.getvalue()
        self.setUpHeaders(data)
        disposition = 'filename="%s"' % self.getFileName()
        self.request.response.setHeader('Content-Disposition', disposition)
        return data


class FlourishReportSheetsExportSchoolYearView(
    FlourishReportSheetsExportTermView):
    """A view for exporting report sheets to an XLS file,
       one sheet for each term of the school year."""

    def getFileName(self):
        return 'report_sheets_%s.xls' % self.schoolyear.__name__

    def getTerms(self):
        return self.context.values()

