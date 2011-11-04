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
Gradebook Views
"""

__docformat__ = 'reStructuredText'

import csv
import datetime
from decimal import Decimal
from StringIO import StringIO
import urllib

from zope.container.interfaces import INameChooser
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryUtility
from zope.cachedescriptors.property import Lazy
from zope.html.field import HtmlFragment
from zope.publisher.browser import BrowserView
from zope.schema import ValidationError, TextLine
from zope.schema.interfaces import IVocabularyFactory
from zope.security import proxy
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.viewlet import viewlet
from zope.i18n.interfaces.locales import ICollator

from z3c.form import form as z3cform
from z3c.form import field, button

import schooltool.skin.flourish.page
import schooltool.skin.flourish.form
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.common.inlinept import InheritTemplate
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.course.interfaces import ISection, ISectionContainer
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.gradebook.activity import createSourceString, getSourceObj
from schooltool.gradebook.activity import Worksheet, LinkedColumnActivity
from schooltool.gradebook.browser.report_utils import buildHTMLParagraphs
from schooltool.gradebook.gradebook import (getCurrentSectionTaught,
    setCurrentSectionTaught, getCurrentSectionAttended,
    setCurrentSectionAttended)
from schooltool.person.interfaces import IPerson
from schooltool.gradebook.journal import ABSENT, TARDY
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.requirement.interfaces import (ICommentScoreSystem,
    IValuesScoreSystem, IDiscreteValuesScoreSystem, IRangedValuesScoreSystem,
    IScoreSystemContainer)
from schooltool.schoolyear.interfaces import ISchoolYear, ISchoolYearContainer
from schooltool.table.table import simple_form_key
from schooltool.term.interfaces import ITerm, IDateManager
from schooltool.skin import flourish

from schooltool.gradebook import GradebookMessage as _


GradebookCSSViewlet = viewlet.CSSViewlet("gradebook.css")

DISCRETE_SCORE_SYSTEM = 'd'
RANGED_SCORE_SYSTEM = 'r'
COMMENT_SCORE_SYSTEM = 'c'
SUMMARY_TITLE = _('Summary')


def getColumnKeys(gradebook):
    column_keys =  [('total', _("Total")), ('average', _("Ave."))]
    journal_data = interfaces.ISectionJournalData(ISection(gradebook), None)
    if journal_data is not None:
        column_keys = ([('absences', _("Abs.")), ('tardies', _("Trd."))] +
            column_keys)
    return column_keys


def convertAverage(average, scoresystem):
    """converts average to display value of the given scoresystem"""
    if scoresystem is None:
        return '%.1f%%' % average
    for score in scoresystem.scores:
        if average >= score[3]:
            return score[0]


class GradebookStartup(object):
    """A view for entry into into the gradebook or mygrades views."""

    template = ViewPageTemplateFile('templates/gradebook_startup.pt')

    def __call__(self):
        if IPerson(self.request.principal, None) is None:
            url = absoluteURL(ISchoolToolApplication(None), self.request)
            url = '%s/auth/@@login.html?nexturl=%s' % (url, self.request.URL)
            self.request.response.redirect(url)
            return ''
        return self.template()

    def update(self):
        self.person = IPerson(self.request.principal)
        self.sectionsTaught = list(IInstructor(self.person).sections())
        self.sectionsAttended = list(ILearner(self.person).sections())

        if self.sectionsTaught:
            section = getCurrentSectionTaught(self.person)
            if section is None or section.__parent__ is None:
                section = self.sectionsTaught[0]
            self.gradebookURL = absoluteURL(section, self.request)+ '/gradebook'
            if not self.sectionsAttended:
                self.request.response.redirect(self.gradebookURL)
        if self.sectionsAttended:
            section = getCurrentSectionAttended(self.person)
            if section is None or section.__parent__ is None:
                section = self.sectionsAttended[0]
            self.mygradesURL = absoluteURL(section, self.request) + '/mygrades'
            if not self.sectionsTaught:
                self.request.response.redirect(self.mygradesURL)


class FlourishGradebookStartup(GradebookStartup, flourish.page.Page):

    def render(self, *args, **kw):
        if IPerson(self.request.principal, None) is None:
            url = absoluteURL(ISchoolToolApplication(None), self.request)
            url = '%s/auth/@@login.html?nexturl=%s' % (url, self.request.URL)
            self.request.response.redirect(url)
            return ''
        return flourish.page.Page.render(self, *args, **kw)

    def __call__(self, *args, **kw):
        if IPerson(self.request.principal, None) is None:
            url = absoluteURL(ISchoolToolApplication(None), self.request)
            url = '%s/auth/@@login.html?nexturl=%s' % (url, self.request.URL)
            self.request.response.redirect(url)
            return ''
        return flourish.page.Page.__call__(self, *args, **kw)


class GradebookStartupNavLink(flourish.page.LinkViewlet):

    @property
    def title(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return ''

        sectionsTaught = list(IInstructor(person).sections())
        sectionsAttended = list(ILearner(person).sections())

        if (not sectionsTaught and
            not sectionsAttended):
            return ''

        return _('Gradebook')

    @property
    def url(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return ''
        app = ISchoolToolApplication(None)
        app_url = absoluteURL(app, self.request)
        return '%s/gradebook.html' % app_url


class SectionGradebookRedirectView(BrowserView):
    """A view for redirecting from a section to either the gradebook for its
       current worksheet or the final grades view for the section.
       In the case of final grades for the section, the query string,
       ?final=yes is used to isntruct this view to redirect to the final grades
       view instead of the gradebook"""

    def __call__(self):
        person = IPerson(self.request.principal)
        activities = interfaces.IActivities(self.context)
        ensureAtLeastOneWorksheet(activities)
        current_worksheet = activities.getCurrentWorksheet(person)
        url = absoluteURL(activities, self.request)
        if current_worksheet is not None:
            url = absoluteURL(current_worksheet, self.request)
            if person in self.context.members:
                url += '/mygrades'
            else:
                url += '/gradebook'
        self.request.response.redirect(url)
        return "Redirecting..."


class GradebookBase(BrowserView):

    def __init__(self, context, request):
        super(GradebookBase, self).__init__(context, request)
        self.changed = False

    @property
    def students(self):
        return self.context.students

    @property
    def scores(self):
        results = {}
        person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheet = gradebook.getCurrentWorksheet(person)
        for activity in gradebook.getWorksheetActivities(worksheet):
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                continue
            ss = activity.scoresystem
            if IDiscreteValuesScoreSystem.providedBy(ss):
                result = [DISCRETE_SCORE_SYSTEM] + [score[0]
                    for score in ss.scores]
            elif IRangedValuesScoreSystem.providedBy(ss):
                result = [RANGED_SCORE_SYSTEM, ss.min, ss.max]
            else:
                result = [COMMENT_SCORE_SYSTEM]
            resultStr = ', '.join(["'%s'" % unicode(value)
                for value in result])
            results[activity.__name__] = resultStr
        return results

    def breakJSString(self, origstr):
        newstr = unicode(origstr)
        newstr = newstr.replace('\n', '')
        newstr = newstr.replace('\r', '')
        newstr = "\\'".join(newstr.split("'"))
        newstr = '\\"'.join(newstr.split('"'))
        return newstr

    @property
    def warningText(self):
        return _('You have some changes that have not been saved.  Click OK to save now or CANCEL to continue without saving.')


class SectionFinder(GradebookBase):
    """Base class for GradebookOverview and MyGradesView"""

    def getUserSections(self):
        if self.isTeacher:
            return list(IInstructor(self.person).sections())
        else:
            return list(ILearner(self.person).sections())

    def getTermId(self, term):
        year = ISchoolYear(term)
        return '%s.%s' % (simple_form_key(year), simple_form_key(term))

    def getTerms(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        terms = []
        for section in self.getUserSections():
            term = ITerm(section)
            if term not in terms:
                terms.append(term)
        return [{'title': '%s / %s' % (ISchoolYear(term).title, term.title),
                 'form_id': self.getTermId(term),
                 'selected': term is currentTerm and 'selected' or None}
                for term in terms]

    def getSectionId(self, section):
        term = ITerm(section)
        year = ISchoolYear(term)
        return '%s.%s.%s' % (simple_form_key(year), simple_form_key(term),
                             simple_form_key(section))

    def getSections(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        for section in self.getUserSections():
            term = ITerm(section)
            if term != currentTerm:
                continue
            url = absoluteURL(section, self.request)
            if self.isTeacher:
                url += '/gradebook'
            else:
                url += '/mygrades'
            title = '%s - %s' % (", ".join([course.title
                                            for course in section.courses]),
                                 section.title)
            css = 'inactive-menu-item'
            if section == currentSection:
                css = 'active-menu-item'
            yield {'obj': section, 'url': url, 'title': title, 'css': css,
                   'form_id': self.getSectionId(section),
                   'selected': title==self.getCurrentSection() and 'selected' or None}

    @property
    def worksheets(self):
        results = []
        for worksheet in self.context.worksheets:
            url = absoluteURL(worksheet, self.request)
            if self.isTeacher:
                url += '/gradebook'
            else:
                url += '/mygrades'
            result = {
                'title': worksheet.title[:15],
                'url': url,
                'current': worksheet == self.getCurrentWorksheet(),
                }
            results.append(result)
        return results

    def getCurrentSection(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        return '%s - %s' % (", ".join([course.title
                                       for course in section.courses]),
                            section.title)

    def getCurrentTerm(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        term = ITerm(section)
        return '%s / %s' % (ISchoolYear(term).title, term.title)

    def handleTermChange(self):
        if 'currentTerm' in self.request:
            currentSection = ISection(proxy.removeSecurityProxy(self.context))
            try:
                currentCourse = list(currentSection.courses)[0]
            except (IndexError,):
                currentCourse = None
            currentTerm = ITerm(currentSection)
            requestTermId = self.request['currentTerm']
            if requestTermId != self.getTermId(currentTerm):
                newSection = None
                for section in self.getUserSections():
                    term = ITerm(section)
                    if self.getTermId(term) == requestTermId:
                        try:
                            temp = list(section.courses)[0]
                        except (IndexError,):
                            temp = None
                        if currentCourse == temp:
                            newSection = section
                            break
                        if newSection is None:
                            newSection = section
                url = absoluteURL(newSection, self.request)
                if self.isTeacher:
                    url += '/gradebook'
                else:
                    url += '/mygrades'
                self.request.response.redirect(url)
                return True
        return False

    def handleSectionChange(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        if 'currentSection' in self.request:
            for section in self.getSections():
                if self.getSectionId(section['obj']) == self.request['currentSection']:
                    if section['obj'] == ISection(gradebook):
                        break
                    self.request.response.redirect(section['url'])
                    return True
        return False

    def processColumnPreferences(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        scoresystems = IScoreSystemContainer(ISchoolToolApplication(None))
        if self.isTeacher:
            person = self.person
        else:
            section = ISection(gradebook)
            instructors = list(section.instructors)
            if len(instructors) == 0:
                person = None
            else:
                person = instructors[0]
        if person is None:
            columnPreferences = {}
        else:
            columnPreferences = gradebook.getColumnPreferences(person)
        column_keys_dict = dict(getColumnKeys(gradebook))

        journal_data = interfaces.ISectionJournalData(ISection(gradebook), None)
        prefs = columnPreferences.get('absences', {})
        if journal_data is None:
            self.absences_hide = True
        else:
            self.absences_hide = prefs.get('hide', True)
        self.absences_label = prefs.get('label', '')
        if len(self.absences_label) == 0:
            self.absences_label = column_keys_dict.get('absences')

        prefs = columnPreferences.get('tardies', {})
        if journal_data is None:
            self.tardies_hide = True
        else:
            self.tardies_hide = prefs.get('hide', True)
        self.tardies_label = prefs.get('label', '')
        if len(self.tardies_label) == 0:
            self.tardies_label = column_keys_dict.get('tardies')

        prefs = columnPreferences.get('total', {})
        self.total_hide = prefs.get('hide', False)
        self.total_label = prefs.get('label', '')
        if len(self.total_label) == 0:
            self.total_label = column_keys_dict['total']

        prefs = columnPreferences.get('average', {})
        self.average_hide = prefs.get('hide', False)
        self.average_label = prefs.get('label', '')
        if len(self.average_label) == 0:
            self.average_label = column_keys_dict['average']
        self.average_scoresystem = scoresystems.get(
            prefs.get('scoresystem', ''))

        prefs = columnPreferences.get('due_date', {})
        self.due_date_hide = prefs.get('hide', False)

        self.apply_all_colspan = 1
        if gradebook.context.deployed:
            self.total_hide = True
            self.average_hide = True
        if not self.absences_hide:
            self.apply_all_colspan += 1
        if not self.tardies_hide:
            self.apply_all_colspan += 1
        if not self.total_hide:
            self.apply_all_colspan += 1
        if not self.average_hide:
            self.apply_all_colspan += 1


class GradebookOverview(SectionFinder):
    """Gradebook Overview/Table"""

    isTeacher = True

    @Lazy
    def students_info(self):
        result = []
        for student in self.context.students:
            insecure_student = proxy.removeSecurityProxy(student)
            result.append({
                    'title': student.title,
                    'username': insecure_student.username,
                    'id': insecure_student.username,
                    'url': absoluteURL(student, self.request),
                    'gradeurl': '%s/%s' % (
                        absoluteURL(self.context, self.request),
                        insecure_student.username),
                    'object': student,
                    })
        return result

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        self.message = ''

        """Make sure the current worksheet matches the current url"""
        worksheet = gradebook.context
        gradebook.setCurrentWorksheet(self.person, worksheet)
        setCurrentSectionTaught(self.person, gradebook.section)

        """Retrieve column preferences."""
        self.processColumnPreferences()

        """Retrieve sorting information and store changes of it."""
        if 'sort_by' in self.request:
            sort_by = self.request['sort_by']
            key, reverse = gradebook.getSortKey(self.person)
            if sort_by == key:
                reverse = not reverse
            else:
                reverse = False
            gradebook.setSortKey(self.person, (sort_by, reverse))
        self.sortKey = gradebook.getSortKey(self.person)

        """Handle change of current term."""
        if self.handleTermChange():
            return

        """Handle change of current section."""
        if self.handleSectionChange():
            return

        """Handle changes to due date filter"""
        if 'num_weeks' in self.request:
            flag, weeks = gradebook.getDueDateFilter(self.person)
            if 'due_date' in self.request:
                flag = True
            else:
                flag = False
            weeks = self.request['num_weeks']
            gradebook.setDueDateFilter(self.person, flag, weeks)

        """Handle changes to scores."""
        evaluator = getName(IPerson(self.request.principal))
        for student in self.students_info:
            for activity in gradebook.activities:
                # Create a hash and see whether it is in the request
                act_hash = activity.__name__
                cell_name = '%s_%s' % (act_hash, student['username'])
                if cell_name in self.request:
                    # XXX: TODO: clean up this mess.
                    #      The details of when to remove the evaluation, etc.
                    #      do not belong in the view anyway.
                    #      The code could also make use of something's
                    #      ScoreValidationError (StudentGradebookFormAdapter?)

                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        cell_score_value = activity.scoresystem.fromUnicode(
                            self.request[cell_name])
                    except (ValidationError, ValueError):
                        self.message = _(
                            'Invalid scores (highlighted in red) were not saved.')
                        continue
                    score = gradebook.getScore(student['object'], activity)
                    # Delete the score
                    if score and cell_score_value is UNSCORED:
                        self.context.removeEvaluation(student['object'], activity)
                        self.changed = True
                    # Do nothing
                    elif not score and cell_score_value is UNSCORED:
                        continue
                    # Replace the score or add new one
                    elif not score or cell_score_value != score.value:
                        self.changed = True
                        self.context.evaluate(
                            student['object'], activity, cell_score_value, evaluator)

    def getCurrentWorksheet(self):
        return self.context.getCurrentWorksheet(self.person)

    def getDueDateFilter(self):
        flag, weeks = self.context.getDueDateFilter(self.person)
        return flag

    def weeksChoices(self):
        return [unicode(choice) for choice in range(1, 10)]

    def getCurrentWeeks(self):
        flag, weeks = self.context.getDueDateFilter(self.person)
        return weeks

    def getLinkedActivityInfo(self, activity):
        source = getSourceObj(activity.source)
        insecure_activity = proxy.removeSecurityProxy(activity)
        insecure_source = proxy.removeSecurityProxy(source)

        if interfaces.IActivity.providedBy(insecure_source):
            short, long, best_score = self.getActivityAttrs(source)
        elif interfaces.IWorksheet.providedBy(insecure_source):
            long = source.title
            short = activity.label or long
            if len(short) > 5:
                short = short[:5].strip()
            best_score = '100'
        else:
            short = long = best_score = ''

        return {
            'linked_source': source,
            'scorable': False,
            'shortTitle': short,
            'longTitle': long,
            'max': best_score,
            'hash': insecure_activity.__name__,
            'object': activity,
            'updateGrades': '',
            }

    def getActivityInfo(self, activity):
        insecure_activity = proxy.removeSecurityProxy(activity)

        if interfaces.ILinkedColumnActivity.providedBy(insecure_activity):
            return self.getLinkedActivityInfo(activity)

        short, long, best_score = self.getActivityAttrs(activity)

        scorable = not (
            ICommentScoreSystem.providedBy(insecure_activity.scoresystem) or
            interfaces.ILinkedActivity.providedBy(insecure_activity))

        if interfaces.ILinkedActivity.providedBy(insecure_activity):
            updateGrades = '%s/updateGrades.html' % (
                absoluteURL(insecure_activity, self.request))
        else:
            updateGrades = ''

        return {
            'linked_source': None,
            'scorable': scorable,
            'shortTitle': short,
            'longTitle': long,
            'max': best_score,
            'hash': insecure_activity.__name__,
            'object': activity,
            'updateGrades': updateGrades,
            }

    @Lazy
    def filtered_activity_info(self):
        result = []
        for activity in self.getFilteredActivities():
            info = self.getActivityInfo(activity)
            result.append(info)
        return result

    def getActivityAttrs(self, activity):
        longTitle = activity.title
        shortTitle = activity.label or longTitle
        shortTitle = shortTitle.replace(' ', '')
        if len(shortTitle) > 5:
            shortTitle = shortTitle[:5].strip()
        ss = proxy.removeSecurityProxy(activity.scoresystem)
        if ICommentScoreSystem.providedBy(ss):
            bestScore = ''
        else:
            bestScore = ss.getBestScore()
        return shortTitle, longTitle, bestScore

    def activities(self):
        """Get  a list of all activities."""
        self.person = IPerson(self.request.principal)
        results = []
        deployed = proxy.removeSecurityProxy(self.context).context.deployed
        for activity_info in self.filtered_activity_info:
            result = dict(activity_info)
            result.update({
                'canDelete': not deployed,
                'moveLeft': not deployed,
                'moveRight': not deployed,
                })
            results.append(result)
        if results:
            results[0]['moveLeft'] = False
            results[-1]['moveRight'] = False
        return results

    def scorableActivities(self):
        """Get a list of those activities that can be scored."""
        return [result for result in self.activities() if result['scorable']]

    def isFiltered(self, activity):
        if interfaces.ILinkedColumnActivity.providedBy(activity):
            return False
        flag, weeks = self.context.getDueDateFilter(self.person)
        if not flag:
            return False
        today = queryUtility(IDateManager).today
        cutoff = today - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff

    def getFilteredActivities(self):
        activities = self.context.getCurrentActivities(self.person)
        return[activity for activity in activities
               if not self.isFiltered(activity)]

    def getStudentActivityValue(self, student_info, activity):
        gradebook = proxy.removeSecurityProxy(self.context)
        score = gradebook.getScore(student_info['object'], activity)
        if not score:
            value = ''
        else:
            value = score.value
        act_hash = activity.__name__
        cell_name = '%s_%s' % (act_hash, student_info['username'])
        if cell_name in self.request:
            value = self.request[cell_name]

        if value and ICommentScoreSystem.providedBy(activity.scoresystem):
            value = '...'

        return value

    def table(self):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheet = gradebook.getCurrentWorksheet(self.person)
        section = ISection(worksheet)

        journal_data = interfaces.ISectionJournalData(section, None)
        rows = []
        for student_info in self.students_info:
            grades = []
            for activity_info in self.filtered_activity_info:
                activity = activity_info['object']
                value = self.getStudentActivityValue(student_info, activity)
                source = activity_info['linked_source']
                if source is not None:
                    if value and interfaces.IWorksheet.providedBy(source):
                        value = '%.1f' % value
                grade = {
                    'activity': activity_info['hash'],
                    'editable': activity_info['scorable'],
                    'value': value
                    }
                grades.append(grade)

            total, raw_average = gradebook.getWorksheetTotalAverage(
                worksheet, student_info['object'])

            total = "%.1f" % total

            if raw_average is UNSCORED:
                average = _('N/A')
            else:
                average = convertAverage(raw_average, self.average_scoresystem)

            absences = tardies = 0
            if (journal_data and not (self.absences_hide and self.tardies_hide)):
                # XXX: opt: perm checks may breed here
                meetings = journal_data.recordedMeetings(student_info['object'])
                for meeting in meetings:
                    grade = journal_data.getGrade(
                        student_info['object'], meeting)
                    if grade == ABSENT:
                        absences += 1
                    elif grade == TARDY:
                        tardies += 1

            rows.append(
                {'student': student_info,
                 'grades': grades,
                 'absences': unicode(absences),
                 'tardies': unicode(tardies),
                 'total': total,
                 'average': average,
                 'raw_average': raw_average,
                })

        # Do the sorting
        key, reverse = self.sortKey
        self.collator = ICollator(self.request.locale)
        def generateStudentKey(row):
            return self.collator.key(row['student']['title'])
        def generateKey(row):
            if key == 'student':
                return generateStudentKey(row)
            elif key == 'total':
                return (float(row['total']), generateStudentKey(row))
            elif key == 'average':
                if row['raw_average'] is UNSCORED:
                    return ('', generateStudentKey(row))
                else:
                    return (row['average'], generateStudentKey(row))
            elif key in ['absences', 'tardies']:
                if journal_data is None:
                    return (0, generateStudentKey(row))
                else:
                    return (int(row[key]), generateStudentKey(row))
            else: # sorting by activity
                grades = dict([(unicode(grade['activity']), grade['value'])
                               for grade in row['grades']])
                if not grades.get(key, ''):
                    return (1, generateStudentKey(row))
                else:
                    return (0, grades.get(key), generateStudentKey(row))
        return sorted(rows, key=generateKey, reverse=reverse)

    @property
    def descriptions(self):
        self.person = IPerson(self.request.principal)
        results = []
        for activity in self.getFilteredActivities():
            description = activity.title
            result = {
                'act_hash': activity.__name__,
                'description': self.breakJSString(description),
                }
            results.append(result)
        return results

    @property
    def deployed(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        return gradebook.context.deployed


class FlourishGradebookOverview(GradebookOverview,
                                flourish.page.WideContainerPage):
    """flourish Gradebook Overview/Table"""

    has_header = False
    page_class = 'page grid'

    @property
    def journal_present(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        return interfaces.ISectionJournalData(section, None) is not None

    def handleYearChange(self):
        if 'currentYear' in self.request:
            currentSection = ISection(proxy.removeSecurityProxy(self.context))
            currentYear = ISchoolYear(ITerm(currentSection))
            requestYearId = self.request['currentYear']
            if requestYearId != currentYear.__name__:
                for section in self.getUserSections():
                    year = ISchoolYear(ITerm(section))
                    if year.__name__ == requestYearId:
                        newSection = section
                        break
                else:
                    return False
                url = absoluteURL(newSection, self.request)
                if self.isTeacher:
                    url += '/gradebook'
                else:
                    url += '/mygrades'
                self.request.response.redirect(url)
                return True
        return False

    def handlePreferencesChange(self):
        if not self.isTeacher:
            return
        gradebook = proxy.removeSecurityProxy(self.context)
        columnPreferences = gradebook.getColumnPreferences(self.person)
        show = self.request.get('show')
        hide = self.request.get('hide')
        if show or hide:
            column_keys_dict = dict(getColumnKeys(gradebook))
            if show not in column_keys_dict and hide not in column_keys_dict:
                return
            if show:
                prefs = columnPreferences.setdefault(show, {})
                prefs['hide'] = False
            if hide:
                prefs = columnPreferences.setdefault(hide, {})
                prefs['hide'] = True
            gradebook.setColumnPreferences(self.person, columnPreferences)
        elif 'scoresystem' in self.request:
            vocab = queryUtility(IVocabularyFactory,
                'schooltool.requirement.discretescoresystems')(None)
            scoresystem = self.request.get('scoresystem', '')
            if scoresystem:
                name = vocab.getTermByToken(scoresystem).value.__name__
            else:
                name = scoresystem
            columnPreferences.get('average', {})['scoresystem'] = name
            gradebook.setColumnPreferences(self.person, columnPreferences)

    def handleMoveActivity(self):
        if not self.isTeacher or self.deployed:
            return
        if 'move_left' in self.request:
            name, change = self.request['move_left'], -1
        elif 'move_right' in self.request:
            name, change = self.request['move_right'], 1
        else:
            return
        worksheet = proxy.removeSecurityProxy(self.context).context
        keys = worksheet.keys()
        if name in keys:
            new_pos = keys.index(name) + change
            if new_pos >= 0 and new_pos < len(keys):
                worksheet.changePosition(name, new_pos)

    def handleDeleteActivity(self):
        if not self.isTeacher or self.deployed:
            return
        if 'delete' in self.request:
            name = self.request['delete']
            worksheet = proxy.removeSecurityProxy(self.context).context
            if name in worksheet.keys():
                del worksheet[name]

    @property
    def scoresystems(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        columnPreferences = gradebook.getColumnPreferences(self.person)
        vocab = queryUtility(IVocabularyFactory,
            'schooltool.requirement.discretescoresystems')(None)
        current = columnPreferences.get('average', {}).get('scoresystem', '')
        results = [{
            'title': _('No score system'),
            'url': '?scoresystem',
            'current': not current,
            }]
        for term in vocab:
            results.append({
                'title': term.value.title,
                'url': '?scoresystem=%s' % term.token,
                'current': term.value.__name__ == current,
                })
        return results

    def update(self):
        """Handle change of current year."""
        self.person = IPerson(self.request.principal)
        if self.handleYearChange():
            return

        """Handle change of column preferences."""
        self.handlePreferencesChange()

        """Handle change of column order."""
        self.handleMoveActivity()

        """Handle removal of column."""
        self.handleDeleteActivity()

        """Everything else handled by old skin method."""
        GradebookOverview.update(self)


class FlourishGradebookYearNavigation(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Overview year navigation viewlet."""


