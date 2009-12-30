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

import datetime
import decimal

from zope.app.container.interfaces import INameChooser
from zope.app.keyreference.interfaces import IKeyReference
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import queryUtility
from zope.html.field import HtmlFragment
from zope.publisher.browser import BrowserView
from zope.schema import ValidationError, Text, TextLine
from zope.schema.interfaces import IVocabularyFactory
from zope.security import proxy
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.viewlet import viewlet

from z3c.form import form as z3cform
from z3c.form import field, button

from schooltool.app import app
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISection
from schooltool.course.interfaces import ILearner, IInstructor
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.gradebook.activity import createSourceString, getSourceObj
from schooltool.gradebook.activity import Worksheet, LinkedColumnActivity
from schooltool.gradebook.browser.report_utils import buildHTMLParagraphs
from schooltool.person.interfaces import IPerson
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.requirement.interfaces import ICommentScoreSystem
from schooltool.requirement.interfaces import IValuesScoreSystem
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.table.table import simple_form_key
from schooltool.term.interfaces import ITerm

from schooltool.gradebook import GradebookMessage as _


GradebookCSSViewlet = viewlet.CSSViewlet("gradebook.css")

DISCRETE_SCORE_SYSTEM = 'd'
RANGED_SCORE_SYSTEM = 'r'
COMMENT_SCORE_SYSTEM = 'c'
SUMMARY_TITLE = _('Summary')

column_keys = [('total', _("Total")), ('average', _("Ave."))]


def escName(name):
    """converts title-based scoresystem name to querystring format"""
    chars = [c for c in name.lower() if c.isalnum() or c == ' ']
    return u''.join(chars).replace(' ', '-')


def getScoreSystemFromEscName(name):
    """converts escaped scoresystem title to scoresystem"""
    factory = queryUtility(IVocabularyFactory,
                           'schooltool.requirement.discretescoresystems')
    vocab = factory(None)
    for term in vocab:
        if name == escName(term.token):
            return term.value
    return None


def convertAverage(average, scoresystem):
    """converts average to display value of the given scoresystem"""
    if scoresystem is None:
        return '%s%%' % average
    for score in scoresystem.scores:
        if average >= score[2]:
            return score[0]


class GradebookStartup(object):
    """A view for entry into into the gradebook or mygrades views."""

    def __call__(self):
        if IPerson(self.request.principal, None) is None:
            url = absoluteURL(ISchoolToolApplication(None), self.request)
            url = '%s/auth/@@login.html?nexturl=%s' % (url, self.request.URL)
            self.request.response.redirect(url)
            return ''
        template = ViewPageTemplateFile('gradebook_startup.pt')
        return template(self)

    def update(self):
        self.person = IPerson(self.request.principal)
        self.sectionsTaught = list(IInstructor(self.person).sections())
        self.sectionsAttended = list(ILearner(self.person).sections())

        if self.sectionsTaught:
            section = self.sectionsTaught[0]
            self.gradebookURL = absoluteURL(section, self.request)+ '/gradebook'
            if not self.sectionsAttended:
                self.request.response.redirect(self.gradebookURL)
        if self.sectionsAttended:
            section = self.sectionsAttended[0]
            self.mygradesURL = absoluteURL(section, self.request) + '/mygrades'
            if not self.sectionsTaught:
                self.request.response.redirect(self.mygradesURL)


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
            if 'mygrades' in self.request['PATH_INFO']:
                url += '/mygrades'
            else:
                url += '/gradebook'
            if 'final' in self.request:
                url += '/final.html'
        self.request.response.redirect(url)
        return "Redirecting..."


