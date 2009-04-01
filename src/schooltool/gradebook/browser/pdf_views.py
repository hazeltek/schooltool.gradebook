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

import cgi
from cStringIO import StringIO

from reportlab.lib import units
from reportlab.lib import pagesizes
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Paragraph
from reportlab.platypus.flowables import HRFlowable, Spacer, Image, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.tables import Table, TableStyle

from zope.component import getUtility, queryAdapter
from zope.i18n import translate
from zope.publisher.browser import BrowserView

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.browser import pdfcal
from schooltool.common import SchoolToolMessage as _
from schooltool.course.interfaces import ISection, ILearner
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.group.interfaces import IGroup
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import ITerm, IDateManager


def _para(text, style):
    """Helper which builds a reportlab Paragraph flowable"""
    if text is None:
        text = ''
    elif isinstance(text, unicode):
        text = text.encode('utf-8')
    else:
        text = str(text)
    return Paragraph(cgi.escape(text), style)


class ReportCard(object):

    styles = None # A dict of paragraph styles, initialized later
    logo = None # A reportlab flowable to be used as logo
    title = _('Report Cards')

    def __init__(self, logo_filename, students):
        if logo_filename is not None:
            self.logo = self.buildLogo(logo_filename)
        self.students = students
        current_term = getUtility(IDateManager).current_term
        self.schoolyear = ISchoolYear(current_term)
        self.setUpStyles()

    def setUpStyles(self):
        from reportlab.lib import enums
        self.styles = {}
        self.styles['default'] = ParagraphStyle(
            name='Default', fontName=pdfcal.SANS,
            fontSize=12, leading=12)

        self.styles['bold'] = ParagraphStyle(
            name='DefaultBold', fontName=pdfcal.SANS_BOLD,
            fontSize=12, leading=12)

        self.styles['title'] = ParagraphStyle(
            name='Title', fontName=pdfcal.SANS_BOLD,
            fontSize=20, leading=22,
            alignment=enums.TA_CENTER, spaceAfter=6)

        self.styles['subtitle'] = ParagraphStyle(
            name='Subtitle', fontName=pdfcal.SANS_BOLD,
            fontSize=16, leading=22,
            alignment=enums.TA_CENTER, spaceAfter=6)

        self.table_style = TableStyle(
          [('LEFTPADDING', (0, 0), (-1, -1), 1),
           ('RIGHTPADDING', (0, 0), (-1, -1), 1),
           ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
           ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ])

    def buildLogo(self, filename):
        logo = Image(filename)
        width = 8 * units.cm
        logo.drawHeight = width * (logo.imageHeight / float(logo.imageWidth))
        logo.drawWidth = width
        return logo

    def buildStudentInfo(self, student):
        student_name = u'%s %s' % (
            student.first_name, student.last_name)

        rows = []
        rows.append(
            [_para(_('Student:'), self.styles['bold']),
             _para(student_name, self.styles['default'])]
             )

        story = []

        widths = [2.5 * units.cm, '50%']
        story.append(Table(rows, widths, style=self.table_style))

        return story

    def getActivity(self, section, layout):
        termName, worksheetName, activityName = layout.split('|')
        activities = IActivities(section)
        if worksheetName in activities:
            return activities[worksheetName][activityName]
        return None

    def getLayoutTermTitle(self, layout):
        termName, worksheetName, activityName = layout.split('|')
        return self.schoolyear[termName].title

    def getLayoutActivityTitle(self, layout):
        termName, worksheetName, activityName = layout.split('|')
        root = IGradebookRoot(ISchoolToolApplication(None))
        return root.deployed[worksheetName][activityName].title

    def buildScores(self, student):
        sections = list(ILearner(student).sections())
        evaluations = IEvaluations(student)
        root = IGradebookRoot(ISchoolToolApplication(None))
        if self.schoolyear.__name__ in root.layouts:
            layouts = root.layouts[self.schoolyear.__name__].columns
        else:
            layouts = []

        courses = []
        for section in sections:
            course = list(section.courses)[0]
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
                    byCourse[course] = str(score.value)
            if len(byCourse):
                scores[layout] = byCourse

        row = [_para('', self.styles['bold'])]
        for layout in layouts:
            if layout not in scores:
                continue
            label = self.getLayoutTermTitle(layout)
            row.append(_para(label, self.styles['bold']))
        rows = [row]

        row = [_para(_('Courses'), self.styles['bold'])]
        for layout in layouts:
            if layout not in scores:
                continue
            label = self.getLayoutActivityTitle(layout)
            row.append(_para(label, self.styles['bold']))
        rows.append(row)

        for course in courses:
            row = [_para(course.title, self.styles['default'])]
            for layout in layouts:
                if layout not in scores:
                    continue
                byCourse = scores[layout]
                score = byCourse.get(course, '')
                row.append(_para(score, self.styles['default']))
            rows.append(row)

        story = [Table(rows, style=self.table_style)]
        return story

    def buildStudentStory(self, student):
        story = []
        if self.logo is not None:
            story.append(self.logo)
        story.append(_para(_('Report Card'), self.styles['title']))

        story.extend(self.buildStudentInfo(student))

        # append horizontal rule
        story.append(HRFlowable(
            width='90%', color=colors.black,
            spaceBefore=0.5*units.cm, spaceAfter=0.5*units.cm))

        story.extend(self.buildScores(student))

        return story

    def buildAggregateStory(self, students):
        story = []
        for student in students:
            story.extend(self.buildStudentStory(student))
            story.append(PageBreak())
        return story

    def renderPDF(self, story, report_title):
        datastream = StringIO()
        doc = SimpleDocTemplate(datastream, pagesize=pagesizes.A4)
        title = report_title
        doc.title = title.encode('utf-8')
        doc.leftMargin = 0.75 * units.inch
        doc.bottomMargin = 0.75 * units.inch
        doc.topMargin = 0.75 * units.inch
        doc.rightMargin = 0.75 * units.inch
        doc.leftPadding = 0
        doc.rightPadding = 0
        doc.topPadding = 0
        doc.bottomPadding = 0
        doc.build(story)
        return datastream.getvalue()

    def __call__(self):
        """Build and render the report"""
        story = self.buildAggregateStory(self.students)
        pdf_data = self.renderPDF(story, self.title)
        return pdf_data