class FlourishGradebookYearNavigationViewlet(flourish.viewlet.Viewlet,
                                             GradebookOverview):
    template = InlineViewPageTemplate('''
    <form method="post"
          tal:attributes="action string:${context/@@absolute_url}">
      <select name="currentYear" class="navigator"
              onchange="this.form.submit()">
        <tal:block repeat="year view/getYears">
          <option
              tal:attributes="value year/form_id;
                              selected year/selected"
              tal:content="year/title" />
        </tal:block>
      </select>
    </form>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    def getYears(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentYear = ISchoolYear(ITerm(currentSection))
        years = []
        for section in self.getUserSections():
            year = ISchoolYear(ITerm(section))
            if year not in years:
                years.append(year)
        return [{'title': year.title,
                 'form_id': year.__name__,
                 'selected': year is currentYear and 'selected' or None}
                for year in years]

    def render(self, *args, **kw):
        return self.template(*args, **kw)


class FlourishGradebookTermNavigation(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Overview term navigation viewlet."""


class FlourishGradebookTermNavigationViewlet(flourish.viewlet.Viewlet,
                                             GradebookOverview):
    template = InlineViewPageTemplate('''
    <form method="post"
          tal:attributes="action string:${context/@@absolute_url}">
      <select name="currentTerm" class="navigator"
              onchange="this.form.submit()">
        <tal:block repeat="term view/getTerms">
          <option
              tal:attributes="value term/form_id;
                              selected term/selected"
              tal:content="term/title" />
        </tal:block>
      </select>
    </form>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    def getTerms(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        currentYear = ISchoolYear(currentTerm)
        terms = []
        for section in self.getUserSections():
            term = ITerm(section)
            if term not in terms and ISchoolYear(term) == currentYear:
                terms.append(term)
        return [{'title': term.title,
                 'form_id': self.getTermId(term),
                 'selected': term is currentTerm and 'selected' or None}
                for term in terms]

    def render(self, *args, **kw):
        return self.template(*args, **kw)


class FlourishGradebookSectionNavigation(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Overview section navigation viewlet."""


class FlourishGradebookSectionNavigationViewlet(flourish.viewlet.Viewlet,
                                                GradebookOverview):
    template = InlineViewPageTemplate('''
    <form method="post"
          tal:attributes="action string:${context/@@absolute_url}">
      <select name="currentSection" class="navigator"
              onchange="this.form.submit()">
        <tal:block repeat="section view/getSections">
	  <option
	      tal:attributes="value section/form_id;
			      selected section/selected;"
	      tal:content="section/title" />
        </tal:block>
      </select>
    </form>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    def getSections(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        for section in self.getUserSections():
            term = ITerm(section)
            if term != currentTerm:
                continue
            url = absoluteURL(section, self.request)
            if self.isTeacher:
                url += '/gradebook'
            else:
                url += '/mygrades'
            css = 'inactive-menu-item'
            if section == currentSection:
                css = 'active-menu-item'
            yield {
                'obj': section,
                'url': url,
                'title': section.title,
                'css': css,
                'form_id': self.getSectionId(section),
                'selected': section==currentSection and 'selected' or None,
                }

    def render(self, *args, **kw):
        return self.template(*args, **kw)


class FlourishGradebookOverviewLinks(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Overview add links viewlet."""


class ActivityAddLink(flourish.page.LinkViewlet):

    @property
    def title(self):
        worksheet = proxy.removeSecurityProxy(self.context).context
        if worksheet.deployed:
            return ''
        return _("Activity")


class FlourishGradebookSettingsLinks(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Settings links viewlet."""


class GradebookTertiaryNavigationManager(flourish.page.TertiaryNavigationManager):

    template = InlineViewPageTemplate("""
        <ul tal:attributes="class view/list_class">
          <li tal:repeat="item view/items"
              tal:attributes="class item/class"
              tal:content="structure item/viewlet">
          </li>
        </ul>
    """)

    @property
    def items(self):
        result = []
        gradebook = proxy.removeSecurityProxy(self.context)
        current = gradebook.context.__name__
        for worksheet in gradebook.worksheets:
            url = '%s/gradebook' % absoluteURL(worksheet, self.request)
            result.append({
                'class': worksheet.__name__ == current and 'active' or None,
                'viewlet': u'<a href="%s">%s</a>' % (url, worksheet.title[:15]),
                })
        return result


class GradeActivity(object):
    """Grading a single activity"""

    @property
    def activity(self):
        act_hash = self.request['activity']
        for activity in self.context.activities:
            if activity.__name__ == act_hash:
                return {'title': activity.title,
                        'max': activity.scoresystem.getBestScore(),
                        'hash': activity.__name__,
                         'obj': activity}

    @property
    def grades(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        for student in self.context.students:
            reqValue = self.request.get(student.username)
            score = gradebook.getScore(student, self.activity['obj'])
            if not score:
                value = reqValue or ''
            else:
                value = reqValue or score.value

            yield {'student': {'title': student.title, 'id': student.username},
                   'value': value}

    def update(self):
        self.messages = []
        if 'CANCEL' in self.request:
            self.request.response.redirect('index.html')

        elif 'UPDATE_SUBMIT' in self.request:
            activity = self.activity['obj']
            evaluator = getName(IPerson(self.request.principal))
            gradebook = proxy.removeSecurityProxy(self.context)
            # Iterate through all students
            for student in self.context.students:
                id = student.username
                if id in self.request:

                    # XXX: heavy code duplication with GradebookOverview

                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        request_score_value = activity.scoresystem.fromUnicode(
                            self.request[id])
                    except (ValidationError, ValueError):
                        message = _(
                            'The grade $value for $name is not valid.',
                            mapping={'value': self.request[id],
                                     'name': student.title})
                        self.messages.append(message)
                        continue
                    score = gradebook.getScore(student, activity)
                    # Delete the score
                    if score and request_score_value is UNSCORED:
                        self.context.removeEvaluation(student, activity)
                    # Do nothing
                    elif not score and request_score_value is UNSCORED:
                        continue
                    # Replace the score or add new one
                    elif not score or request_score_value != score.value:
                        self.context.evaluate(
                            student, activity, request_score_value, evaluator)

            if not len(self.messages):
                self.request.response.redirect('index.html')


class FlourishGradeActivity(GradeActivity, flourish.page.Page):
    """flourish Grading a single activity"""


def getScoreSystemDiscreteValues(ss):
    if IDiscreteValuesScoreSystem.providedBy(ss):
        return (ss.scores[-1][2], ss.scores[0][2])
    elif IRangedValuesScoreSystem.providedBy(ss):
        return (ss.min, ss.max)
    return (0, 0)


class MyGradesView(SectionFinder):
    """Student view of own grades."""

    isTeacher = False

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheet = proxy.removeSecurityProxy(gradebook.context)

        """Make sure the current worksheet matches the current url"""
        worksheet = gradebook.context
        gradebook.setCurrentWorksheet(self.person, worksheet)
        setCurrentSectionAttended(self.person, gradebook.section)

        """Retrieve column preferences."""
        self.processColumnPreferences()

        self.table = []
        count = 0
        for activity in self.context.getCurrentActivities(self.person):
            activity = proxy.removeSecurityProxy(activity)
            score = self.context.getScore(self.person, activity)

            if score:
                if ICommentScoreSystem.providedBy(score.scoreSystem):
                    grade = {
                        'comment': True,
                        'paragraphs': buildHTMLParagraphs(score.value),
                        }
                elif IValuesScoreSystem.providedBy(score.scoreSystem):
                    s_min, s_max = getScoreSystemDiscreteValues(score.scoreSystem)
                    value = score.value
                    if IDiscreteValuesScoreSystem.providedBy(score.scoreSystem):
                        value = score.scoreSystem.getNumericalValue(score.value)
                        if value is None:
                            value = 0
                    count += s_max - s_min
                    grade = {
                        'comment': False,
                        'value': '%s / %s' % (value, score.scoreSystem.getBestScore()),
                        }

                else:
                    grade = {
                        'comment': False,
                        'value': score.value,
                        }

            else:
                grade = {
                    'comment': False,
                    'value': '',
                    }

            title = activity.title
            if activity.description:
                title += ' - %s' % activity.description

            row = {
                'activity': title,
                'grade': grade,
                }
            self.table.append(row)

        if count:
            total, average = gradebook.getWorksheetTotalAverage(worksheet,
                self.person)
            self.average = convertAverage(average, self.average_scoresystem)
        else:
            self.average = None

        """Handle change of current term."""
        if self.handleTermChange():
            return

        """Handle change of current section."""
        self.handleSectionChange()

    def getCurrentWorksheet(self):
        return self.context.getCurrentWorksheet(self.person)


class FlourishMyGradesView(MyGradesView, flourish.page.Page):
    """Flourish student view of own grades."""

    has_header = False

    def handleYearChange(self):
        if 'currentYear' in self.request:
            currentSection = ISection(proxy.removeSecurityProxy(self.context))
            currentYear = ISchoolYear(ITerm(currentSection))
            requestYearId = self.request['currentYear']
            if requestYearId != currentYear.__name__:
                for section in self.getUserSections():
                    year = ISchoolYear(ITerm(section))
                    if year.__name__ == requestYearId:
                        newSection = section
                        break
                else:
                    return False
                url = absoluteURL(newSection, self.request)
                if self.isTeacher:
                    url += '/gradebook'
                else:
                    url += '/mygrades'
                self.request.response.redirect(url)
                return True
        return False

    def update(self):
        """Handle change of year."""
        self.person = IPerson(self.request.principal)
        if self.handleYearChange():
            return

        """Everything else handled by old skin method."""
        MyGradesView.update(self)


class FlourishMyGradesYearNavigation(flourish.page.RefineLinksViewlet):
    """flourish MyGrades Overview year navigation viewlet."""


class FlourishMyGradesYearNavigationViewlet(
    FlourishGradebookYearNavigationViewlet):

    isTeacher = False


class FlourishMyGradesTermNavigation(flourish.page.RefineLinksViewlet):
    """flourish MyGrades Overview term navigation viewlet."""


class FlourishMyGradesTermNavigationViewlet(
    FlourishGradebookTermNavigationViewlet):

    isTeacher = False


class FlourishMyGradesSectionNavigation(flourish.page.RefineLinksViewlet):
    """flourish MyGrades Overview section navigation viewlet."""


class FlourishMyGradesSectionNavigationViewlet(
    FlourishGradebookSectionNavigationViewlet):

    isTeacher = False


class MyGradesTertiaryNavigationManager(flourish.page.TertiaryNavigationManager):

    template = InlineViewPageTemplate("""
        <ul tal:attributes="class view/list_class">
          <li tal:repeat="item view/items"
              tal:attributes="class item/class"
              tal:content="structure item/viewlet">
          </li>
        </ul>
    """)

    @property
    def items(self):
        result = []
        gradebook = proxy.removeSecurityProxy(self.context)
        current = gradebook.context.__name__
        for worksheet in gradebook.worksheets:
            url = '%s/mygrades' % absoluteURL(worksheet, self.request)
            result.append({
                'class': worksheet.__name__ == current and 'active' or None,
                'viewlet': u'<a href="%s">%s</a>' % (url, worksheet.title[:15]),
                })
        return result


class LinkedActivityGradesUpdater(object):
    """Functionality to update grades from a linked activity"""

    def update(self, linked_activity, request):
        evaluator = getName(IPerson(request.principal))
        external_activity = linked_activity.getExternalActivity()
        if external_activity is None:
            msg = "Couldn't find an ExternalActivity match for %s"
            raise LookupError(msg % external_activity.title)
        worksheet = linked_activity.__parent__
        gradebook = interfaces.IGradebook(worksheet)
        for student in gradebook.students:
            external_grade = external_activity.getGrade(student)
            if external_grade is not None:
                score = float(external_grade) * float(linked_activity.points)
                score = Decimal("%.2f" % score)
                gradebook.evaluate(student, linked_activity, score, evaluator)


class UpdateLinkedActivityGrades(LinkedActivityGradesUpdater):
    """A view for updating the grades of a linked activity."""

    def __call__(self):
        self.update(self.context, self.request)
        next_url = absoluteURL(self.context.__parent__, self.request) + \
                   '/gradebook'
        self.request.response.redirect(next_url)


class GradebookColumnPreferences(BrowserView):
    """A view for editing a teacher's gradebook column preferences."""

    def worksheets(self):
        results = []
        gradebook = proxy.removeSecurityProxy(self.context)
        for worksheet in gradebook.context.__parent__.values():
            if worksheet.deployed:
                continue
            results.append(worksheet)
        return results

    def addSummary(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheets = gradebook.context.__parent__

        overwrite = self.request.get('overwrite', '') == 'on'
        if overwrite:
            currentWorksheets = []
            for worksheet in worksheets.values():
                if worksheet.deployed:
                    continue
                if worksheet.title == SUMMARY_TITLE:
                    while len(worksheet.values()):
                        del worksheet[worksheet.values()[0].__name__]
                    summary = worksheet
                else:
                    currentWorksheets.append(worksheet)
            next = SUMMARY_TITLE
        else:
            next = self.nextSummaryTitle()
            currentWorksheets = self.worksheets()
            summary = Worksheet(next)
            chooser = INameChooser(worksheets)
            name = chooser.chooseName('', summary)
            worksheets[name] = summary

        for worksheet in currentWorksheets:
            if worksheet.title.startswith(SUMMARY_TITLE):
                continue
            activity = LinkedColumnActivity(worksheet.title, u'assignment',
                '', createSourceString(worksheet))
            chooser = INameChooser(summary)
            name = chooser.chooseName('', activity)
            summary[name] = activity

    def nextSummaryTitle(self):
        index = 1
        next = SUMMARY_TITLE
        while True:
            for worksheet in self.worksheets():
                if worksheet.title == next:
                    break
            else:
                break
            index += 1
            next = SUMMARY_TITLE + str(index)
        return next

    def summaryFound(self):
        return self.nextSummaryTitle() != SUMMARY_TITLE

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        factory = queryUtility(IVocabularyFactory,
                               'schooltool.requirement.discretescoresystems')
        vocab = factory(None)

        if 'UPDATE_SUBMIT' in self.request:
            columnPreferences = gradebook.getColumnPreferences(self.person)
            for key, name in getColumnKeys(gradebook):
                prefs = columnPreferences.setdefault(key, {})
                if 'hide_' + key in self.request:
                    prefs['hide'] = True
                else:
                    prefs['hide'] = False
                if 'label_' + key in self.request:
                    prefs['label'] = self.request['label_' + key]
                else:
                    prefs['label'] = ''
                if key == 'average':
                    token = self.request['scoresystem_' + key]
                    if token:
                        name = vocab.getTermByToken(token).value.__name__
                    else:
                        name = token
                    prefs['scoresystem'] = name
            prefs = columnPreferences.setdefault('due_date', {})
            if 'hide_due_date' in self.request:
                prefs['hide'] = True
            else:
                prefs['hide'] = False
            gradebook.setColumnPreferences(self.person, columnPreferences)

        if 'ADD_SUMMARY' in self.request:
            self.addSummary()

        if 'form-submitted' in self.request:
            self.request.response.redirect('index.html')

    @property
    def hide_due_date_value(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        columnPreferences = gradebook.getColumnPreferences(self.person)
        prefs = columnPreferences.get('due_date', {})
        return prefs.get('hide', False)

    @property
    def columns(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        results = []
        columnPreferences = gradebook.getColumnPreferences(self.person)
        for key, name in getColumnKeys(gradebook):
            prefs = columnPreferences.get(key, {})
            hide = prefs.get('hide', key in ['absences', 'tardies'])
            label = prefs.get('label', '')
            scoresystem = prefs.get('scoresystem', '')
            result = {
                'name': name,
                'hide_name': 'hide_' + key,
                'hide_value': hide,
                'label_name': 'label_' + key,
                'label_value': label,
                'has_scoresystem': key == 'average',
                'scoresystem_name': 'scoresystem_' + key,
                'scoresystem_value': scoresystem.encode('punycode'),
                }
            results.append(result)
        return results

    @property
    def scoresystems(self):
        factory = queryUtility(IVocabularyFactory,
                               'schooltool.requirement.discretescoresystems')
        vocab = factory(None)
        result = {
            'name': _('-- No score system --'),
            'value': '',
            }
        results = [result]
        for term in vocab:
            result = {
                'name': term.value.title,
                'value': term.token,
                }
            results.append(result)
        return results


class NoCurrentTerm(BrowserView):
    """A view for informing the user of the need to set up a schoolyear
       and at least one term."""

    def update(self):
        pass


class GradeStudent(z3cform.EditForm):
    """Edit form for a student's grades."""
    z3cform.extends(z3cform.EditForm)
    template = ViewPageTemplateFile('templates/grade_student.pt')

    def __init__(self, context, request):
        super(GradeStudent, self).__init__(context, request)
        if 'nexturl' in self.request:
            self.nexturl = self.request['nexturl']
        else:
            self.nexturl = self.gradebookURL()

    def update(self):
        self.person = IPerson(self.request.principal)
        for index, activity in enumerate(self.getFilteredActivities()):
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                continue
            elif interfaces.ILinkedActivity.providedBy(activity):
                continue
            if ICommentScoreSystem.providedBy(activity.scoresystem):
                field_cls = HtmlFragment
                title = activity.title
            else:
                field_cls = TextLine
                bestScore = activity.scoresystem.getBestScore()
                title = "%s (%s)" % (activity.title, bestScore)
            newSchemaFld = field_cls(
                title=title,
                description=activity.description,
                constraint=activity.scoresystem.fromUnicode,
                required=False)
            newSchemaFld.__name__ = str(activity.__name__)
            newSchemaFld.interface = interfaces.IStudentGradebookForm
            newFormFld = field.Field(newSchemaFld)
            self.fields += field.Fields(newFormFld)
        super(GradeStudent, self).update()

    @button.buttonAndHandler(_("Previous"))
    def handle_previous_action(self, action):
        if self.applyData():
            return
        prev, next = self.prevNextStudent()
        if prev is not None:
            url = '%s/%s' % (self.gradebookURL(),
                             urllib.quote(prev.username.encode('utf-8')))
            self.request.response.redirect(url)

    @button.buttonAndHandler(_("Next"))
    def handle_next_action(self, action):
        if self.applyData():
            return
        prev, next = self.prevNextStudent()
        if next is not None:
            url = '%s/%s' % (self.gradebookURL(),
                             urllib.quote(next.username.encode('utf-8')))
            self.request.response.redirect(url)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nexturl)

    def applyData(self):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return True
        changes = self.applyChanges(data)
        if changes:
            self.status = self.successMessage
        else:
            self.status = self.noChangesMessage
        return False

    def updateActions(self):
        super(GradeStudent, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['previous'].addClass('button-ok')
        self.actions['next'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

        prev, next = self.prevNextStudent()
        if prev is None:
            del self.actions['previous']
        if next is None:
            del self.actions['next']

    def applyChanges(self, data):
        super(GradeStudent, self).applyChanges(data)
        self.request.response.redirect(self.nexturl)

    def prevNextStudent(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        section = ISection(gradebook)
        student = self.context.student

        prev, next = None, None
        members = [member for name, member in
                   sorted([(m.last_name + m.first_name, m) for m in section.members])]
        if len(members) < 2:
            return prev, next
        for index, member in enumerate(members):
            if member == student:
                if index == 0:
                    next = members[1]
                elif index == len(members) - 1:
                    prev = members[-2]
                else:
                    prev = members[index - 1]
                    next = members[index + 1]
                break
        return prev, next

    def isFiltered(self, activity):
        flag, weeks = self.context.gradebook.getDueDateFilter(self.person)
        if not flag:
            return False
        today = queryUtility(IDateManager).today
        cutoff = today - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff

    def getFilteredActivities(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        return[activity for activity in gradebook.context.values()
               if not self.isFiltered(activity)]

    @property
    def label(self):
        return _(u'Enter grades for ${fullname}',
                 mapping={'fullname': self.context.student.title})

    def gradebookURL(self):
        return absoluteURL(self.context.gradebook, self.request)


class FlourishGradeStudent(GradeStudent, flourish.form.Form):
    """A flourish view for editing a teacher's gradebook column preferences."""

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Enter grade details below')

    @property
    def subtitle(self):
        return self.context.student.title

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishGradeStudent, self).handleApply.func(self, action)

    @button.buttonAndHandler(_("Previous"))
    def handle_previous_action(self, action):
        super(FlourishGradeStudent, self).handle_previous_action.func(self,
            action)

    @button.buttonAndHandler(_("Next"))
    def handle_next_action(self, action):
        super(FlourishGradeStudent, self).handle_next_action.func(self,
            action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        super(FlourishGradeStudent, self).handle_cancel_action.func(self,
            action)


class StudentGradebookView(object):
    """View a student gradebook."""

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)

        mapping = {
            'worksheet': gradebook.context.title,
            'student': '%s %s' % (self.context.student.first_name,
                                  self.context.student.last_name),
            'section': '%s - %s' % (", ".join([course.title
                                               for course in
                                               gradebook.section.courses]),
                                    gradebook.section.title),
            }
        self.title = _('$worksheet for $student in $section', mapping=mapping)

        self.blocks = []
        activities = [activity for activity in gradebook.context.values()
                      if not self.isFiltered(activity)]
        for activity in activities:
            score = gradebook.getScore(self.context.student, activity)
            if not score:
                value = ''
            else:
                value = score.value
            if ICommentScoreSystem.providedBy(activity.scoresystem):
                block = {
                    'comment': True,
                    'paragraphs': buildHTMLParagraphs(value),
                    }
            else:
                block = {
                    'comment': False,
                    'content': value,
                    }
            block['label'] = activity.title
            self.blocks.append(block)

    def isFiltered(self, activity):
        flag, weeks = self.context.gradebook.getDueDateFilter(self.person)
        if not flag:
            return False
        today = queryUtility(IDateManager).today
        cutoff = today - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff


class FlourishStudentGradebookView(flourish.page.Page):
    """A flourish view of the student gradebook."""

    @property
    def title(self):
        return self.context.student.title

    @property
    def subtitle(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        return _(u'${section} grades for ${worksheet}',
                 mapping={'section': ISection(gradebook).title,
                          'worksheet': gradebook.context.title})

    @property
    def blocks(self):
        blocks = []
        person = IPerson(self.request.principal, None)
        if person is None:
            return blocks
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        flag, weeks = gradebook.getDueDateFilter(person)
        today = queryUtility(IDateManager).today
        cutoff = today - datetime.timedelta(7 * int(weeks))
        for activity in gradebook.context.values():
            if flag and activity.due_date < cutoff:
                continue
            score = gradebook.getScore(self.context.student, activity)
            if not score:
                value = ''
            else:
                value = score.value
            if ICommentScoreSystem.providedBy(activity.scoresystem):
                block = {
                    'comment': True,
                    'paragraphs': buildHTMLParagraphs(value),
                    }
            else:
                block = {
                    'comment': False,
                    'content': value,
                    }
            block['label'] = activity.title
            blocks.append(block)
        return blocks


class GradebookCSVView(BrowserView):

    def __call__(self):
        csvfile = StringIO()
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        row = ['year', 'term', 'section', 'worksheet', 'activity', 'student',
               'grade']
        writer.writerow(row)
        syc = ISchoolYearContainer(self.context)
        for year in syc.values():
            for term in year.values():
                for section in ISectionContainer(term).values():
                    self.writeGradebookRows(writer, year, term, section)
        return csvfile.getvalue().decode('utf-8')

    def writeGradebookRows(self, writer, year, term, section):
        activities = interfaces.IActivities(section)
        for worksheet in activities.values():
            gb = interfaces.IGradebook(worksheet)
            for student in gb.students:
                for activity in gb.activities:
                    score = gb.getScore(student, activity)
                    if not score:
                        continue
                    value = unicode(score.value).replace('\n', '\\n')
                    value = value.replace('\r', '\\r')
                    row = [year.__name__, term.__name__, section.__name__,
                           worksheet.__name__, activity.__name__,
                           student.username, value]
                    row = [item.encode('utf-8') for item in row]
                    writer.writerow(row)


class SectionGradebookLinkViewlet(flourish.page.LinkViewlet):

    @Lazy
    def activities(self):
        return interfaces.IActivities(self.context)

    @Lazy
    def gradebook(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return None
        activities = self.activities
        if flourish.canEdit(activities):
            ensureAtLeastOneWorksheet(activities)
        if not len(activities):
            return None
        current_worksheet = activities.getCurrentWorksheet(person)
        return interfaces.IGradebook(current_worksheet)

    @property
    def url(self):
        if self.gradebook is None:
            return None
        return absoluteURL(self.gradebook, self.request)

    @property
    def enabled(self):
        if not super(SectionGradebookLinkViewlet, self).enabled:
            return False
        if self.gradebook is None:
            return None
        can_view = flourish.canView(self.gradebook)
        return can_view
