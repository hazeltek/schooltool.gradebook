#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2009 Shuttleworth Foundation
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
Report reference and request adapters
"""
from schooltool.report import report

from schooltool.gradebook import GradebookMessage as _


##################     Student reports   ####################
class StudentReportCardReference(report.StudentReportReference):
    title = _('Student Report Card')
    description = _('Contains scores from report sheets and attendance.  Customizable layout.  Formatted to be sent to parents.')


class StudentReportCardRequest(report.StudentReportRequest):
    title = _('Request Report Card')
    extra = '/request_report_card.html'


class StudentDetailReportReference(report.StudentReportReference):
    title = _('Student Detail Report')
    description = _('Contains scores from report sheets, detailed attendance and demographic data.  For use by school staff.')


class StudentDetailReportRequest(report.StudentReportRequest):
    title = _('Request Detailed Student Report')
    extra = '/request_student_detail.html'


##################     Group reports   ####################
class GroupReportCardReference(report.GroupReportReference):
    title = _('Student Report Card by Group')
    description = _('A single pdf containing report cards for all students in the selected group.')


class GroupReportCardRequest(report.GroupReportRequest):
    title = _('Request Report Card')
    extra = '/request_report_card.html'


class GroupDetailReportReference(report.GroupReportReference):
    title = _('Student Detail Report by Group')
    description = _('A single pdf containing detail reports for all students in the selected group.')


class GroupDetailReportRequest(report.GroupReportRequest):
    title = _('Request Detailed Student Report')
    extra = '/request_student_detail.html'


##################     SchoolYear reports   ####################
class AbsencesByDayReference(report.SchoolYearReportReference):
    title = _('Absences By Day')
    description = _('Lists students absent on a given day.')


class AbsencesByDayRequest(report.SchoolYearReportRequest):
    title = _('Absences By Day')
    extra = '/request_absences_by_day.html'


##################     Term reports   ####################
class FailingReportReference(report.TermReportReference):
    title = _('Failures by Term')
    description = _('Shows all students receiving failing scores in the selected report activity and term.')


class FailingReportRequest(report.TermReportRequest):
    title = _('Failures by Term')
    extra = '/request_failing_report.html'


##################     Section reports   ####################
class SectionAbsencesReference(report.SectionReportReference):
    title = _('Absences by Section')
    description = _('Summary of absences and tardies from a single section and term.')


class SectionAbsencesRequest(report.SectionReportRequest):
    title = _('Download Absences by Section Report')
    extra = '/section_absences.pdf'

