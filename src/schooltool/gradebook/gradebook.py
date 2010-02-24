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
Gradebook Implementation
"""
__docformat__ = 'reStructuredText'

from decimal import Decimal

from persistent.dict import PersistentDict
from zope.security import proxy
from zope import annotation
from zope.keyreference.interfaces import IKeyReference
from zope.component import adapts, queryMultiAdapter, getMultiAdapter
from zope.interface import implements
from zope.location.location import LocationProxy
from zope.publisher.interfaces import IPublishTraverse
from zope.security.proxy import removeSecurityProxy

from schooltool import course, requirement
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.basicperson.interfaces import IBasicPerson
from schooltool.securitypolicy.crowds import ConfigurableCrowd
from schooltool.securitypolicy.crowds import AggregateCrowd
from schooltool.securitypolicy.crowds import ManagersCrowd
from schooltool.securitypolicy.crowds import ClerksCrowd
from schooltool.securitypolicy.crowds import AdministratorsCrowd

from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import getSourceObj
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.requirement.scoresystem import UNSCORED, ScoreValidationError
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.requirement.scoresystem import RangedValuesScoreSystem

GRADEBOOK_SORTING_KEY = 'schooltool.gradebook.sorting'
CURRENT_WORKSHEET_KEY = 'schooltool.gradebook.currentworksheet'
DUE_DATE_FILTER_KEY = 'schooltool.gradebook.duedatefilter'
COLUMN_PREFERENCES_KEY = 'schooltool.gradebook.columnpreferences'


class WorksheetGradebookTraverser(object):
    '''Traverser that goes from a worksheet to the gradebook'''

    implements(IPublishTraverse)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        context = proxy.removeSecurityProxy(self.context)
        try:
            activity = context[name]
            return activity
        except KeyError:
            if name == 'gradebook':
                gb = interfaces.IGradebook(context)
                gb = LocationProxy(gb, self.context, name)
                gb.__setattr__('__parent__', gb.__parent__)
                return gb
            elif name == 'mygrades':
                gb = interfaces.IMyGrades(context)
                gb = LocationProxy(gb, self.context, name)
                gb.__setattr__('__parent__', gb.__parent__)
                return gb
            else:
                return queryMultiAdapter((self.context, request), name=name)


class StudentGradebookTraverser(object):
    '''Traverser that goes from a section's gradebook to a student
    gradebook using the student's username as the path in the url.'''

    implements(IPublishTraverse)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        app = ISchoolToolApplication(None)
        context = removeSecurityProxy(self.context)

        try:
            student = app['persons'][name]
        except KeyError:
            return queryMultiAdapter((self.context, request), name=name)

        try:
            gb = getMultiAdapter((student, context), interfaces.IStudentGradebook)
        except ValueError:
            return queryMultiAdapter((self.context, request), name=name)

        # location looks like http://host/path/to/gradebook/studentsUsername
        gb = LocationProxy(gb, self.context, name)
        return gb


class GradebookBase(object):
    def __init__(self, context):
        self.context = context
        # To make URL creation happy
        self.__parent__ = context
        self.section = self.context.__parent__.__parent__
        # Establish worksheets and all activities
        activities = interfaces.IActivities(self.section)
        ensureAtLeastOneWorksheet(activities)
        self.worksheets = list(activities.values())
        self.activities = []
        for activity in context.values():
            self.activities.append(activity)
        self.students = list(self.section.members)

    def _checkStudent(self, student):
        if student not in self.students:
            raise ValueError(
                'Student %r is not in this section.' %student.username)
        # Remove security proxy, so that the object can be referenced and
        # adapters are not proxied. Note that the gradebook itself has
        # sufficient tight security.
        return proxy.removeSecurityProxy(student)

    def _checkActivity(self, activity):
        # Remove security proxy, so that the object can be referenced and
        # adapters are not proxied. Note that the gradebook itself has
        # sufficient tight security.
        if activity in self.activities:
            return proxy.removeSecurityProxy(activity)
        raise ValueError(
            '%r is not part of this section.' %activity.title)

    def hasEvaluation(self, student, activity):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        if activity in requirement.interfaces.IEvaluations(student):
            return True
        return False

    def getEvaluation(self, student, activity):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        evaluations = requirement.interfaces.IEvaluations(student)
        ev, value, ss = None, None, None
        if interfaces.ILinkedColumnActivity.providedBy(activity):
            sourceObj = getSourceObj(activity.source)
            if interfaces.IActivity.providedBy(sourceObj):
                ev = evaluations.get(sourceObj, None)
                ss = sourceObj.scoresystem
            elif interfaces.IWorksheet.providedBy(sourceObj):
                gb = interfaces.IGradebook(sourceObj)
                if student in gb.students:
                    total, value = gb.getWorksheetTotalAverage(sourceObj, student)
                    ss = RangedValuesScoreSystem()
        else:
            ev = evaluations.get(activity, None)
            ss = activity.scoresystem
        if ev is not None and ev.value is not UNSCORED:
            value = ev.value
        return value, ss

    def evaluate(self, student, activity, score, evaluator=None):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        evaluation = requirement.evaluation.Evaluation(
            activity, activity.scoresystem, score, evaluator)
        evaluations = requirement.interfaces.IEvaluations(student)
        evaluations.addEvaluation(evaluation)

    def removeEvaluation(self, student, activity):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        evaluations = requirement.interfaces.IEvaluations(student)
        del evaluations[activity]

    def getWorksheetActivities(self, worksheet):
        if worksheet:
            return list(worksheet.values())
        else:
            return []

    def getWorksheetTotalAverage(self, worksheet, student):
        if worksheet is None:
            return 0, UNSCORED
        weights = worksheet.getCategoryWeights()

        # weight by categories
        if weights:
            adjusted_weights = {}
            for activity in self.getWorksheetActivities(worksheet):
                value, ss = self.getEvaluation(student, activity)
                category = activity.category
                if value is not None and value is not UNSCORED:
                    if category in weights:
                        adjusted_weights[category] = weights[category]
            total_percentage = 0
            for key in adjusted_weights:
                total_percentage += adjusted_weights[key]
            for key in adjusted_weights:
                adjusted_weights[key] /= total_percentage

            totals = {}
            average_totals = {}
            average_counts = {}
            for activity in self.getWorksheetActivities(worksheet):
                value, ss = self.getEvaluation(student, activity)
                if value is not None and value is not UNSCORED:
                    if IDiscreteValuesScoreSystem.providedBy(ss):
                        minimum = ss.scores[-1][2]
                        maximum = ss.scores[0][2]
                        value = ss.getNumericalValue(value)
                    elif IRangedValuesScoreSystem.providedBy(ss):
                        minimum = ss.min
                        maximum = ss.max
                    else:
                        continue
                    totals.setdefault(activity.category, Decimal(0))
                    totals[activity.category] += value - minimum
                    average_totals.setdefault(activity.category, Decimal(0))
                    average_totals[activity.category] += (value - minimum)
                    average_counts.setdefault(activity.category, Decimal(0))
                    average_counts[activity.category] += (maximum - minimum)
            average = Decimal(0)
            for category, value in average_totals.items():
                if category in weights:
                    average += ((value / average_counts[category]) *
                        adjusted_weights[category])
            if not len(average_counts):
                return 0, UNSCORED
            else:
                return sum(totals.values()), int(round(average*100))

        # when not weighting categories, the default is to weight the
        # evaluations by activities.
        else:
            total = 0
            count = 0
            for activity in self.getWorksheetActivities(worksheet):
                value, ss = self.getEvaluation(student, activity)
                if value is not None and value is not UNSCORED:
                    if IDiscreteValuesScoreSystem.providedBy(ss):
                        minimum = ss.scores[-1][2]
                        maximum = ss.scores[0][2]
                        value = ss.getNumericalValue(value)
                    elif IRangedValuesScoreSystem.providedBy(ss):
                        minimum = ss.min
                        maximum = ss.max
                    else:
                        continue
                    total += value - minimum
                    count += maximum - minimum
            if count:
                return total, int(round(Decimal(100 * total) / Decimal(count)))
            else:
                return 0, UNSCORED

    def getCurrentWorksheet(self, person):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if CURRENT_WORKSHEET_KEY not in ann:
            ann[CURRENT_WORKSHEET_KEY] = PersistentDict()
        if self.worksheets:
            default = self.worksheets[0]
        else:
            default = None
        section_id = hash(IKeyReference(self.section))
        worksheet = ann[CURRENT_WORKSHEET_KEY].get(section_id, default)
        if worksheet is not None and worksheet.hidden:
            return default
        return worksheet

    def setCurrentWorksheet(self, person, worksheet):
        person = proxy.removeSecurityProxy(person)
        worksheet = proxy.removeSecurityProxy(worksheet)
        ann = annotation.interfaces.IAnnotations(person)
        if CURRENT_WORKSHEET_KEY not in ann:
            ann[CURRENT_WORKSHEET_KEY] = PersistentDict()
        section_id = hash(IKeyReference(self.section))
        ann[CURRENT_WORKSHEET_KEY][section_id] = worksheet

    def getDueDateFilter(self, person):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if DUE_DATE_FILTER_KEY not in ann:
            return (False, '9')
        return ann[DUE_DATE_FILTER_KEY]

    def setDueDateFilter(self, person, flag, weeks):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        ann[DUE_DATE_FILTER_KEY] = (flag, weeks)

    def getColumnPreferences(self, person):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if COLUMN_PREFERENCES_KEY not in ann:
            return PersistentDict()
        return ann[COLUMN_PREFERENCES_KEY]

    def setColumnPreferences(self, person, columnPreferences):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        ann[COLUMN_PREFERENCES_KEY] = PersistentDict(columnPreferences)

    def getCurrentActivities(self, person):
        worksheet = self.getCurrentWorksheet(person)
        return self.getWorksheetActivities(worksheet)

    def getCurrentEvaluationsForStudent(self, person, student):
        """See interfaces.IGradebook"""
        self._checkStudent(student)
        evaluations = requirement.interfaces.IEvaluations(student)
        activities = self.getCurrentActivities(person)
        for activity, evaluation in evaluations.items():
            if activity in activities:
                yield activity, evaluation

    def getEvaluationsForStudent(self, student):
        """See interfaces.IGradebook"""
        self._checkStudent(student)
        evaluations = requirement.interfaces.IEvaluations(student)
        for activity, evaluation in evaluations.items():
            if activity in self.activities:
                yield activity, evaluation

    def getEvaluationsForActivity(self, activity):
        """See interfaces.IGradebook"""
        self._checkActivity(activity)
        for student in self.section.members:
            evaluations = requirement.interfaces.IEvaluations(student)
            if activity in evaluations:
                yield student, evaluations[activity]

    def getSortKey(self, person):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if GRADEBOOK_SORTING_KEY not in ann:
            ann[GRADEBOOK_SORTING_KEY] = PersistentDict()
        section_id = hash(IKeyReference(self.section))
        return ann[GRADEBOOK_SORTING_KEY].get(section_id, ('student', False))

    def setSortKey(self, person, value):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if GRADEBOOK_SORTING_KEY not in ann:
            ann[GRADEBOOK_SORTING_KEY] = PersistentDict()
        section_id = hash(IKeyReference(self.section))
        ann[GRADEBOOK_SORTING_KEY][section_id] = value


class Gradebook(GradebookBase):
    implements(interfaces.IGradebook)
    adapts(interfaces.IWorksheet)

    def __init__(self, context):
        super(Gradebook, self).__init__(context)
        # To make URL creation happy
        self.__name__ = 'gradebook'


class MyGrades(GradebookBase):
    implements(interfaces.IMyGrades)
    adapts(interfaces.IWorksheet)

    def __init__(self, context):
        super(MyGrades, self).__init__(context)
        # To make URL creation happy
        self.__name__ = 'mygrades'


class StudentGradebook(object):
    """Adapter of student and gradebook used for grading one student at a
       time"""
    implements(interfaces.IStudentGradebook)
    adapts(IBasicPerson, interfaces.IGradebook)

    def __init__(self, student, gradebook):
        self.student = student
        self.gradebook = gradebook
        activities = [(str(activity.__name__), activity)
            for activity in gradebook.activities]
        self.activities = dict(activities)


class StudentGradebookFormAdapter(object):
    """Adapter used by grade student view to interact with student
       gradebook"""
    implements(interfaces.IStudentGradebookForm)
    adapts(interfaces.IStudentGradebook)

    def __init__(self, context):
        self.__dict__['context'] = context

    def __setattr__(self, name, value):
        activity = self.context.activities[name]
        evaluator = None
        try:
            score = activity.scoresystem.fromUnicode(value)
            self.context.gradebook.evaluate(self.context.student, activity,
                                            score, evaluator)
        except ScoreValidationError:
            pass

    def __getattr__(self, name):
        activity = self.context.activities[name]
        value, ss = self.context.gradebook.getEvaluation(self.context.student,
            activity)
        if value is None or value is UNSCORED:
            value = ''
        return value


def getWorksheetSection(worksheet):
    """Adapt IWorksheet to ISection."""
    return worksheet.__parent__.__parent__


def getGradebookSection(gradebook):
    """Adapt IGradebook to ISection."""
    return course.interfaces.ISection(gradebook.context)


def getMyGradesSection(gradebook):
    """Adapt IMyGrades to ISection."""
    return course.interfaces.ISection(gradebook.context)


class GradebookEditorsCrowd(AggregateCrowd, ConfigurableCrowd):
    setting_key = 'administration_can_grade_students'

    def crowdFactories(self):
        return [ManagersCrowd, AdministratorsCrowd, ClerksCrowd]

    def contains(self, principal):
        """Return the value of the related setting (True or False)."""
        return (ConfigurableCrowd.contains(self, principal) and
                AggregateCrowd.contains(self, principal))

