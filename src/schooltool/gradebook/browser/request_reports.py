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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Request PDF Views
"""

from datetime import datetime
from urllib import unquote_plus

import zope.schema
import zope.schema.vocabulary
import zope.schema.interfaces
import z3c.form
import z3c.form.validator
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getUtility
from zope.i18n import translate
from zope.interface import implements, Interface
from zope.publisher.browser import BrowserView
from zope.traversing.browser.absoluteurl import absoluteURL

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import IDateManager, ITerm
from schooltool.export.export import RequestXLSReportDialog
from schooltool.report.browser.report import RequestRemoteReportDialog

from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook.interfaces import IGradebookRoot
from schooltool.gradebook.gradebook import GradebookReportTask
from schooltool.gradebook.gradebook import TraversableXLSReportTask
from schooltool.requirement.interfaces import ICommentScoreSystem
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.skin.flourish.form import Dialog


class TermActivityChoices(zope.schema.vocabulary.SimpleVocabulary):
    implements(zope.schema.interfaces.IContextSourceBinder)

    def __init__(self, context):
        self.context = context
        terms = self.createTerms(ITerm(self.context.get('term')))
        zope.schema.vocabulary.SimpleVocabulary.__init__(self, terms)

    def createTerms(self, term):
        result = []
        result.append(self.createTerm(
                None,
                z3c.form.widget.SequenceWidget.noValueToken,
                _("Select a source"),
                ))
        root = IGradebookRoot(ISchoolToolApplication(None))
        schoolyear = ISchoolYear(term)
        deployedKey = '%s_%s' % (schoolyear.__name__, term.__name__)
        for key in root.deployed:
            if key.startswith(deployedKey):
                deployedWorksheet = root.deployed[key]
                for activity in deployedWorksheet.values():
                    if ICommentScoreSystem.providedBy(activity.scoresystem):
                        continue
                    title = '%s - %s - %s' % (term.title,
                        deployedWorksheet.title, activity.title)
                    token = '%s-%s-%s' % (term.__name__,
                        deployedWorksheet.__name__, activity.__name__)
                    token=unicode(token).encode('punycode')
                    result.append(self.createTerm(
                        (deployedWorksheet, activity,),
                        token,
                        title,
                        ))
        return result


def termactivitychoicesfactory():
    return TermActivityChoices


class FailingReportScores(zope.schema.vocabulary.SimpleVocabulary):
    implements(zope.schema.interfaces.IContextSourceBinder)

    def __init__(self, context):
        self.context = context
        terms = self.createTerms()
        zope.schema.vocabulary.SimpleVocabulary.__init__(self, terms)

    def createTerms(self):
        result = []
        scoresystem = self.context.get('scoresystem')
        if not scoresystem:
            return result
        result.append(self.createTerm(
                None,
                z3c.form.widget.SequenceWidget.noValueToken,
                _("Select a score"),
                ))
        for score in scoresystem.scores:
            title = score[0]
            result.append(self.createTerm(
                    score[0],
                    'scr-%s' % unicode(title).encode('punycode'),
                    title,
                    ))
        return result


def failingreportscorefactory():
    return FailingReportScores


class IRequestFailingReport(Interface):

    source = zope.schema.Choice(
        title=(u"Report Activity"),
        source="schooltool.gradebook.TermActivityChoices",
        required=True)


class ITextMinmaxScore(Interface):

    score = zope.schema.TextLine(
        title=_(u'Score'),
        required=True)


class IDiscreteValuesMinmaxScore(Interface):

    score = zope.schema.Choice(
        title=(u"Score"),
        source="schooltool.gradebook.FailingReportScores",
        required=True)


class FailingTextScoreValidator(z3c.form.validator.SimpleFieldValidator):

    def validate(self, value):
        scoresystem = self.context.get('scoresystem')
        if not scoresystem:
            raise zope.schema.interfaces.RequiredMissing()
        if (value is not self.field.missing_value and
            not scoresystem.isValidScore(value)):
            raise z3c.form.converter.FormatterValidationError(
                _("${value} is not valid in ${scoresystem}.",
                    mapping={
                        'value': value,
                        'scoresystem': scoresystem.title,
                    }),
                value)
        return z3c.form.validator.SimpleFieldValidator.validate(self, value)


class FlourishRequestFailingReportView(RequestRemoteReportDialog):

    fields = z3c.form.field.Fields(IRequestFailingReport)

    report_builder = 'failures_by_term.pdf'

    def resetForm(self):
        RequestRemoteReportDialog.resetForm(self)
        self.form_params['term'] = self.context
        self.updateWidgets()
        if 'score' not in self.widgets:
            self.addScoreField()
        self.form_params['scoresystem'] = self.scoresystem

    def updateWidgets(self):
        super(FlourishRequestFailingReportView, self).updateWidgets()
        if (self.widgets and 'score' in self.widgets and
            unicode(self.source_token) != self.request.get('source_token')):
            widget = self.widgets['score']
            widget.value = widget.__class__(widget.request).value
            widget.ignoreRequest = True
            widget.update()
        self.widgets['source'].onchange = u"ST.dialogs.submit(this)"

    @property
    def source_token(self):
        return self.widgets['source'].value

    @property
    def scoresystem(self):
        widget = self.widgets['source']
        if not widget.value:
            return None
        res = widget.terms.getValue(widget.value[0])
        if not res:
            return None
        worksheet, activity = res
        return activity.scoresystem

    def addScoreField(self):
        scoresystem = self.scoresystem
        if not scoresystem:
            return
        if (IDiscreteValuesScoreSystem.providedBy(scoresystem) and
            scoresystem.scores):
            self.fields += z3c.form.field.Fields(IDiscreteValuesMinmaxScore['score'])
        else:
            self.fields += z3c.form.field.Fields(ITextMinmaxScore['score'])

    @property
    def score_title(self):
        scoresystem = self.scoresystem
        if scoresystem and IDiscreteValuesScoreSystem.providedBy(scoresystem):
            if scoresystem._isMaxPassingScore:
                return _('Maximum Passing Score')
        return _('Minimum Passing Score')

    def updateTaskParams(self, task):
        term = self.context
        deployedWorksheet, activity = self.form_params['source']
        task.request_params['activity'] = '%s|%s|%s' % (
            term.__name__, deployedWorksheet.__name__, activity.__name__)
        task.request_params['min'] = self.form_params.get('score')


RequestFailing_score_title = z3c.form.widget.ComputedWidgetAttribute(
    lambda adapter: translate(adapter.view.score_title, context=adapter.request),
    view=FlourishRequestFailingReportView,
    field=ITextMinmaxScore['score']
    )


z3c.form.validator.WidgetValidatorDiscriminators(
    FailingTextScoreValidator,
    view=FlourishRequestFailingReportView,
    field=ITextMinmaxScore['score'])


RequestFailing_score_discrete_title = z3c.form.widget.ComputedWidgetAttribute(
    lambda adapter: translate(adapter.view.score_title, context=adapter.request),
    view=FlourishRequestFailingReportView,
    field=IDiscreteValuesMinmaxScore['score']
    )


class RequestFailingReportView(BrowserView):

    def title(self):
        return _('Request Failures by Term Report')

    def current_source(self):
        if 'source' in self.request:
            return self.request['source']
        return ''

    def getScoreSystem(self, source):
        termName, worksheetName, activityName = source.split('|')
        root = IGradebookRoot(ISchoolToolApplication(None))
        return root.deployed[worksheetName][activityName].scoresystem

    def choices(self):
        """Get  a list of the possible choices for report activities."""
        result = {
            'name': _('Choose a report activity'),
            'value': '',
            }
        results = [result]
        root = IGradebookRoot(ISchoolToolApplication(None))
        term = self.context
        schoolyear = ISchoolYear(term)
        deployedKey = '%s_%s' % (schoolyear.__name__, term.__name__)
        for key in root.deployed:
            if key.startswith(deployedKey):
                deployedWorksheet = root.deployed[key]
                for activity in deployedWorksheet.values():
                    if ICommentScoreSystem.providedBy(activity.scoresystem):
                        continue
                    name = '%s - %s - %s' % (term.title,
                        deployedWorksheet.title, activity.title)
                    value = '%s|%s|%s' % (term.__name__,
                        deployedWorksheet.__name__, activity.__name__)
                    result = {
                        'name': name,
                        'value': value,
                        }
                    results.append(result)
        return results

    def minmax(self):
        ismax = False
        current = self.current_source()
        if current:
            ss = self.getScoreSystem(current)
            if IDiscreteValuesScoreSystem.providedBy(ss):
                if ss._isMaxPassingScore:
                    ismax = True
        if ismax:
            return _('Maximum Passing Score')
        else:
            return _('Minimum Passing Score')

    def scores(self):
        results = []
        current = self.current_source()
        if current:
            ss = self.getScoreSystem(current)
            if IDiscreteValuesScoreSystem.providedBy(ss):
                for score in ss.scores:
                    result = {
                        'name': score[0],
                        'value': score[0],
                        'selected': score[0] == ss._minPassingScore,
                        }
                    results.append(result)
        return results

    def getErrorMessage(self):
        return _('You must specify both a report activity and a minimum passing score.')

    def update(self):
        self.message = ''
        if 'form-submitted' in self.request:
            if 'CANCEL' in self.request:
                self.request.response.redirect(self.nextURL())
            elif 'DOWNLOAD' in self.request:
                if not (self.request['source'] and self.request['score']):
                    self.message = self.getErrorMessage()
                else:
                    url = '%s?activity=%s&min=%s' % (self.reportURL(),
                        self.request['source'], self.request['score'])
                    self.request.response.redirect(url)

    def reportURL(self):
        return absoluteURL(self.context, self.request) + '/failures_by_term.pdf'

    def nextURL(self):
        return absoluteURL(self.context, self.request) + '/reports'


class RequestAbsencesByDayView(BrowserView):

    def title(self):
        return _('Request Absences By Day Report')

    def currentDay(self):
        day = self.request.get('day', None)
        if day is None:
            tod = datetime.now()
            return '%d-%02d-%02d' % (tod.year, tod.month, tod.day)
        else:
            return day

    def isValidDate(self):
        day = self.currentDay()
        try:
            year, month, day = [int(part) for part in day.split('-')]
            datetime(year, month, day)
        except:
            return False
        date = datetime.date(datetime(year, month, day))
        return self.context.first <= date <= self.context.last

    def getErrorMessage(self):
        return _('You must specify a valid date within the school year.')

    def update(self):
        self.message = ''
        if 'form-submitted' in self.request:
            if 'CANCEL' in self.request:
                self.request.response.redirect(self.nextURL())
            elif 'DOWNLOAD' in self.request:
                if not self.isValidDate():
                    self.message = self.getErrorMessage()
                else:
                    url = '%s?day=%s' % (self.reportURL(),
                        self.request['day'])
                    self.request.response.redirect(url)

    def reportURL(self):
        return absoluteURL(self.context, self.request) + '/absences_by_day.pdf'

    def nextURL(self):
        return absoluteURL(self.context, self.request) + '/reports'


class RequestStudentReportView(BrowserView):

    def __call__(self):
        """Make sure there is a current term."""
        if getUtility(IDateManager).current_term is None:
            template = ViewPageTemplateFile('templates/no_current_term.pt')
            return template(self)
        return super(RequestStudentReportView, self).__call__()

    def action(self):
        index = self.request['PATH_INFO'].rfind('/') + 1
        return self.request['PATH_INFO'][index:]

    def title(self):
        if self.action() == 'request_report_card.html':
            return _('Request Report Card')
        else:
            return _('Request Detailed Student Report')

    def availableTerms(self):
        current_term = getUtility(IDateManager).current_term
        current_year = ISchoolYear(current_term)
        result = {
            'title': current_year.__name__,
            'value': '',
            'selected': True,
            }
        results = [result]
        for term in current_year.values():
            result = {
                'title': term.title,
                'value': '?term=' + term.__name__,
                'selected': False,
                }
            results.append(result)
        return results

    def update(self):
        self.message = ''
        if 'form-submitted' in self.request:
            if 'CANCEL' in self.request:
                self.request.response.redirect(self.nextURL())
            elif 'DOWNLOAD' in self.request:
                url = '%s%s' % (self.reportURL(), self.request['selectedTerm'])
                self.request.response.redirect(url)

    def reportURL(self):
        if self.action() == 'request_report_card.html':
            url = '/report_card.pdf'
        else:
            url = '/student_detail.pdf'
        return absoluteURL(self.context, self.request) + url

    def nextURL(self):
        return absoluteURL(self.context, self.request) + '/reports'


class RequestReportDownloadDialogBase(Dialog):

    @property
    def file_type(self):
        if 'file_type' in self.request:
            return unquote_plus(self.request['file_type'])

    @property
    def description(self):
        if 'description' in self.request:
            return unquote_plus(self.request['description'])


class FlourishRequestStudentReportView(RequestReportDownloadDialogBase,
                                       RequestStudentReportView):

    def update(self):
        RequestReportDownloadDialogBase.update(self)
        RequestStudentReportView.update(self)


class IRequestAbsencesByDayForm(Interface):

    date = zope.schema.Date(
        title=_(u'Date'),
        required=True)


class DayMustBeInSchoolYear(zope.schema.interfaces.ValidationError):
    __doc__ = _('You must specify a valid date within the school year.')


class AbsenceByDayValidator(z3c.form.validator.SimpleFieldValidator):

    def validate(self, value):
        date = value
        if (date is None or
            date < self.view.schoolyear.first or
            date > self.view.schoolyear.last):
            raise DayMustBeInSchoolYear(value)


class FlourishRequestAbsencesByDayView(RequestRemoteReportDialog):

    fields = z3c.form.field.Fields(IRequestAbsencesByDayForm)

    report_builder = 'absences_by_day.pdf'

    title = _('Request Absences By Day Report')

    @property
    def schoolyear(self):
        return self.context

    def update(self):
        self.message = ''
        RequestRemoteReportDialog.update(self)

    def updateTaskParams(self, task):
        date = self.form_params.get('date')
        if date is not None:
            day = '%d-%02d-%02d' % (date.year, date.month, date.day)
            task.request_params['day'] = day


z3c.form.validator.WidgetValidatorDiscriminators(
    AbsenceByDayValidator,
    view=FlourishRequestAbsencesByDayView,
    field=IRequestAbsencesByDayForm['date'])


class FlourishRequestSectionAbsencesView(RequestRemoteReportDialog):

    report_builder = 'section_absences.pdf'


class FlourishRequestPrintableWorksheetView(RequestRemoteReportDialog):

    report_builder = 'gradebook.pdf'
    task_factory = GradebookReportTask


class FlourishRequestGradebookExportView(RequestXLSReportDialog):

    report_builder = 'export.xls'
    task_factory = TraversableXLSReportTask

    @property
    def target(self):
        worksheet = self.context.__parent__
        activities = worksheet.__parent__
        return (activities.__parent__, activities.__name__)


class FlourishRequestReportSheetsExportView(RequestXLSReportDialog):

    report_builder = 'export_report_sheets.xls'


class FlourishRequestReportCardView(RequestRemoteReportDialog):

    report_builder = 'report_card.pdf'


class FlourishRequestStudentDetailReportView(RequestRemoteReportDialog):

    report_builder = 'student_detail.pdf'
