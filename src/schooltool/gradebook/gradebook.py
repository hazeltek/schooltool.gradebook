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
from zope.component import adapts, adapter
from zope.component import queryMultiAdapter, getMultiAdapter
from zope.interface import implements, implementer
from zope.location.location import LocationProxy
from zope.publisher.interfaces import IPublishTraverse
from zope.security.proxy import removeSecurityProxy

from schooltool import course, requirement
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.basicperson.interfaces import IBasicPerson
from schooltool.securitypolicy.crowds import ConfigurableCrowd
from schooltool.securitypolicy.crowds import AdministrationCrowd

from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import getSourceObj
from schooltool.gradebook.activity import ensureAtLeastOneWorksheet
from schooltool.requirement.evaluation import Score
from schooltool.requirement.scoresystem import UNSCORED, ScoreValidationError
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.requirement.scoresystem import RangedValuesScoreSystem

GRADEBOOK_SORTING_KEY = 'schooltool.gradebook.sorting'
CURRENT_SECTION_TAUGHT_KEY = 'schooltool.gradebook.currentsectiontaught'
CURRENT_SECTION_ATTENDED_KEY = 'schooltool.gradebook.currentsectionattended'
DUE_DATE_FILTER_KEY = 'schooltool.gradebook.duedatefilter'
COLUMN_PREFERENCES_KEY = 'schooltool.gradebook.columnpreferences'


def getCurrentSectionTaught(person):
    person = proxy.removeSecurityProxy(person)
    ann = annotation.interfaces.IAnnotations(person)
    if CURRENT_SECTION_TAUGHT_KEY not in ann:
        ann[CURRENT_SECTION_TAUGHT_KEY] = None
    else:
        section = ann[CURRENT_SECTION_TAUGHT_KEY]
        try:
            interfaces.IActivities(section)
        except:
            ann[CURRENT_SECTION_TAUGHT_KEY] = None
    return ann[CURRENT_SECTION_TAUGHT_KEY]


def setCurrentSectionTaught(person, section):
    person = proxy.removeSecurityProxy(person)
    ann = annotation.interfaces.IAnnotations(person)
    ann[CURRENT_SECTION_TAUGHT_KEY] = section


def getCurrentSectionAttended(person):
    person = proxy.removeSecurityProxy(person)
    ann = annotation.interfaces.IAnnotations(person)
    if CURRENT_SECTION_ATTENDED_KEY not in ann:
        ann[CURRENT_SECTION_ATTENDED_KEY] = None
    else:
        section = ann[CURRENT_SECTION_ATTENDED_KEY]
        try:
            interfaces.IActivities(section)
        except:
            ann[CURRENT_SECTION_ATTENDED_KEY] = None
    return ann[CURRENT_SECTION_ATTENDED_KEY]


def setCurrentSectionAttended(person, section):
    person = proxy.removeSecurityProxy(person)
    ann = annotation.interfaces.IAnnotations(person)
    ann[CURRENT_SECTION_ATTENDED_KEY] = section


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


@adapter(requirement.interfaces.IHaveEvaluations,
         interfaces.IActivity)
@implementer(requirement.interfaces.IScore)
def getActivityScore(evaluatee, activity):
    evaluations = requirement.interfaces.IEvaluations(evaluatee)
    evaluation = evaluations.get(activity, None)
    if evaluation is None:
        return None
    return requirement.interfaces.IScore(evaluation)


@adapter(requirement.interfaces.IHaveEvaluations,
         interfaces.ILinkedColumnActivity)
@implementer(requirement.interfaces.IScore)
def getLinkedActivityScore(evaluatee, activity):
    source = getSourceObj(activity.source)
    score = queryMultiAdapter(
        (evaluatee, source),
        requirement.interfaces.IScore,
        default=None)
    return score


@adapter(requirement.interfaces.IHaveEvaluations,
         interfaces.IActivityWorksheet)
