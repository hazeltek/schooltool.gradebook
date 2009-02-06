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
"""Gradebook Views

$Id$
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
from schooltool.person.interfaces import IPerson
from schooltool.requirement.scoresystem import UNSCORED
from schooltool.common import SchoolToolMessage as _
from schooltool.requirement.interfaces import IValuesScoreSystem
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem

from datetime import datetime

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
        t = datetime.now()
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

    def breakJSString(self,origstr):
        newstr = str(origstr)
        newstr = "\\'".join(newstr.split("'"))
        newstr = '\\"'.join(newstr.split('"'))
        return newstr


class SectionFinder(GradebookBase):
    """Base class for GradebookOverview and MyGradesView"""

    def getSections(self, isTeacher):
        gradebook = proxy.removeSecurityProxy(self.context)

        sectionsTaught = list(IInstructor(self.person).sections())
        sectionsAttended = list(ILearner(self.person).sections())
        for section in sectionsTaught:
            url = absoluteURL(section, self.request)
            url += '/gradebook'
            title = '%s - %s' % (list(section.courses)[0].title, section.title)
            css = 'inactive-menu-item'
            if section == gradebook.context:
                css = 'active-menu-item'
            yield {'obj': section, 'url': url, 'title': title, 'css': css}
        for section in sectionsAttended:
            url = absoluteURL(section, self.request)
            url += '/mygrades'
            title = '%s - %s' % (list(section.courses)[0].title, section.title)
            css = 'inactive-menu-item'
            if section == gradebook.context:
                css = 'active-menu-item'
            yield {'obj': section, 'url': url, 'title': title, 'css': css}

    def getCurrentSection(self):
        section = ISection(proxy.removeSecurityProxy(self.context))
        return '%s - %s' % (list(section.courses)[0].title, section.title)


class GradebookOverview(SectionFinder):
    """Gradebook Overview/Table"""

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

        """Handle change of current section."""
        if 'currentSection' in self.request:
            for section in self.getSections(True):
                if section['title'] == self.request['currentSection']:
                    if section['obj'] == ISection(gradebook):
                        break
                    self.request.response.redirect(section['url'])
                    return

        """Handle change of current worksheet."""
        if 'currentWorksheet' in self.request:
            for worksheet in gradebook.worksheets:
                if worksheet.title == self.request['currentWorksheet']:
                    if worksheet == gradebook.getCurrentWorksheet(self.person):
                        break
                    gradebook.setCurrentWorksheet(self.person, worksheet)
                    url = absoluteURL(worksheet, self.request)
                    self.request.response.redirect(url)
                    return

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

    def activities(self):
        """Get  a list of all activities."""
        result = []
        for activity in self.context.getCurrentActivities(self.person):
            shortTitle = activity.title
            if len(activity.title) > 14:
                shortTitle = activity.title[0:11] + '...'
                
            result.append({'shortTitle': shortTitle,
                           'longTitle': activity.title,
                           'max': activity.scoresystem.getBestScore(),
                           'hash': hash(IKeyReference(activity))})
            
        return result

    def table(self):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        worksheet = gradebook.getCurrentWorksheet(self.person)
        activities = [(hash(IKeyReference(activity)), activity)
            for activity in gradebook.getWorksheetActivities(worksheet)]
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
                {'student': {'title': student.title, 'id': student.username},
                 'grades': grades, 'total': str(total),
                 'average': str(average)})

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


class FinalGradesView(SectionFinder):
    """Final Grades Table for all students in the section"""

    def table(self):
        """Generate the table of grades."""
        gradebook = proxy.removeSecurityProxy(self.context)
        rows = []
        students = sorted(self.context.students, key=lambda x: x.title)
        for student in students:
            grades = []
            for worksheet in gradebook.worksheets:
                total, average = gradebook.getWorksheetTotalAverage(worksheet,
                    student)
                grades.append({'value': str(average)})
            calculated = gradebook.getFinalGrade(student)
            final = gradebook.getAdjustedFinalGrade(self.person, student)
            adj_dict = gradebook.getFinalGradeAdjustment(self.person, student)
            adj_id = 'adj_' + student.username
            adj_value = adj_dict['adjustment']
            reason_id = 'reason_' + student.username
            reason_value = adj_dict['reason']

            rows.append(
                {'student': student,
                 'grades': grades,
                 'calculated': calculated,
                 'final': final,
                 'adjustment': {'id': adj_id, 'value': adj_value},
                 'reason': {'id': reason_id, 'value': reason_value}})

        return rows

    def update(self):
        self.person = IPerson(self.request.principal)
        gradebook = proxy.removeSecurityProxy(self.context)
        students = sorted(self.context.students, key=lambda x: x.title)

        """Handle change of current section."""
        if 'currentSection' in self.request:
            for section in self.getSections(True):
                if section['title'] == self.request['currentSection']:
                    if section['obj'] != ISection(gradebook):
                        self.request.response.redirect(section['url'] + \
                            '?final=yes')
                    break

        """Retrieve final grade adjustments and store changes to them."""
        self.error_message = ''
        for student in students:
            adj_id = 'adj_' + student.username
            if adj_id in self.request:
                adj_value = self.request[adj_id]
                reason_value = self.request['reason_' + student.username]
                try:
                    gradebook.setFinalGradeAdjustment(self.person, student,
                        adj_value, reason_value)
                except ValueError, e:
                    if not self.error_message:
                        self.error_message = str(e)


class GradeStudent(object):
    """Grading a single student."""

    message = ''

    @property
    def student(self):
        id = self.request['student']
        school = app.getSchoolToolApplication()
        return school['persons'][id]

    @property
    def activities(self):
        return [
            {'title': activity.title,
             'max': activity.scoresystem.getBestScore(),
             'hash': hash(IKeyReference(activity))}
            for activity in self.context.getCurrentActivities(self.person)]

    def grades(self):
        activities = [(hash(IKeyReference(activity)), activity)
            for activity in self.context.getCurrentActivities(self.person)]
        student = self.student
        gradebook = proxy.removeSecurityProxy(self.context)
        for act_hash, activity in activities:
            ev = gradebook.getEvaluation(student, activity)
            value = self.request.get(str(act_hash))
            if ev is not None and ev.value is not UNSCORED:
                yield {'activity': act_hash, 'value': value or ev.value}
            else:
                yield {'activity': act_hash, 'value': value or ''}

    def update(self):
        self.person = IPerson(self.request.principal)

        if 'CANCEL' in self.request:
            self.request.response.redirect('index.html')

        elif 'UPDATE_SUBMIT' in self.request:
            student = self.student
            evaluator = getName(IPerson(self.request.principal))
            gradebook = proxy.removeSecurityProxy(self.context)
            # Iterate through all activities
            for activity in self.context.activities:
                # Create a hash and see whether it is in the request
                act_hash = str(hash(IKeyReference(activity)))
                if act_hash in self.request:

                    # If a value is present, create an evaluation, if the
                    # score is different
                    try:
                        score = activity.scoresystem.fromUnicode(
                            self.request[act_hash])
                    except (zope.schema.ValidationError, ValueError):
                        self.message = _(
                            'The grade $value for activity $name is not valid.',
                            mapping={'value': self.request[act_hash],
                                     'name': activity.title})
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


class GradeActivity(object):
    """Grading a single activity"""

    message = ''

    @property
    def activity(self):
        if hasattr(self, '_activity'):
            return self._activity
        act_hash = int(self.request['activity'])
        for activity in self.context.activities:
            if hash(IKeyReference(activity)) == act_hash:
                self._activity = activity
                return activity

    @property
    def grades(self):
        gradebook = proxy.removeSecurityProxy(self.context)
        for student in self.context.students:
            ev = gradebook.getEvaluation(student, self.activity)
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
            activity = self.activity
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


class Grade(object):
    """Grading a specific activity for a student."""

    @property
    def student(self):
        id = self.request['student']
        school = app.getSchoolToolApplication()
        return school['persons'][id]

    @property
    def activity(self):
        if hasattr(self, '_activity'):
            return self._activity
        act_hash = int(self.request['activity'])
        for activity in self.context.activities:
            if hash(IKeyReference(activity)) == act_hash:
                self._activity = activity
                return activity

    @property
    def activityInfo(self):
        formatter = self.request.locale.dates.getFormatter('date', 'short')
        return {'title': self.activity.title,
                'date': formatter.format(self.activity.date),
                'maxScore': self.activity.scoresystem.getBestScore()}

    @property
    def evaluationInfo(self):
        formatter = self.request.locale.dates.getFormatter('dateTime', 'short')
        gradebook = proxy.removeSecurityProxy(self.context)
        ev = gradebook.getEvaluation(self.student, self.activity)
        if ev is not None and ev.value is not UNSCORED:
            return {'value': ev.value,
                    'time': formatter.format(ev.time)}
        else:
            return {'value': '', 'time': ''}

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect('index.html')

        elif 'DELETE' in self.request:
            self.context.removeEvaluation(self.student, self.activity)

        elif 'UPDATE_SUBMIT' in self.request:
            evaluator = getName(IPerson(self.request.principal))

            score = self.activity.scoresystem.fromUnicode(self.request['grade'])
            gradebook = proxy.removeSecurityProxy(self.context)
            ev = gradebook.getEvaluation(self.student, self.activity)
            if ev is None or score != ev.value:
                self.context.evaluate(
                    self.student, self.activity, score, evaluator)

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

    def update(self):
        self.person = IPerson(self.request.principal)

        """Handle change of current worksheet."""
        if 'currentWorksheet' in self.request:
            for worksheet in self.context.worksheets:
                if worksheet.title == self.request['currentWorksheet']:
                    self.context.setCurrentWorksheet(self.person, worksheet)
                    break

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