class BasePDFView(BrowserView):
    """The report card (PDF) base class"""

    pdf_disabled_text = _("PDF support is disabled."
                          "  It can be enabled by your administrator.")

    def __init__(self, *args, **kw):
        super(BasePDFView, self).__init__(*args, **kw)
        self.students = self.collectStudents()

    @property
    def pdf_support_disabled(self):
        return pdfcal.disabled

    def buildPDF(self):
        report = ReportCard(None, self.students)
        return report()

    def __call__(self):
        """Return the PDF of a report card for each student."""
        if self.pdf_support_disabled:
            return translate(self.pdf_disabled_text, context=self.request)

        pdf_data = self.buildPDF()

        response = self.request.response
        response.setHeader('Content-Type', 'application/pdf')
        response.setHeader('Content-Length', len(pdf_data))
        response.setHeader("pragma", "no-store,no-cache")
        response.setHeader("cache-control",
                           "no-cache, no-store,must-revalidate, max-age=-1")
        response.setHeader("expires", "-1")
        # We don't really accept ranges, but Acrobat Reader will not show the
        # report in the browser page if this header is not provided.
        response.setHeader('Accept-Ranges', 'bytes')

        return pdf_data


class StudentReportCardPDFView(BasePDFView):
    """A view for printing a report card for a student"""

    def collectStudents(self):
        return [self.context]


class GroupReportCardPDFView(BasePDFView):
    """A view for printing a report card for each person in a group"""

    def collectStudents(self):
        return list(self.context.members)