class GradebookBase(BrowserView):

    def __init__(self, context, request):
        super(GradebookBase, self).__init__(context, request)
        self.changed = False

    @property
    def time(self):
        t = datetime.datetime.now()
        return "%s-%s-%s %s:%s:%s" % (t.year, t.month, t.day,
                                      t.hour, t.minute, t.second)

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
            results[hash(IKeyReference(activity))] = resultStr
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

    def getSections(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        gradebook = proxy.removeSecurityProxy(self.context)
        for section in self.getUserSections():
            term = ITerm(section)
            if term != currentTerm:
                continue
            url = absoluteURL(section, self.request)
            if self.isTeacher:
                url += '/gradebook'
            else:
                url += '/mygrades'
            title = '%s - %s' % (list(section.courses)[0].title, section.title)
            css = 'inactive-menu-item'
            if section == currentSection:
                css = 'active-menu-item'
            yield {'obj': section, 'url': url, 'title': title, 'css': css}

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
        return '%s - %s' % (list(section.courses)[0].title, section.title)

    def getCurrentTerm(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        term = ITerm(section)
        return '%s / %s' % (ISchoolYear(term).title, term.title)

    def handleTermChange(self):
        if 'currentTerm' in self.request:
            currentSection = ISection(proxy.removeSecurityProxy(self.context))
            currentCourse = list(currentSection.courses)[0]
            currentTerm = ITerm(currentSection)
            requestTermId = self.request['currentTerm']
            if requestTermId != self.getTermId(currentTerm):
                newSection = None
                for section in self.getUserSections():
                    term = ITerm(section)
                    if self.getTermId(term) == requestTermId:
                        if currentCourse == list(section.courses)[0]:
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
                if section['title'] == self.request['currentSection']:
                    if section['obj'] == ISection(gradebook):
                        break
                    self.request.response.redirect(section['url'])
                    return True
        return False

    def processColumnPreferences(self):
        gradebook = proxy.removeSecurityProxy(self.context)
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
        column_keys_dict = dict(column_keys)
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
        self.average_scoresystem = getScoreSystemFromEscName(
            prefs.get('scoresystem', ''))
        self.apply_all_colspan = 1
        if gradebook.context.deployed:
            self.total_hide = True
            self.average_hide = True
        if not self.total_hide:
            self.apply_all_colspan += 1
        if not self.average_hide:
            self.apply_all_colspan += 1


class GradebookOverview(SectionFinder):
    """Gradebook Overview/Table"""

    isTeacher = True

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        self.message = ''

        """Make sure the current worksheet matches the current url"""
        worksheet = gradebook.context
        gradebook.setCurrentWorksheet(self.person, worksheet)

        """Retrieve column preferences."""
        self.processColumnPreferences()

        """Retrieve sorting information and store changes of it."""
        if 'sort_by' in self.request:
            sort_by = self.request['sort_by']
            key, reverse = gradebook.getSortKey(self.person)
            if sort_by == key:
                reverse = not reverse
            else:
                reverse=False
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
        for student in self.context.students:
            for activity in gradebook.activities:
                # Create a hash and see whether it is in the request
                act_hash = unicode(hash(IKeyReference(activity)))
                cell_name = '%s_%s' % (act_hash, student.username)
                if cell_name in self.request:
                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        score = activity.scoresystem.fromUnicode(
                            self.request[cell_name])
                    except (ValidationError, ValueError):
                        self.message = _(
                            'Invalid scores (highlighted in red) were not saved.')
                        continue
                    value, ss = gradebook.getEvaluation(student, activity)
                    # Delete the score
                    if value is not None and score is UNSCORED:
                        self.context.removeEvaluation(student, activity)
                        self.changed = True
                    # Do nothing
                    elif value is None and score is UNSCORED:
                        continue
                    # Replace the score or add new one/
                    elif value is None or score != value:
                        self.changed = True
                        self.context.evaluate(
                            student, activity, score, evaluator)

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

    def getActivityAttrs(self, activity):
        shortTitle = activity.label
        if shortTitle is None or len(shortTitle) == 0:
            shortTitle = activity.title
        shortTitle = shortTitle.replace(' ', '')
        if len(shortTitle) > 5:
            shortTitle = shortTitle[:5].strip()
        longTitle = activity.title
        if ICommentScoreSystem.providedBy(activity.scoresystem):
            bestScore = ''
        else:
            bestScore = activity.scoresystem.getBestScore()
        return shortTitle, longTitle, bestScore

    def activities(self):
        """Get  a list of all activities."""
        self.person = IPerson(self.request.principal)
        results = []
        for activity in self.getFilteredActivities():
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                scorable = False
                source = getSourceObj(activity.source)
                if interfaces.IActivity.providedBy(source):
                    shortTitle, longTitle, bestScore = \
                        self.getActivityAttrs(source)
                    if source.label is not None and len(source.label):
                        shortTitle = source.label
                    if source.title is not None and len(source.title):
                        longTitle = source.title
                elif interfaces.IWorksheet.providedBy(source):
                    shortTitle = source.title
                    if len(shortTitle) > 5:
                        shortTitle = shortTitle[:5].strip()
                    longTitle = source.title
                    bestScore = '100'
                else:
                    shortTitle = longTitle = bestScore = ''
            else:
                scorable = not ICommentScoreSystem.providedBy(
                    activity.scoresystem)
                shortTitle, longTitle, bestScore = \
                    self.getActivityAttrs(activity)
            result = {
                'scorable': scorable,
                'shortTitle': shortTitle,
                'longTitle': longTitle,
                'max': bestScore,
                'hash': hash(IKeyReference(activity)),
                }
            results.append(result)
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
        cutoff = datetime.date.today() - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff

    def getFilteredActivities(self):
        activities = self.context.getCurrentActivities(self.person)
        return[activity for activity in activities
               if not self.isFiltered(activity)]

    def getStudentActivityValue(self, student, activity):
        gradebook = proxy.removeSecurityProxy(self.context)
        value, ss = gradebook.getEvaluation(student, activity)
        if value is None or value is UNSCORED:
            value = ''

        act_hash = hash(IKeyReference(activity))
        cell_name = '%s_%s' % (act_hash, student.username)
        if cell_name in self.request:
            value = self.request[cell_name]

        if value and ICommentScoreSystem.providedBy(activity.scoresystem):
            value = '...'

        return value

    def table(self):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheet = gradebook.getCurrentWorksheet(self.person)
        activities = [(hash(IKeyReference(activity)), activity)
            for activity in self.getFilteredActivities()]
        rows = []
        for student in self.context.students:
            grades = []
            for act_hash, activity in activities:
                value = self.getStudentActivityValue(student, activity)
                if interfaces.ILinkedColumnActivity.providedBy(activity):
                    editable = False
                else:
                    editable = not ICommentScoreSystem.providedBy(
                        activity.scoresystem)

                grade = {
                    'activity': act_hash,
                    'editable': editable,
                    'value': value
                    }
                grades.append(grade)

            total, average = gradebook.getWorksheetTotalAverage(worksheet,
                student)

            if average is UNSCORED:
                average = _('N/A')
            else:
                average = convertAverage(average, self.average_scoresystem)

            rows.append(
                {'student': {'title': student.title,
                             'id': student.username,
                             'url': absoluteURL(student, self.request),
                             'gradeurl': absoluteURL(self.context, self.request) +
                                    ('/%s' % student.username),
                            },
                 'grades': grades, 'total': unicode(total),
                 'average': unicode(average)
                })

        # Do the sorting
        key, reverse = self.sortKey
        def generateKey(row):
            if key != 'student':
                grades = dict([(unicode(grade['activity']), grade['value'])
                               for grade in row['grades']])
                if not grades.get(key, ''):
                    return (1, row['student']['title'])
                else:
                    return (0, grades.get(key))
            return row['student']['title']

        return sorted(rows, key=generateKey, reverse=reverse)

    @property
    def firstCellId(self):
        self.person = IPerson(self.request.principal)
        activities = self.getFilteredActivities()
        students = self.context.students
        if len(activities) and len(students):
            act_hash = hash(IKeyReference(activities[0]))
            student_id = students[0].username
            return '%s_%s' % (act_hash, student_id)
        else:
            return ''

    @property
    def descriptions(self):
        self.person = IPerson(self.request.principal)
        results = []
        for activity in self.getFilteredActivities():
            description = activity.title
            result = {
                'act_hash': hash(IKeyReference(activity)),
                'description': self.breakJSString(description),
                }
            results.append(result)
        return results


class GradeActivity(object):
    """Grading a single activity"""

    @property
    def activity(self):
        act_hash = int(self.request['activity'])
        for activity in self.context.activities:
            if hash(IKeyReference(activity)) == act_hash:
                return {'title': activity.title,
                        'max': activity.scoresystem.getBestScore(),
                        'hash': hash(IKeyReference(activity)),
                         'obj': activity}

    @property
    def grades(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        for student in self.context.students:
            reqValue = self.request.get(student.username)
            value, ss = gradebook.getEvaluation(student, self.activity['obj'])
            if value is None or value is UNSCORED:
                value = reqValue or ''
            else:
                value = reqValue or value

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

                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        score = activity.scoresystem.fromUnicode(
                            self.request[id])
                    except (ValidationError, ValueError):
                        message = _(
                            'The grade $value for $name is not valid.',
                            mapping={'value': self.request[id],
                                     'name': student.title})
                        self.messages.append(message)
                        continue
                    value, ss = gradebook.getEvaluation(student, activity)
                    # Delete the score
                    if value is not None and score is UNSCORED:
                        self.context.removeEvaluation(student, activity)
                    # Do nothing
                    elif value is None and score is UNSCORED:
                        continue
                    # Replace the score or add new one/
                    elif value is None or score != value:
                        self.context.evaluate(
                            student, activity, score, evaluator)

            if not len(self.messages):
                self.request.response.redirect('index.html')


def getScoreSystemDiscreteValues(ss):
    if IDiscreteValuesScoreSystem.providedBy(ss):
        return (ss.scores[-1][1], ss.scores[0][1])
    elif IRangedValuesScoreSystem.providedBy(ss):
        return (ss.min, ss.max)
    return (0, 0)


class MyGradesView(SectionFinder):
    """Student view of own grades."""

    isTeacher = False

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)

        """Make sure the current worksheet matches the current url"""
        worksheet = gradebook.context
        gradebook.setCurrentWorksheet(self.person, worksheet)

        """Retrieve column preferences."""
        self.processColumnPreferences()

        self.table = []
        total = 0
        count = 0
        for activity in self.context.getCurrentActivities(self.person):
            activity = proxy.removeSecurityProxy(activity)
            value, ss = self.context.getEvaluation(self.person, activity)

            if value is not None and value is not UNSCORED:
                if IValuesScoreSystem.providedBy(ss):
                    grade = '%s / %s' % (value, ss.getBestScore())
                    s_min, s_max = getScoreSystemDiscreteValues(ss)
                    if IDiscreteValuesScoreSystem.providedBy(ss):
                        value = ss.getNumericalValue(value)
                        if value is None:
                            value = 0
                    total += value - s_min
                    count += s_max - s_min
                else:
                    grade = value
            else:
                grade = None

            self.table.append({'activity': activity.title,
                               'grade': grade})

        if count:
            average = int((float(100 * total) / float(count)) + 0.5)
            self.average = convertAverage(average, self.average_scoresystem)
            if self.average is UNSCORED:
                self.average = None
        else:
            self.average = None

        """Handle change of current term."""
        if self.handleTermChange():
            return

        """Handle change of current section."""
        self.handleSectionChange()

    def getCurrentWorksheet(self):
        return self.context.getCurrentWorksheet(self.person)


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
                score = decimal.Decimal("%.2f" % external_grade) * \
                        decimal.Decimal(linked_activity.points)
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

        if 'UPDATE_SUBMIT' in self.request:
            columnPreferences = gradebook.getColumnPreferences(self.person)
            for key, name in column_keys:
                prefs = columnPreferences.setdefault(key, {})
                if 'hide_' + key in self.request:
                    prefs['hide'] = True
                else:
                    prefs['hide'] = False
                if 'label_' + key in self.request:
                    prefs['label'] = self.request['label_' + key]
                else:
                    prefs['label'] = ''
                if key != 'total':
                    prefs['scoresystem'] = self.request['scoresystem_' + key]
            gradebook.setColumnPreferences(self.person, columnPreferences)

        if 'ADD_SUMMARY' in self.request:
            self.addSummary()

        if 'form-submitted' in self.request:
            self.request.response.redirect('index.html')

    @property
    def columns(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        results = []
        columnPreferences = gradebook.getColumnPreferences(self.person)
        for key, name in column_keys:
            prefs = columnPreferences.get(key, {})
            hide = prefs.get('hide', False)
            label = prefs.get('label', '')
            scoresystem = prefs.get('scoresystem', '')
            result = {
                'name': name,
                'hide_name': 'hide_' + key,
                'hide_value': hide,
                'label_name': 'label_' + key,
                'label_value': label,
                'scoresystem_name': 'scoresystem_' + key,
                'scoresystem_value': scoresystem,
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
                'name': term.token,
                'value': escName(term.token),
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
    template = ViewPageTemplateFile('grade_student.pt')

    def __init__(self, context, request):
        super(GradeStudent, self).__init__(context, request)
        if 'nexturl' in self.request:
            self.nexturl = self.request['nexturl']
        else:
            self.nexturl = self.gradebookURL()

    def update(self):
        self.person = IPerson(self.request.principal)
        for index, activity in enumerate(self.getFilteredActivities()):
            if ICommentScoreSystem.providedBy(activity.scoresystem):
                field_cls = HtmlFragment
            else:
                field_cls = TextLine
            newSchemaFld = field_cls(
                title=activity.title,
                description=activity.description,
                constraint=activity.scoresystem.fromUnicode,
                required=False)
            newSchemaFld.__name__ = str(hash(IKeyReference(activity)))
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
            url = '%s/%s' % (self.gradebookURL(), prev.username)
            self.request.response.redirect(url)

    @button.buttonAndHandler(_("Next"))
    def handle_next_action(self, action):
        if self.applyData():
            return
        prev, next = self.prevNextStudent()
        if next is not None:
            url = '%s/%s' % (self.gradebookURL(), next.username)
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
        cutoff = datetime.date.today() - datetime.timedelta(7 * int(weeks))
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
            'section': '%s - %s' % (list(gradebook.section.courses)[0].title,
                                    gradebook.section.title),
            }
        self.title = _('$worksheet for $student in $section', mapping=mapping)

        self.blocks = []
        activities = [activity for activity in gradebook.context.values()
                      if not self.isFiltered(activity)]
        for activity in activities:
            value, ss = gradebook.getEvaluation(self.context.student, activity)
            if value is None or value is UNSCORED:
                value = ''
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
        cutoff = datetime.date.today() - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff

