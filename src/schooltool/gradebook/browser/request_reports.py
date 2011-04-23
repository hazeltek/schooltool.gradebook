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
Request PDF Views
"""

from datetime import datetime

from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import getUtility
from zope.publisher.browser import BrowserView
from zope.traversing.browser.absoluteurl import absoluteURL

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import IDateManager

from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook.interfaces import IGradebookRoot
from schooltool.requirement.interfaces import ICommentScoreSystem
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem


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