@implementer(requirement.interfaces.IScore)
def getWorksheetAverageScore(evaluatee, worksheet):
    gradebook = interfaces.IGradebook(worksheet)
    if evaluatee not in gradebook.students:
        return None
    total, value = gradebook.getWorksheetTotalAverage(worksheet, evaluatee)
    score_system = RangedValuesScoreSystem()
    score = Score(score_system, value)
    # Set the __parent__ for security mechanism
    # Let's assume that if you can look at the worksheet, you
    # can also look at the average grades in that worksheet.
    score.__parent__ = worksheet
    return score


def canAverage(worksheet, containing=None):
    if containing is None:
        containing = worksheet
    for activity in worksheet.values():
        linked_act = interfaces.ILinkedColumnActivity(activity, None)
        if linked_act is not None:
            source = getSourceObj(linked_act.source)
            linked_ws = interfaces.IWorksheet(source, None)
            if linked_ws is not None:
                linked_ws = proxy.removeSecurityProxy(linked_ws)
                if (linked_ws is proxy.removeSecurityProxy(containing) or
                    not canAverage(linked_ws, containing)):
                    return False
    return True


class GradebookBase(object):
    def __init__(self, context):
        self.context = context
        # To make URL creation happy
        self.__parent__ = context
        self.section = self.context.__parent__.__parent__
        # Establish worksheets and all activities
        worksheets = interfaces.IActivities(self.section)
        ensureAtLeastOneWorksheet(worksheets)
        self.worksheets = list(worksheets.values())
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
        evaluations = requirement.interfaces.IEvaluations(student)
        evaluation = evaluations.get(activity, None)
        if not (evaluation is None or
                evaluation.value is UNSCORED):
            return True
        return False

    def getScore(self, student, activity):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        score = queryMultiAdapter(
            (student, activity),
            requirement.interfaces.IScore,
            default=None)
        return score

    def evaluate(self, student, activity, score, evaluator=None):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        evaluation = requirement.evaluation.Evaluation(
            activity, activity.scoresystem, score, evaluator)
        evaluations = requirement.interfaces.IEvaluations(student)
        current = evaluations.get(activity)
        if current is not None:
            evaluation.previous = current
        evaluations.addEvaluation(evaluation)

    def removeEvaluation(self, student, activity, evaluator=None):
        """See interfaces.IGradebook"""
        student = self._checkStudent(student)
        activity = self._checkActivity(activity)
        evaluations = requirement.interfaces.IEvaluations(student)
        unscored = requirement.evaluation.Evaluation(
            activity, activity.scoresystem, UNSCORED, evaluator)
        # throw KeyError here, like "del evaluations[activity]" would have
        unscored.previous = evaluations[activity]
        evaluations.addEvaluation(unscored)

    def getWorksheetActivities(self, worksheet):
        if worksheet:
            return list(worksheet.values())
        else:
            return []

    def getWorksheetTotalAverage(self, worksheet, student):
        def getMinMaxValue(score):
            ss = score.scoreSystem
            if IDiscreteValuesScoreSystem.providedBy(ss):
                return (ss.scores[-1][2], ss.scores[0][2],
                    ss.getNumericalValue(score.value))
            elif IRangedValuesScoreSystem.providedBy(ss):
                return ss.min, ss.max, score.value
            return None, None, None

        if worksheet is None or not canAverage(worksheet):
            return 0, UNSCORED

        # XXX: move this to gradebook adapter for GenericWorksheet
        weights = None
        if hasattr(worksheet, 'getCategoryWeights'):
            weights = worksheet.getCategoryWeights()

        # weight by categories
        if weights:
            adjusted_weights = {}
            for activity in self.getWorksheetActivities(worksheet):
                score = self.getScore(student, activity)
                category = activity.category
                if score:
                    if category in weights and weights[category] is not None:
                        adjusted_weights[category] = weights[category]
            total_percentage = 0
            for key in adjusted_weights:
                total_percentage += adjusted_weights[key]
            if total_percentage:
                for key in adjusted_weights:
                    adjusted_weights[key] /= total_percentage

            totals = {}
            average_totals = {}
            average_counts = {}
            for activity in self.getWorksheetActivities(worksheet):
                score = self.getScore(student, activity)
                if not score:
                    continue

                minimum, maximum, value = getMinMaxValue(score)
                if minimum is None:
                    continue

                totals.setdefault(activity.category, Decimal(0))
                totals[activity.category] += value - minimum
                average_totals.setdefault(activity.category, Decimal(0))
                average_totals[activity.category] += (value - minimum)
                average_counts.setdefault(activity.category, Decimal(0))
                average_counts[activity.category] += (maximum - minimum)
            average = Decimal(0)
            for category, value in average_totals.items():
                if category in weights and weights[category] is not None:
                    average += ((value / average_counts[category]) *
                        adjusted_weights[category])
            if not len(average_counts):
                return 0, UNSCORED
            else:
                return sum(totals.values()), average * 100

        # when not weighting categories, the default is to weight the
        # evaluations by activities.
        else:
            total = 0
            count = 0
            for activity in self.getWorksheetActivities(worksheet):
                score = self.getScore(student, activity)
                if not score:
                    continue
                minimum, maximum, value = getMinMaxValue(score)
                if minimum is None:
                    continue
                total += value - minimum
                count += maximum - minimum
            if count:
                return total, Decimal(100 * total) / Decimal(count)
            else:
                return 0, UNSCORED

    def getCurrentWorksheet(self, person):
        section = self.section
        worksheets = interfaces.IActivities(section)
        current = worksheets.getCurrentWorksheet(person)
        return current

    def setCurrentWorksheet(self, person, worksheet):
        section = self.section
        worksheets = interfaces.IActivities(section)
        worksheet = proxy.removeSecurityProxy(worksheet)
        worksheets.setCurrentWorksheet(person, worksheet)

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
            if (activity in activities and
                evaluation.value is not UNSCORED):
                yield activity, evaluation

    def getEvaluationsForStudent(self, student):
        """See interfaces.IGradebook"""
        self._checkStudent(student)
        evaluations = requirement.interfaces.IEvaluations(student)
        for activity, evaluation in evaluations.items():
            if (activity in self.activities and
                evaluation.value is not UNSCORED):
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
    adapts(interfaces.IActivityWorksheet)

    def __init__(self, context):
        super(Gradebook, self).__init__(context)
        # To make URL creation happy
        self.__name__ = 'gradebook'


class MyGrades(GradebookBase):
    implements(interfaces.IMyGrades)
    adapts(interfaces.IActivityWorksheet)

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
        gradebook = self.context.gradebook
        student = self.context.student
        activity = self.context.activities[name]
        # XXX: hack to receive the evaluator from the form
        evaluator = removeSecurityProxy(self.context).evaluator
        try:
            if value is None or value == '':
                score = gradebook.getScore(student, activity)
                if score:
                    gradebook.removeEvaluation(student, activity, evaluator=evaluator)
            else:
                score_value = activity.scoresystem.fromUnicode(value)
                gradebook.evaluate(student, activity, score_value, evaluator)
        except ScoreValidationError:
            pass

    def __getattr__(self, name):
        activity = self.context.activities[name]
        score = self.context.gradebook.getScore(self.context.student, activity)
        if not score:
            return ''
        elif interfaces.ILinkedColumnActivity.providedBy(activity):
            sourceObj = getSourceObj(activity.source)
            if interfaces.IActivityWorksheet.providedBy(sourceObj):
                return '%.1f' % score.value
        return score.value


def getWorksheetSection(worksheet):
    """Adapt IActivityWorksheet to ISection."""
    return worksheet.__parent__.__parent__


def getGradebookSection(gradebook):
    """Adapt IGradebook to ISection."""
    return course.interfaces.ISection(gradebook.context)


def getMyGradesSection(gradebook):
    """Adapt IMyGrades to ISection."""
    return course.interfaces.ISection(gradebook.context)


class GradebookEditorsCrowd(ConfigurableCrowd):
    setting_key = 'administration_can_grade_students'

    def contains(self, principal):
        """Return the value of the related setting (True or False)."""
        return (AdministrationCrowd(self.context).contains(principal) and
                super(GradebookEditorsCrowd, self).contains(principal))

