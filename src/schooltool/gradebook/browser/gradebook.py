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

from schooltool.course.interfaces import ILearner
from schooltool.course.interfaces import IInstructor
__docformat__ = 'reStructuredText'
import zope.schema
from zope.security import proxy
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.app.keyreference.interfaces import IKeyReference
from zope.viewlet import viewlet
from zope.traversing.api import getName
from zope.publisher.browser import BrowserView

from schooltool.app import app
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISection
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.person.interfaces import IPerson
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.common import SchoolToolMessage as _
from schooltool.requirement.interfaces import IValuesScoreSystem
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.term.interfaces import ITerm

import datetime
import decimal

GradebookCSSViewlet = viewlet.CSSViewlet("gradebook.css")

DISCRETE_SCORE_SYSTEM = 'd'
RANGED_SCORE_SYSTEM = 'r'


class GradebookStartup(object):
    """A view for entry into into the gradebook or mygrades views."""

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
            ss = activity.scoresystem
            if IDiscreteValuesScoreSystem.providedBy(ss):
                result = [DISCRETE_SCORE_SYSTEM] + [score[0] 
                    for score in ss.scores]
            else:
                result = [RANGED_SCORE_SYSTEM, ss.min, ss.max]
            resultStr = ', '.join(["'%s'" % str(value) 
                for value in result])
            results[hash(IKeyReference(activity))] = resultStr
        return results

    def breakJSString(self, origstr):
        newstr = str(origstr)
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

    def getTerms(self):
        currentSection = ISection(proxy.removeSecurityProxy(self.context))
        currentTerm = ITerm(currentSection)
        terms = []
        for section in self.getUserSections():
            term = ITerm(section)
            if term not in terms:
                terms.append(term)
        return [{'title': term.title} for term in terms]

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
                'title': worksheet.title[:10],
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
        return term.title

    def handleTermChange(self):
        if 'currentTerm' in self.request:
            currentSection = ISection(proxy.removeSecurityProxy(self.context))
            currentCourse = list(currentSection.courses)[0]
            currentTerm = ITerm(currentSection)
            requestTitle = self.request['currentTerm']
            if requestTitle != currentTerm.title:
                newSection = None
                for section in self.getUserSections():
                    term = ITerm(section)
                    if term.title == requestTitle:
                        if currentCourse == list(section.courses)[0]:
                            newSection = section
                            break
                        if newSection is None:
                            newSection = section
                url = absoluteURL(newSection, self.request) + '/gradebook'
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
                act_hash = str(hash(IKeyReference(activity)))
                cell_name = '%s_%s' % (act_hash, student.username)
                if cell_name in self.request:
                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        score = activity.scoresystem.fromUnicode(
                            self.request[cell_name])
                    except (zope.schema.ValidationError, ValueError):
                        self.message = _(
                            'The grade $value for activity $name is not valid.',
                            mapping={'value': self.request[cell_name],
                                     'name': activity.title})
                        return
                    ev = gradebook.getEvaluation(student, activity)
                    # Delete the score
                    if ev is not None and score is UNSCORED:
                        self.context.removeEvaluation(student, activity)
                        self.changed = True
                    # Do nothing
                    elif ev is None and score is UNSCORED:
                        continue
                    # Replace the score or add new one/
                    elif ev is None or score != ev.value:
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

    def activities(self):
        """Get  a list of all activities."""
        self.person = IPerson(self.request.principal)
        result = []
        for activity in self.getFilteredActivities():
            shortTitle = activity.label
            if shortTitle is None or len(shortTitle) == 0:
                shortTitle = activity.title
            shortTitle = shortTitle.replace(' ', '')
            if len(shortTitle) > 5:
                shortTitle = shortTitle[:5].strip()

            result.append({'shortTitle': shortTitle,
                           'longTitle': activity.title,
                           'max': activity.scoresystem.getBestScore(),
                           'hash': hash(IKeyReference(activity))})
            
        return result

    def isFiltered(self, activity):
        flag, weeks = self.context.getDueDateFilter(self.person)
        if not flag:
            return False
        cutoff = datetime.date.today() - datetime.timedelta(7 * int(weeks))
        return activity.due_date < cutoff

    def getFilteredActivities(self):
        activities = self.context.getCurrentActivities(self.person)
        return[activity for activity in activities
               if not self.isFiltered(activity)]

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
                ev = gradebook.getEvaluation(student, activity)
                if ev is not None and ev.value is not UNSCORED:
                    value = ev.value
                else:
                    value = ''

                cell_name = '%s_%s' % (act_hash, student.username)
                if cell_name in self.request:
                    value = self.request[cell_name]

                grades.append({'activity': act_hash, 'value': value})

            total, average = gradebook.getWorksheetTotalAverage(worksheet,
                student)

            rows.append(
                {'student': {'title': student.title, 
                             'id': student.username,
                             'url': absoluteURL(student, self.request),
                            },
                 'grades': grades, 'total': str(total),
                 'average': str(average)
                })

        # Do the sorting
        key, reverse = self.sortKey
        def generateKey(row):
            if key != 'student':
                grades = dict([(str(grade['activity']), grade['value'])
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


class SummaryView(SectionFinder):
    """Final Grades Table for all students in the section"""

    isTeacher = True

    def table(self):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        rows = []
        students = sorted(self.context.students, key=lambda x: x.title)
        for student in students:
            grades = []
            for worksheet in self.worksheets:
                total, average = gradebook.getWorksheetTotalAverage(worksheet,
                    student)
                grades.append({'value': str(average)})
            calculated = gradebook.getFinalGrade(student)

            row = {
                'student': student,
                'grades': grades,
                'calculated': calculated,
                }
            rows.append(row)

        return rows

    @property
    def worksheets(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        return [worksheet
                for worksheet in gradebook.worksheets
                if not worksheet.deployed]


class GradeActivity(object):
    """Grading a single activity"""

    message = ''

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
            ev = gradebook.getEvaluation(student, self.activity['obj'])
            value = self.request.get(student.username)
            if ev is not None and ev.value is not UNSCORED:
                value = value or ev.value
            else:
                value = value or ''

            yield {'student': {'title': student.title, 'id': student.username},
                   'value': value}

    def update(self):
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
                    except (zope.schema.ValidationError, ValueError):
                        self.message = _(
                            'The grade $value for $name is not valid.',
                            mapping={'value': self.request[id],
                                     'name': student.title})
                        return
                    ev = gradebook.getEvaluation(student, activity)
                    # Delete the score
                    if ev is not None and score is UNSCORED:
                        self.context.removeEvaluation(student, activity)
                    # Do nothing
                    elif ev is None and score is UNSCORED:
                        continue
                    # Replace the score or add new one/
                    elif ev is None or score != ev.value:
                        self.context.evaluate(
                            student, activity, score, evaluator)

            self.request.response.redirect('index.html')


def getScoreSystemDiscreteValues(ss):
    if IDiscreteValuesScoreSystem.providedBy(ss):
        return (ss.scores[-1][1], ss.scores[0][1])
    elif IRangedValuesScoreSystem.providedBy(ss):
        return (ss.min, ss.max)
    return (0, 0)


def getEvaluationDiscreteValue(ev):
    ss = ev.requirement.scoresystem
    if IDiscreteValuesScoreSystem.providedBy(ss):
        val = ss.getNumericalValue(ev.value)
        if val is not None:
            return val
    elif IRangedValuesScoreSystem.providedBy(ss):
        return ev.value
    return 0


class MyGradesView(SectionFinder):
    """Student view of own grades."""

    isTeacher = False

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)

        """Make sure the current worksheet matches the current url"""
        worksheet = gradebook.context
        gradebook.setCurrentWorksheet(self.person, worksheet)

        """Handle change of current term."""
        if self.handleTermChange():
            return

        """Handle change of current section."""
        if self.handleSectionChange():
            return

        self.table = []
        total = 0
        count = 0
        for activity in self.context.getCurrentActivities(self.person):
            activity = proxy.removeSecurityProxy(activity)
            ev = proxy.removeSecurityProxy(
                self.context.getEvaluation(self.person, activity))

            if ev is not None and ev.value is not UNSCORED:
                ss = ev.requirement.scoresystem
                if IValuesScoreSystem.providedBy(ss):
                    grade = '%s / %s' % (ev.value, ss.getBestScore())
                    s_min, s_max = getScoreSystemDiscreteValues(ss)
                    value = getEvaluationDiscreteValue(ev)
                    total += value - s_min
                    count += s_max - s_min
                else:
                    grade = ev.value
            else:
                grade = None

            self.table.append({'activity': activity.title,
                               'grade': grade})
        if count:
            self.average = int((float(100 * total) / float(count)) + 0.5)
        else:
            self.average = None

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
