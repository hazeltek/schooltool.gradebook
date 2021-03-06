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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Gradebook Views
"""

__docformat__ = 'reStructuredText'

import pytz
from collections import OrderedDict
import datetime
from decimal import Decimal
from decimal import InvalidOperation
import urllib
from lxml import html

from zope.container.interfaces import INameChooser
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryUtility, getUtility
from zope.cachedescriptors.property import Lazy
from zope.html.field import HtmlFragment
from zope.interface import Interface
from zope.publisher.browser import BrowserView
from zope.schema import ValidationError, TextLine
from zope.schema.interfaces import IVocabularyFactory
from zope.security import proxy
from zope.security.interfaces import Unauthorized
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.viewlet import viewlet
from zope.i18n.interfaces.locales import ICollator
from zope.i18n import translate
from zope.authentication.interfaces import IUnauthenticatedPrincipal
from zope.component import queryMultiAdapter
from zope.location.location import LocationProxy

import zc.resourcelibrary
from zc.table.column import GetterColumn
from z3c.form import form as z3cform
from z3c.form import field, button

import schooltool.skin.flourish.page
import schooltool.skin.flourish.form
import schooltool.contact.contact
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.interfaces import IApplicationPreferences
from schooltool.app.interfaces import IRelationshipStateContainer
from schooltool.app.membership import Membership
from schooltool.app.states import ACTIVE
from schooltool.common.inlinept import InheritTemplate
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.contact.interfaces import IContact
from schooltool.course.interfaces import ISection
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.gradebook.activity import createSourceString, getSourceObj
from schooltool.gradebook.activity import Worksheet, LinkedColumnActivity
from schooltool.gradebook.gradebook import (getCurrentSectionTaught,
    setCurrentSectionTaught, getCurrentSectionAttended,
    setCurrentSectionAttended)
from schooltool.gradebook.gradebook import getCurrentEnrollmentMode
from schooltool.gradebook.gradebook import setCurrentEnrollmentMode
from schooltool.person.interfaces import IPerson
from schooltool.person.interfaces import IPersonFactory
from schooltool.requirement.scoresystem import UNSCORED, ScoreValidationError
from schooltool.requirement.interfaces import (ICommentScoreSystem,
    IValuesScoreSystem, IDiscreteValuesScoreSystem, IRangedValuesScoreSystem,
    IScoreSystemContainer, IEvaluations, IScore)
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.table.table import simple_form_key
from schooltool import table
from schooltool.term.interfaces import ITerm, IDateManager
from schooltool.report.report import ReportLinkViewlet
from schooltool.skin import flourish
from schooltool.skin.flourish.report import buildHTMLParagraphs

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
    if (scoresystem is None or
        not IDiscreteValuesScoreSystem.providedBy(scoresystem)):
        return '%.1f%%' % average
    for score in scoresystem.scores:
        if average >= score[3]:
            return score[0]


class GradebookStartup(object):
    """A view for entry into into the gradebook or mygrades views."""

    template = ViewPageTemplateFile('templates/gradebook_startup.pt')
    noSections = False
    teacher_gradebook_view_name = 'gradebook'
    student_gradebook_view_name = 'mygrades'

    def __call__(self):
        if IPerson(self.request.principal, None) is None:
            url = absoluteURL(ISchoolToolApplication(None), self.request)
            url = '%s/auth/@@login.html?nexturl=%s' % (url, self.request.URL)
            self.request.response.redirect(url)
            return ''
        return self.template()

    @Lazy
    def sectionsTaught(self):
        return list(IInstructor(self.person).sections())

    @Lazy
    def sectionsAttended(self):
        return list(ILearner(self.person).sections())

    def getFromYear(self, sections, active):
        in_active = filter(lambda x: ISchoolYear(x) is active, sections)
        if not in_active:
            return sections[0]
        current_term = getUtility(IDateManager).current_term
        in_current_term = filter(lambda x: ITerm(x) is current_term, in_active)
        if in_current_term:
            return in_current_term[0]
        return in_active[0]

    def update(self):
        schoolyears = ISchoolYearContainer(ISchoolToolApplication(None))
        active = schoolyears.getActiveSchoolYear()
        self.person = IPerson(self.request.principal)
        if not self.sectionsTaught and not self.sectionsAttended:
            self.noSections = True
        if self.sectionsTaught:
            section = getCurrentSectionTaught(self.person)
            if section is None or section.__parent__ is None:
                section = self.getFromYear(self.sectionsTaught, active)
            self.gradebookURL = '%s/%s' % (absoluteURL(section, self.request),
                                           self.teacher_gradebook_view_name)
            if not self.sectionsAttended:
                self.request.response.redirect(self.gradebookURL)
        if self.sectionsAttended:
            section = getCurrentSectionAttended(self.person)
            if section is None or section.__parent__ is None:
                section = self.getFromYear(self.sectionsAttended, active)
            self.mygradesURL = '%s/%s' % (absoluteURL(section, self.request),
                                          self.student_gradebook_view_name)
            if not self.sectionsTaught:
                self.request.response.redirect(self.mygradesURL)


class FlourishGradebookStartup(flourish.page.Page, GradebookStartup):

    content_template = ViewPageTemplateFile("templates/f_gradebook_startup.pt")

    def update(self):
        if IPerson(self.request.principal, None) is None:
            raise Unauthorized("user not logged in")
        GradebookStartup.update(self)


class GradebookStartupNavLink(flourish.page.LinkViewlet):

    startup_view_name = 'gradebook.html'

    @property
    def enabled(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return False

        sectionsTaught = list(IInstructor(person).sections())
        sectionsAttended = list(ILearner(person).sections())
        return sectionsTaught or sectionsAttended

    @property
    def url(self):
        person = IPerson(self.request.principal, None)
        if person is None:
            return ''
        app = ISchoolToolApplication(None)
        return '%s/%s' % (absoluteURL(app, self.request),
                          self.startup_view_name)


class SectionGradebookRedirectView(BrowserView):
    """A view for redirecting from a section to either the gradebook for its
       current worksheet or the final grades view for the section.
       In the case of final grades for the section, the query string,
       ?final=yes is used to isntruct this view to redirect to the final grades
       view instead of the gradebook"""

    teacher_worksheet_view_name = 'gradebook'
    student_worksheet_view_name = 'mygrades'

    def __call__(self):
        person = IPerson(self.request.principal)
        worksheets = interfaces.IActivities(self.context)
        ensureAtLeastOneWorksheet(worksheets)
        current_worksheet = worksheets.getCurrentWorksheet(person)
        url = absoluteURL(worksheets, self.request)
        if current_worksheet is not None:
            url = absoluteURL(current_worksheet, self.request)
            if person in self.context.members:
                url += '/%s' % self.student_worksheet_view_name
            else:
                url += '/%s' % self.teacher_worksheet_view_name
        self.request.response.redirect(url)
        return "Redirecting..."


class GradebookBase(BrowserView):

    teacher_gradebook_view_name = 'gradebook'
    student_gradebook_view_name = 'mygrades'

    changed = False

    @property
    def students(self):
        return self.context.students

    @property
    def all_hidden(self):
        activities = self.context.__parent__.__parent__
        return not activities.worksheets

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
                url += '/%s' % self.teacher_gradebook_view_name
            else:
                url += '/%s' % self.student_gradebook_view_name
            title = '%s - %s' % (", ".join([course.title
                                            for course in section.courses]),
                                 section.title)
            yield {'obj': section, 'url': url, 'title': title,
                   'form_id': self.getSectionId(section),
                   'selected': section == currentSection and 'selected' or None}

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
                    url += '/%s' % self.teacher_gradebook_view_name
                else:
                    url += '/%s' % self.student_gradebook_view_name
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
        if not gradebook.context.canAverage():
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


class JSONScoresBase(object):

    def getJSONScores(self, scoresystem):
        encoder = flourish.tal.JSONEncoder()
        result = []
        for label, abbr, value, percent in scoresystem.scores:
            title = label
            if abbr:
                title += ': %s' % abbr
            result.append({
                'label': title,
                'value': label,
            })
        json = encoder.encode(result)
        return json


class GradebookOverview(SectionFinder, JSONScoresBase):
    """Gradebook Overview/Table"""

    isTeacher = True
    needs_comments = False
    column_averages = None
    total_column_averages = None

    def getTodayState(self, student, section):
        relationships = Membership.bind(member=student).all().relationships
        for link_info in relationships:
            if link_info.target is section:
                today = link_info.state.today
                if today is not None:
                    meaning, code = today
                    state = self.app_states.states.get(code)
                    if state is not None:
                        return state.title
                else:
                    all = link_info.state.all()
                    if all:
                        date, meaning, code = all[0]
                        state = self.app_states.states.get(code)
                        if state is not None:
                            return '%s - %s' % (state.title, date)

    @Lazy
    def app_states(self):
        app = ISchoolToolApplication(None)
        return IRelationshipStateContainer(app)['section-membership']

    @property
    def students_info(self):
        result = []
        students = self.students
        section = proxy.removeSecurityProxy(self.context).section
        today = queryUtility(IDateManager).today
        active_students = students.on(today).any(ACTIVE)
        current_mode = getCurrentEnrollmentMode(self.person)
        if current_mode == 'gradebook-enrollment-mode-enrolled':
            students = active_students
        for student in students:
            css_class = ['popup_link']
            insecure_student = proxy.removeSecurityProxy(student)
            title = insecure_student.title
            if insecure_student not in active_students:
                css_class.append('inactive-student')
                state = self.getTodayState(insecure_student, section)
                if state is not None:
                    title = '%s (%s)' % (title, state)
            result.append({
                    'title': title,
                    'css_class': ' '.join(css_class),
                    'first_name': insecure_student.first_name,
                    'last_name': insecure_student.last_name,
                    'username': insecure_student.username,
                    'id': insecure_student.username,
                    'url': absoluteURL(insecure_student, self.request),
                    'gradeurl': '%s/%s' % (
                        absoluteURL(self.context, self.request),
                        insecure_student.username),
                    'object': insecure_student,
                    })
        return result

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()

    def doneURL(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        section = ISection(gradebook)
        return absoluteURL(section, self.request)

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        self.message = ''

        if 'CANCEL' in self.request:
            self.request.response.redirect(self.doneURL())
            return

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
                reverse = (sort_by not in ('student', 'first_name', 'last_name'))
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
                        self.context.removeEvaluation(student['object'], activity,
                                                      evaluator=evaluator)
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
        elif interfaces.IActivityWorksheet.providedBy(insecure_source):
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
            'cssClass': None,
            'scores': None,
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

        scores = None
        if scorable and \
           IDiscreteValuesScoreSystem.providedBy(insecure_activity.scoresystem):
            scores = self.getJSONScores(insecure_activity.scoresystem)

        if interfaces.ILinkedActivity.providedBy(insecure_activity):
            updateGrades = '%s/updateGrades.html' % (
                absoluteURL(insecure_activity, self.request))
        else:
            updateGrades = ''

        if ICommentScoreSystem.providedBy(insecure_activity.scoresystem):
            self.needs_comments = True
            zc.resourcelibrary.need("ckeditor")

        return {
            'linked_source': None,
            'scorable': scorable,
            'cssClass': scorable and 'scorable' or None,
            'scores': scores,
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
        for activity_info in self.filtered_activity_info:
            result = dict(activity_info)
            result.update({
                'canDelete': not self.deployed,
                'moveLeft': not self.deployed,
                'moveRight': not self.deployed,
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

        return value

    def getCommentShorthand(self, comment):
        result = ''
        inside_markup = False
        for char in comment:
            if inside_markup:
                if char == '>':
                    inside_markup = False
            else:
                if char == '<':
                    inside_markup = True
                else:
                    result += char
        return html.fromstring(result).text.lstrip()[:4]

    def table(self, worksheet=None):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        if worksheet is None:
            worksheet = gradebook.getCurrentWorksheet(self.person)

        section = ISection(worksheet, None)
        journal_data = interfaces.ISectionJournalData(section, None)
        rows = []
        for student_info in self.students_info:
            grades = []
            for activity_info in self.filtered_activity_info:
                activity = activity_info['object']
                is_comment = False
                hidden_value = ''
                value = self.getStudentActivityValue(student_info, activity)
                if ICommentScoreSystem.providedBy(activity.scoresystem):
                    is_comment = True
                    hidden_value = value
                    if value:
                        value = self.getCommentShorthand(value)
                source = activity_info['linked_source']
                if source is not None:
                    if value and interfaces.IActivityWorksheet.providedBy(source):
                        value = '%.1f' % value
                is_discrete = IDiscreteValuesScoreSystem.providedBy(
                    activity.scoresystem)
                grade = {
                    'activity': activity_info['hash'],
                    'editable': activity_info['scorable'],
                    'value': value,
                    'is_comment': is_comment,
                    'is_discrete': is_discrete,
                    'max': activity_info['max'],
                    'hidden_value': hidden_value,
                    }
                grades.append(grade)

            raw_total, raw_average = gradebook.getWorksheetTotalAverage(
                worksheet, student_info['object'])

            total = "%.1f" % raw_total

            if raw_average is UNSCORED:
                average = _('N/A')
            else:
                average = convertAverage(raw_average, self.average_scoresystem)

            absences = tardies = 0
            if (journal_data and not (self.absences_hide and self.tardies_hide)):
                # XXX: opt: perm checks may breed here
                meetings = journal_data.absentMeetings(student_info['object'])
                for meeting, score in meetings:
                    ss = score.scoreSystem
                    if ss.isExcused(score):
                        continue
                    elif ss.isAbsent(score):
                        absences += 1
                    elif ss.isTardy(score):
                        tardies += 1

            rows.append(
                {'student': student_info,
                 'grades': grades,
                 'absences': unicode(absences),
                 'tardies': unicode(tardies),
                 'total': total,
                 'average': average,
                 'raw_average': raw_average,
                 'raw_total': raw_total,
                 'raw_absences': absences,
                 'raw_tardies': tardies,
                })

        # Do the sorting
        key, reverse = self.sortKey
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        def generateStudentKey(row):
            return sorting_key(row['student']['object'])
        def generateKey(row):
            if key == 'student':
                return generateStudentKey(row)
            elif key == 'last_name':
                return (collator.key(row['student']['last_name']),
                        collator.key(row['student']['first_name']))
            elif key == 'first_name':
                return (collator.key(row['student']['first_name']),
                        collator.key(row['student']['last_name']))
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
                value = -9999999.9
                for grade in row['grades']:
                    if key == unicode(grade['activity']):
                        try:
                            value = float(grade['value'])
                        except:
                            pass
                        break
                return (value, generateStudentKey(row))
        result = sorted(rows, key=generateKey, reverse=reverse)
        self.column_averages = self.getColumnAverages(result)
        self.total_column_averages = self.getTotalColumnAverages(
            result, journal_data)
        return result

    def getColumnAverages(self, table):
        result = []
        columns = OrderedDict()
        for student_info in table:
            for i, grade in enumerate(student_info['grades']):
                if i not in columns:
                    columns[i] = {
                        'grades': [],
                        'is_comment': grade['is_comment'],
                        'is_discrete': grade['is_discrete'],
                        'max': grade['max'],
                    }
                columns[i]['grades'].append(grade['value'])
        for column in columns.values():
            average = ''
            if not column['is_comment'] and not column['is_discrete']:
                average_grades = []
                count = 0
                for grade in column['grades']:
                    # XXX: why decimals are str and not Decimal?
                    if grade != '':
                        try:
                            average_grades.append(Decimal(grade))
                            count += int(column['max'])
                        except (InvalidOperation,):
                            # ignore invalid grades
                            pass
                if count:
                    average = convertAverage(
                        (100 * sum(average_grades))/Decimal(count), None)
            result.append(average)
        return result

    def getTotalColumnAverages(self, table, journal_data):
        result = {}
        graded_student_count = 0
        absences = []
        tardies = []
        total = []
        average = []
        formatDecimal = lambda x: '%.1f' % x
        for student_info in table:
            absences.append(student_info['raw_absences'])
            tardies.append(student_info['raw_tardies'])
            student_average = student_info['raw_average']
            if student_average is not UNSCORED:
                graded_student_count += 1
                total.append(student_info['raw_total'])
                average.append(student_average)
        if journal_data is not None:
            row_count = len(table)
            if row_count:
                result['absences'] = formatDecimal(sum(absences) / row_count)
                result['tardies'] = formatDecimal(sum(tardies) / row_count)
        if graded_student_count:
            result['total'] = formatDecimal(
                sum(total) / graded_student_count)
            result['average'] = convertAverage(
                sum(average) / graded_student_count, self.average_scoresystem)
        return result

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

    @Lazy
    def deployed(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        return gradebook.context.deployed

    @property
    def show_absences_column(self):
        return self.journal_present and not self.absences_hide

    @property
    def show_tardies_column(self):
        return self.journal_present and not self.tardies_hide

    @property
    def show_total_column(self):
        return not self.deployed and not self.total_hide

    @property
    def show_average_column(self):
        return not self.deployed and not self.average_hide


class FlourishGradebookOverview(GradebookOverview,
                                flourish.page.WideContainerPage):
    """flourish Gradebook Overview/Table"""

    content_template = ViewPageTemplateFile(
        "templates/f_gradebook_overview.pt")

    labels_row_header = _('Activity')
    scores_row_header = _('Points')

    @property
    def readonly(self):
        return not flourish.canEdit(self.context)

    @property
    def page_class(self):
        if self.all_hidden:
            return 'page'
        else:
            return 'page grid'

    @property
    def title(self):
        if self.all_hidden:
            return _('No Visible Worksheets')
        else:
            return _('Enter Grades')

    @property
    def has_header(self):
        return self.all_hidden

    @property
    def journal_present(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        return interfaces.ISectionJournalData(section, None) is not None

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
            columnPreferences.setdefault('average', {})['scoresystem'] = name
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
            if term.value.hidden:
                continue
            results.append({
                'title': translate(term.value.title, context=self.request),
                'url': '?scoresystem=%s' % term.token,
                'current': term.value.__name__ == current,
                })
        return results

    def update(self):
        """Handle change of current year."""
        self.person = IPerson(self.request.principal)

        """Handle change of column preferences."""
        self.handlePreferencesChange()

        """Handle change of column order."""
        self.handleMoveActivity()

        """Handle removal of column."""
        self.handleDeleteActivity()

        """Everything else handled by old skin method."""
        GradebookOverview.update(self)

    def handleTermChange(self):
        return False

    def handleSectionChange(self):
        return False


class TeacherNavigationViewletBase(flourish.page.RefineLinksViewlet):

    @property
    def person(self):
        return IPerson(self.request.principal)

    @property
    def section(self):
        return proxy.removeSecurityProxy(self.context).section

    def render(self, *args, **kw):
        if self.person in self.section.instructors:
            return super(TeacherNavigationViewletBase,
                         self).render(*args, **kw)


class FlourishGradebookYearNavigation(TeacherNavigationViewletBase):
    """flourish Gradebook Overview year navigation viewlet."""


class FlourishGradebookYearNavigationViewlet(flourish.viewlet.Viewlet,
                                             GradebookOverview):
    template = InlineViewPageTemplate('''
    <select name="currentYear" class="navigator"
            tal:define="years view/getYears"
            tal:condition="years"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="year years"
              tal:attributes="value year/section_url;
                              selected year/selected"
              tal:content="year/title" />
    </select>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    @Lazy
    def user_sections(self):
        return self.getUserSections()

    def getYears(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentYear = ISchoolYear(ITerm(currentSection))
        years = []
        for section in self.user_sections:
            year = ISchoolYear(ITerm(section))
            if year not in years:
                years.append(year)
        return [{'title': year.title,
                 'section_url': self.getSectionURL(year),
                 'selected': year is currentYear and 'selected' or None}
                for year in sorted(years, key=lambda x:x.first)]

    def render(self, *args, **kw):
        return self.template(*args, **kw)

    def getSectionURL(self, year):
        result = None
        for section in self.user_sections:
            term = ITerm(section)
            if ISchoolYear(term).__name__ == year.__name__:
               result = section
               break
        url = absoluteURL(result, self.request)
        if self.isTeacher:
            url += '/%s' % self.teacher_gradebook_view_name
        else:
            url += '/%s' % self.student_gradebook_view_name
        return url


class FlourishGradebookTermNavigation(TeacherNavigationViewletBase):
    """flourish Gradebook Overview term navigation viewlet."""


class FlourishGradebookTermNavigationViewlet(flourish.viewlet.Viewlet,
                                             GradebookOverview):
    template = InlineViewPageTemplate('''
    <select name="currentTerm" class="navigator"
            tal:define="terms view/getTerms"
            tal:condition="terms"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="term terms"
              tal:attributes="value term/section_url;
                              selected term/selected"
              tal:content="term/title" />
    </select>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    @Lazy
    def user_sections(self):
        return self.getUserSections()

    def getTerms(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        currentYear = ISchoolYear(currentTerm)
        terms = []
        for section in self.user_sections:
            term = ITerm(section)
            if ISchoolYear(term) == currentYear and term not in terms:
                terms.append(term)
        return [{'title': term.title,
                 'section_url': self.getSectionURL(term),
                 'selected': term is currentTerm and 'selected' or None}
                for term in sorted(terms, key=lambda x:x.first)]

    def render(self, *args, **kw):
        return self.template(*args, **kw)

    def getCourse(self, section):
        try:
            return list(section.courses)[0]
        except (IndexError,):
            return None

    def getSectionURL(self, term):
        result = None
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentCourse = self.getCourse(currentSection)
        for section in self.user_sections:
            if term == ITerm(section):
                if currentCourse == self.getCourse(section):
                    result = section
                    break
                elif result is None:
                    result = section
        url = absoluteURL(result, self.request)
        if self.isTeacher:
            url += '/%s' % self.teacher_gradebook_view_name
        else:
            url += '/%s' % self.student_gradebook_view_name
        return url


class FlourishGradebookSectionNavigation(TeacherNavigationViewletBase):
    """flourish Gradebook Overview section navigation viewlet."""


class FlourishGradebookSectionNavigationViewlet(flourish.viewlet.Viewlet,
                                                GradebookOverview):
    template = InlineViewPageTemplate('''
    <select name="currentSection" class="navigator"
            tal:define="sections view/getSections"
            tal:condition="sections"
            onchange="ST.redirect($(this).context.value)">
      <option tal:repeat="section sections"
            tal:attributes="value section/url;
                            selected section/selected;"
            tal:content="section/title" />
    </select>
    ''')

    @property
    def person(self):
        return IPerson(self.request.principal)

    @Lazy
    def user_sections(self):
        return self.getUserSections()

    def getSections(self):
        result = []
        collator = ICollator(self.request.locale)
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        for section in self.user_sections:
            term = ITerm(section)
            if term != currentTerm:
                continue
            url = absoluteURL(section, self.request)
            if self.isTeacher:
                url += '/%s' % self.teacher_gradebook_view_name
            else:
                url += '/%s' % self.student_gradebook_view_name
            result.append({
                'url': url,
                'title': section.title,
                'selected': section==currentSection and 'selected' or None,
                })
        return sorted(result, key=lambda x:collator.key(x['title']))

    def render(self, *args, **kw):
        return self.template(*args, **kw)


class FlourishGradebookOverviewLinks(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Overview add links viewlet."""


class ActivityAddLink(flourish.page.LinkViewlet):

    @property
    def title(self):
        worksheet = proxy.removeSecurityProxy(self.context).context
        if worksheet.deployed or worksheet.hidden:
            return ''
        return _("Activity")


class CategoryWeightsLink(flourish.page.LinkViewlet):

    @property
    def enabled(self):
        worksheet = proxy.removeSecurityProxy(self.context).context
        return not worksheet.deployed and not worksheet.hidden


class FlourishGradebookSettingsLinks(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Settings links viewlet."""


class FlourishGradebookActionsLinks(flourish.page.RefineLinksViewlet):
    """flourish Gradebook Actions links viewlet."""


class GradebookTertiaryNavigationManager(flourish.page.TertiaryNavigationManager):

    template = ViewPageTemplateFile('templates/f_gradebook_tertiary_nav.pt')

    @property
    def items(self):
        result = []
        gradebook = proxy.removeSecurityProxy(self.context)
        current = gradebook.context.__name__
        for worksheet in gradebook.worksheets:
            url = '%s/gradebook' % absoluteURL(worksheet, self.request)
            classes = worksheet.__name__ == current and ['active'] or []
            if worksheet.deployed:
                classes.append('deployed')
            result.append({
                'class': classes and ' '.join(classes) or None,
                'viewlet': u'<a title="%s" href="%s">%s</a>' % (worksheet.title, url, worksheet.title[:15]),
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
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        for student in sorted(self.context.students, key=sorting_key):
            reqValue = self.request.get(student.username)
            score = gradebook.getScore(student, self.activity['obj'])
            if not score:
                value = reqValue or ''
            else:
                value = reqValue or score.value

            yield {'student': {'title': student.title,
                               'first_name': student.first_name,
                               'last_name': student.last_name,
                               'id': student.username},
                   'value': value}

    def doneURL(self):
        return absoluteURL(self.context, self.request)

    def update(self):
        self.messages = []

        if 'CANCEL' in self.request:
            self.request.response.redirect(self.doneURL())

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
                        self.context.removeEvaluation(student, activity,
                                                      evaluator=evaluator)
                    # Do nothing
                    elif not score and request_score_value is UNSCORED:
                        continue
                    # Replace the score or add new one
                    elif not score or request_score_value != score.value:
                        self.context.evaluate(
                            student, activity, request_score_value, evaluator)

            if not len(self.messages):
                self.request.response.redirect(self.doneURL())


class FlourishGradeActivity(GradeActivity, flourish.page.Page):
    """flourish Grading a single activity"""

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()


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
        for activity in gradebook.getCurrentActivities(self.person):
            activity = proxy.removeSecurityProxy(activity)
            score = gradebook.getScore(self.person, activity)

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
                    if int(value) != value:
                        value = '%.1f' % value
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
                'object': activity,
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
    page_class = 'page grid'

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
                    url += '/%s' % self.teacher_gradebook_view_name
                else:
                    url += '/%s' % self.student_gradebook_view_name
                self.request.response.redirect(url)
                return True
        return False

    def update(self):
        """Handle change of year."""
        if IUnauthenticatedPrincipal.providedBy(self.request.principal):
            raise Unauthorized("user not logged in")
        self.person = IPerson(self.request.principal)
        if self.handleYearChange():
            return

        """Everything else handled by old skin method."""
        MyGradesView.update(self)


def mygrades_score_formatter(grade, item, formatter):
    if grade['comment']:
        paragraphs = ['<p>%s</p>' % p for p in grade['paragraphs']]
        return ''.join(paragraphs)
    else:
        return grade['value']


class MyGradesTable(table.ajax.Table):

    batch_size = 0

    def items(self):
        return self.view.table

    def columns(self):
        activity = GetterColumn(
            name='title',
            title=_('Activity'),
            getter=lambda i, f: i['activity'])
        score = GetterColumn(
            name='score',
            title=_('Score'),
            getter=lambda i, f: i['grade'],
            cell_formatter=mygrades_score_formatter)
        return [activity, score]

    def sortOn(self):
        return None

    def updateFormatter(self):
        if self._table_formatter is None:
            self.setUp(table_formatter=self.table_formatter,
                       batch_size=self.batch_size,
                       prefix=self.__name__,
                       css_classes={'table': 'data'})


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

    # XXX: almost the same as GradebookTertiaryNavigationManager
    #      merge

    template = ViewPageTemplateFile('templates/f_gradebook_tertiary_nav.pt')

    @property
    def items(self):
        result = []
        gradebook = proxy.removeSecurityProxy(self.context)
        current = gradebook.context.__name__
        for worksheet in gradebook.worksheets:
            url = '%s/mygrades' % absoluteURL(worksheet, self.request)
            classes = worksheet.__name__ == current and ['active'] or []
            if worksheet.deployed:
                classes.append('deployed')
            result.append({
                'class': classes and ' '.join(classes) or None,
                'viewlet': u'<a title="%s" href="%s">%s</a>' % (worksheet.title, url, worksheet.title[:15]),
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
                score = external_grade * linked_activity.points
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
        # XXX: hack to pass the evaluator to the form adapter
        gradebook = proxy.removeSecurityProxy(self.context)
        gradebook.evaluator = getName(self.person)
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
        self.actions['previous'].addClass('button-neutral')
        self.actions['next'].addClass('button-neutral')
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

        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        members = sorted(section.members, key=sorting_key)
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


class FlourishStudentGradeHistory(flourish.page.Page):

    @property
    def title(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        return ISection(gradebook).title

    @property
    def subtitle(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        return _(u'${worksheet} grade history for ${student}',
                 mapping={'worksheet': gradebook.context.title,
                          'student': self.context.student.title})

    @property
    def timezone(self):
        app = ISchoolToolApplication(None)
        prefs = IApplicationPreferences(app)
        timezone_name = prefs.timezone
        return pytz.timezone(timezone_name)

    @property
    def timeformat(self):
        app = ISchoolToolApplication(None)
        prefs = IApplicationPreferences(app)
        return prefs.timeformat

    def buildHistoryTable(self):
        persons = ISchoolToolApplication(None)['persons']
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        worksheet = proxy.removeSecurityProxy(gradebook.context)
        student = self.context.student
        timezone = self.timezone
        timeformat = self.timeformat

        # XXX: this is nearly a copy of MyGradesView.update
        self.table = []
        count = 0
        for activity in gradebook.getWorksheetActivities(worksheet):
            evaluations = IEvaluations(student)
            evaluations = proxy.removeSecurityProxy(evaluations)
            current = evaluations.get(activity, None)
            history = evaluations.getHistory(activity)
            if (current is None and
                not history):
                continue

            grade_records = []
            for evaluation in [current] + list(reversed(history)):
                if evaluation is None:
                    record = {
                        'comment': True,
                        'paragraphs': buildHTMLParagraphs(_('Removed score')),
                        }
                    continue
                score = IScore(evaluation, None)
                if score:
                    ss = score.scoreSystem
                    if ICommentScoreSystem.providedBy(ss):
                        record = {
                            'comment': True,
                            'paragraphs': buildHTMLParagraphs(score.value),
                            }
                    elif IValuesScoreSystem.providedBy(ss):
                        s_min, s_max = getScoreSystemDiscreteValues(ss)
                        value = score.value
                        if IDiscreteValuesScoreSystem.providedBy(ss):
                            value = score.scoreSystem.getNumericalValue(score.value)
                            if value is None:
                                value = 0
                        if int(value) != value:
                            value = '%.1f' % value
                        count += s_max - s_min
                        record = {
                            'comment': False,
                            'value': '%s / %s' % (value, ss.getBestScore()),
                            }
                    else:
                        record = {
                            'comment': False,
                            'value': score.value,
                            }
                else:
                    record = {
                        'comment': True,
                        'paragraphs': buildHTMLParagraphs(_('Removed score')),
                        }

                if (evaluation is not None and evaluation.evaluator):
                    record['evaluator'] = persons.get(evaluation.evaluator, None)
                else:
                    record['evaluator'] = None
                if (evaluation is not None and evaluation.evaluator):
                    record['evaluator'] = persons.get(evaluation.evaluator, None)
                else:
                    record['evaluator'] = None

                if (evaluation is not None and
                    getattr(evaluation, 'time', None) is not None):
                    time_utc = pytz.utc.localize(evaluation.time)
                    time = time_utc.astimezone(timezone)
                    record['date'] = time.date()
                    record['time'] = time.strftime(timeformat)
                else:
                    record['date'] = None
                    record['time'] = None

                grade_records.append(record)

            row = {
                'activity': activity.title,
                'grades': grade_records,
                }

            self.table.append(row)


    def update(self):
        super(FlourishStudentGradeHistory, self).update()
        self.buildHistoryTable()


class StudentGradebookView(object):
    """View a student gradebook."""

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)

        mapping = {
            'worksheet': gradebook.context.title,
            'student': self.context.student.title,
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

    def update(self):
        gradebook = proxy.removeSecurityProxy(self.context.gradebook)
        worksheet = proxy.removeSecurityProxy(gradebook.context)
        student = self.context.student
        column_keys_dict = dict(getColumnKeys(gradebook))

        person = IPerson(self.request.principal, None)
        if person is None:
            columnPreferences = {}
        else:
            columnPreferences = gradebook.getColumnPreferences(person)

        prefs = columnPreferences.get('average', {})
        self.average_hide = prefs.get('hide', False)
        self.average_label = prefs.get('label', '')
        if len(self.average_label) == 0:
            self.average_label = column_keys_dict['average']
        scoresystems = IScoreSystemContainer(ISchoolToolApplication(None))
        self.average_scoresystem = scoresystems.get(
            prefs.get('scoresystem', ''))

        # XXX: the rest is a copy of MyGradesView.update
        self.table = []
        count = 0
        for activity in gradebook.getWorksheetActivities(worksheet):
            activity = proxy.removeSecurityProxy(activity)
            score = gradebook.getScore(student, activity)

            if score:
                ss = score.scoreSystem
                if ICommentScoreSystem.providedBy(ss):
                    grade = {
                        'comment': True,
                        'paragraphs': buildHTMLParagraphs(score.value),
                        }
                elif IValuesScoreSystem.providedBy(ss):
                    s_min, s_max = getScoreSystemDiscreteValues(ss)
                    value = score.value
                    if IDiscreteValuesScoreSystem.providedBy(ss):
                        value = score.scoreSystem.getNumericalValue(score.value)
                        if value is None:
                            value = 0
                    if int(value) != value:
                        value = '%.1f' % value
                    count += s_max - s_min
                    grade = {
                        'comment': False,
                        'value': '%s / %s' % (value, ss.getBestScore()),
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
                student)
            self.average = convertAverage(average, self.average_scoresystem)
        else:
            self.average = None


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
        if not flourish.canView(activities):
            return None
        if not len(activities):
            return None
        current_worksheet = activities.getCurrentWorksheet(person)
        return interfaces.IGradebook(current_worksheet, None)

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


class JSONViewBase(flourish.page.Page):

    def result(self):
        raise NotImplementedError('subclasses must provide result()')

    def translate(self, message):
        return translate(message, context=self.request)

    def __call__(self):
        response = self.request.response
        response.setHeader('Content-Type', 'application/json')
        encoder = flourish.tal.JSONEncoder()
        json = encoder.encode(self.result())
        return json


class FlourishGradebookValidateScoreView(JSONViewBase):

    def result(self):
        result = {'is_valid': True, 'is_extracredit': False}
        activity_id = self.request.get('activity_id')
        score = self.request.get('score')
        if score and activity_id:
            person = IPerson(self.request.principal)
            worksheet = self.context.getCurrentWorksheet(person)
            activity = worksheet.get(activity_id)
            if activity is not None:
                scoresystem = activity.scoresystem
                score = self.request.get('score')
                try:
                    score = scoresystem.fromUnicode(score)
                except (ScoreValidationError,):
                    result['is_valid'] = False
                else:
                    if IDiscreteValuesScoreSystem.providedBy(scoresystem):
                        result['score'] = score
                    if (IRangedValuesScoreSystem.providedBy(scoresystem) and
                        score > scoresystem.getBestScore()):
                        result['is_extracredit'] = True
        return result


class FlourishActivityPopupMenuView(JSONViewBase, JSONScoresBase):

    @property
    def readonly(self):
        return not flourish.canEdit(self.context)

    def options(self, info, worksheet):
        options = []
        url = '%s/gradebook' % absoluteURL(worksheet, self.request)
        if info['canDelete']:
            options.append({
                    'label': self.translate(_('Edit')),
                    'url': absoluteURL(info['object'], self.request),
                    })
        if info['scorable']:
            options.append({
                    'label': self.translate(_('Score this')),
                    'url': '%s/gradeActivity.html?activity=%s' % (
                        url, info['hash'])
                    })
            options.append({
                    'label': self.translate(_('Fill down')),
                    'url': '#',
                    'css_class': 'filldown',
                    })
        options.append({
                'label': self.translate(_('Sort by')),
                'url': '%s?sort_by=%s' % (url, info['hash']),
                })
        if info['canDelete']:
            options.append({
                    'label': self.translate(_('Delete')),
                    'url': '%s?delete=%s' % (url, info['hash']),
                    })
        if info['moveLeft']:
            options.append({
                    'label': self.translate(_('Move left')),
                    'url': '%s?move_left=%s' % (url, info['hash']),
                    })
        if info['moveRight']:
            options.append({
                    'label': self.translate(_('Move right')),
                    'url': '%s?move_right=%s' % (url, info['hash']),
                    })
        if info['updateGrades']:
            options.append({
                    'label': self.translate(_('Update grades')),
                    'url': info['updateGrades'],
                    })
        return options

    def result(self):
        result = {}
        activity_id = self.request.get('activity_id')
        worksheet = proxy.removeSecurityProxy(self.context).context
        if activity_id is not None and activity_id in worksheet:
            activity = worksheet[activity_id]
            info = self.getActivityInfo(activity)
            can_modify = not self.readonly and not worksheet.deployed
            info.update({
                    'canDelete': can_modify,
                    'moveLeft': can_modify,
                    'moveRight': can_modify,
                    })
            keys = worksheet.keys()
            if keys[0] == activity.__name__:
                info['moveLeft'] = False
            if keys[-1] == activity.__name__:
                info['moveRight'] = False
            result['header'] = info['longTitle']
            result['options'] = self.options(info, worksheet)
        return result

    # XXX: All of this has been copied from the gradebook view
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
            'cssClass': None,
            'scores': None,
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
            self.readonly or
            ICommentScoreSystem.providedBy(insecure_activity.scoresystem) or
            interfaces.ILinkedActivity.providedBy(insecure_activity))
        scores = None
        if scorable and \
           IDiscreteValuesScoreSystem.providedBy(insecure_activity.scoresystem):
            scores = self.getJSONScores(insecure_activity.scoresystem)
        if (interfaces.ILinkedActivity.providedBy(insecure_activity) and
            not self.readonly):
            updateGrades = '%s/updateGrades.html' % (
                absoluteURL(insecure_activity, self.request))
        else:
            updateGrades = ''
        return {
            'linked_source': None,
            'scorable': scorable,
            'cssClass': scorable and 'scorable' or None,
            'scores': scores,
            'shortTitle': short,
            'longTitle': long,
            'max': best_score,
            'hash': insecure_activity.__name__,
            'object': activity,
            'updateGrades': updateGrades,
            }

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


class FlourishStudentPopupMenuView(JSONViewBase):

    @property
    def readonly(self):
        return not flourish.canEdit(self.context)

    def options(self, student):
        url = absoluteURL(student, self.request)
        readonly = self.readonly
        gradeurl = '%s/%s' % (
            absoluteURL(self.context, self.request),
            student.username)
        options = []
        options.append({
            'label': self.translate(_('Student')),
            'url': url,
            })
        if not readonly:
            options.append({
                'label': self.translate(_('Score')),
                'url': gradeurl,
                })
        options.append({
            'label': self.translate(_('Score History')),
            'url': '%s/history.html' % gradeurl,
            })
        options.append({
            'label': self.translate(_('Report')),
            'url': '%s/view.html' % gradeurl,
            })
        return options

    def result(self):
        student_id = self.request.get('student_id')
        result = {}
        if student_id is not None:
            app = ISchoolToolApplication(None)
            student = app['persons'].get(student_id)
            if student is not None and student in self.context.students:
                result['header'] = student.title
                result['options'] = self.options(student)
        return result


class FlourishNamePopupMenuView(JSONViewBase):

    def options(self, worksheet, column_id='student'):
        options = [
            {
                'label': self.translate(_('Sort by')),
                'url': '?sort_by=%s' % column_id,
                },
            ]
        return options

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()

    def result(self):
        column_id = self.request.get('column_id')
        for column in self.name_sorting_columns:
            if column.name == column_id:
                break
        worksheet = proxy.removeSecurityProxy(self.context).context
        self.deployed = worksheet.deployed
        self.processColumnPreferences()
        result = {
            'header': self.translate(column.title),
            'options': self.options(worksheet, column_id),
            }
        return result

    # XXX: Copied (and modified) from the gradebook view
    def processColumnPreferences(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        person = IPerson(self.request.principal)
        columnPreferences = gradebook.getColumnPreferences(person)
        journal_data = interfaces.ISectionJournalData(ISection(gradebook), None)
        self.journal_present = journal_data is not None
        prefs = columnPreferences.get('absences', {})
        if journal_data is None:
            self.absences_hide = True
        else:
            self.absences_hide = prefs.get('hide', True)
        prefs = columnPreferences.get('tardies', {})
        if journal_data is None:
            self.tardies_hide = True
        else:
            self.tardies_hide = prefs.get('hide', True)
        prefs = columnPreferences.get('total', {})
        self.total_hide = prefs.get('hide', False)
        prefs = columnPreferences.get('average', {})
        self.average_hide = prefs.get('hide', False)


class FlourishTotalPopupMenuView(JSONViewBase):

    titles = {
        'total': _('Total'),
        'average': _('Ave.'),
        'tardies': _('Trd.'),
        'absences': _('Abs.'),
        }

    def options(self, column_id):
        options = [
            {
                'label': self.translate(_('Hide')),
                'url': '?hide=%s' % column_id,
                },
            {
                'label': self.translate(_('Sort by')),
                'url': '?sort_by=%s' % column_id,
                },
            ]
        if column_id in ('average',):
            scoresystem_options = []
            for scoresystem in self._scoresystems:
                scoresystem_options.append({
                        'label': scoresystem['title'],
                        'url': scoresystem['url'],
                        'current': scoresystem['current'],
                        })
            options.append({
                    'header': self.translate(_('Score System')),
                    'options': scoresystem_options,
                    })
        return options

    def result(self):
        result = {}
        column_id = self.request.get('column_id')
        if column_id in self.titles:
            result['header'] = self.translate(self.titles[column_id])
            result['options'] = self.options(column_id)
        return result

    # XXX: Copied (and modified) from the gradebook view
    @property
    def _scoresystems(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        person = IPerson(self.request.principal)
        columnPreferences = gradebook.getColumnPreferences(person)
        vocab = queryUtility(
            IVocabularyFactory,
            'schooltool.requirement.discretescoresystems')(None)
        current = columnPreferences.get('average', {}).get('scoresystem', '')
        results = [{
            'title': _('No score system'),
            'url': '?scoresystem',
            'current': not current,
            }]
        for term in vocab:
            if term.value.hidden:
                continue
            results.append({
                'title': translate(term.value.title, context=self.request),
                'url': '?scoresystem=%s' % term.token,
                'current': term.value.__name__ == current,
                })
        return results


class PrintableWorksheetViewlet(ReportLinkViewlet):

    def render(self, *args, **kw):
        worksheet = proxy.removeSecurityProxy(self.context).context
        if worksheet.hidden:
            return ''
        return super(PrintableWorksheetViewlet, self).render(*args, **kw)


class GradebookExportViewlet(ReportLinkViewlet):

    def render(self, *args, **kw):
        worksheet = proxy.removeSecurityProxy(self.context).context
        if worksheet.hidden:
            return ''
        return super(GradebookExportViewlet, self).render(*args, **kw)


class ICommentCellForm(Interface):
    '''An interface used to build the comment cell modal'''

    value = HtmlFragment(
        title=_("Value"),
        required=False)


class CommentCellFormAdapter(object):

    def __init__(self, context):
        pass

    def __getattr__(self, name):
        return ''


class FlourishGradebookCommentCell(flourish.form.Form):

    fields = field.Fields(ICommentCellForm)


class TermReportLinkViewlet(ReportLinkViewlet):
    pass


class ChildrenGradebookOverview(flourish.viewlet.Viewlet):

    @property
    def person(self):
        return IPerson(self.context, None)

    def gradebooks(self):
        contact = IContact(self.person)
        relationships = schooltool.contact.contact.ContactRelationship.bind(
            contact=contact)
        children = list(relationships.any(
                schooltool.contact.contact.ACTIVE+
                schooltool.contact.contact.PARENT))

        gradebooks = []
        for child in children:
            relationships = Membership.bind(member=child)
            for section in relationships:
                try:
                    activities = interfaces.IActivities(section)
                except:
                    continue
                for worksheet in activities.values():
                    gb = interfaces.IGradebook(worksheet)
                    stud_gb = queryMultiAdapter(
                        (child, gb), interfaces.IStudentGradebook)
                    if stud_gb is None:
                        continue
                    gradebooks.append(LocationProxy(stud_gb, gb, child.__name__))
        return gradebooks


class EnrollmentModes(flourish.page.RefineLinksViewlet):

    pass


class EnrollmentModeContent(flourish.content.ContentProvider):

    enrollment_mode_name = 'gradebook-enrollment-mode'
    enrolled_mode = 'gradebook-enrollment-mode-enrolled'
    all_mode = 'gradebook-enrollment-mode-all'

    @Lazy
    def default_mode(self):
        return self.enrolled_mode

    @Lazy
    def enrollment_modes(self):
        return (self.enrolled_mode, self.all_mode)

    @Lazy
    def modes(self):
        person = self.person
        if person is None:
            return []
        gradebook_url = absoluteURL(self.context, self.request)
        result = []
        result.append({
                'id': self.enrolled_mode,
                'label': _('Active'),
                'url': '%s?%s' % (
                    gradebook_url,
                    urllib.urlencode({
                            self.enrollment_mode_name: self.enrolled_mode,
                            }))
                })
        result.append({
                'id': self.all_mode,
                'label': _('All'),
                'url': '%s?%s' % (
                    gradebook_url,
                    urllib.urlencode({
                            self.enrollment_mode_name: self.all_mode,
                            }))
                })
        return result

    @Lazy
    def person(self):
        person = IPerson(self.request.principal, None)
        return person

    def render(self):
        return ''


class EnrollmentModesSelector(flourish.viewlet.Viewlet):

    list_class = 'filter'

    template = InlineViewPageTemplate('''
        <ul tal:attributes="class view/list_class"
            tal:condition="view/items">
          <li tal:repeat="item view/items">
            <input type="radio"
                   onclick="ST.redirect($(this).context.value)"
                   tal:attributes="value item/url;
                                   id item/id;
                                   checked item/selected;" />
            <label tal:content="item/label"
                   tal:attributes="for item/id" />
          </li>
        </ul>
    ''')

    @Lazy
    def content(self):
        return self.manager.view.providers.get('gradebook-enrollment-modes')

    @Lazy
    def items(self):
        if not self.content:
            return []
        result = list(self.content.modes)
        for mode in result:
            mode['selected'] = bool(mode['id'] == self.current_mode)
        return result

    @Lazy
    def person(self):
        person = IPerson(self.request.principal, None)
        return person

    @property
    def current_mode(self):
        mode = getCurrentEnrollmentMode(self.person)
        if mode is None:
            mode = self.content.default_mode
            setCurrentEnrollmentMode(self.person, mode)
        return mode

    def update(self):
        if self.content:
            name = self.content.enrollment_mode_name
            requested_mode = self.request.get(name)
            if (requested_mode in self.content.enrollment_modes and
                requested_mode != self.current_mode):
                setCurrentEnrollmentMode(self.person, requested_mode)

    def render(self, *args, **kw):
        if len(self.items) < 2:
            return ''
        return self.template(*args, **kw)


class ColumnPreferencesMenu(flourish.page.RefineLinksViewlet):

    pass


class ColumnPreferencesMenuOptions(flourish.viewlet.Viewlet):

    prefix = '__GRADEBOOK-COLUMN-PREFERENCES__'
    list_class = 'filter'
    template = InlineViewPageTemplate('''
        <ul tal:attributes="class view/list_class"
            tal:condition="view/items">
          <li tal:repeat="item view/items">
            <input type="checkbox"
                   onclick="ST.redirect($(this).context.value)"
                   tal:attributes="value item/url;
                                   id item/id;
                                   checked item/checked;" />
            <label tal:content="item/label"
                   tal:attributes="for item/id" />
          </li>
        </ul>
    ''')

    @property
    def columns(self):
        result = []
        if not self.view.deployed:
            result.append(('total', _('Total')))
            result.append(('average' , _('Average')))
        if self.view.journal_present:
            result.insert(0, ('tardies' , _('Tardies')))
            result.insert(0, ('absences', _('Absences')))
        return result

    @property
    def items(self):
        result = []
        for name, label in self.columns:
            hide_column = getattr(self.view, '%s_hide' % name)
            result.append({
                'url': '%s?%s=%s' % (
                    absoluteURL(self.context, self.request),
                    ['hide', 'show'][hide_column],
                    name),
                'id': '%s%s' % (self.prefix, name),
                'checked': None if hide_column else 'checked',
                'label': label,
                })
        return result
