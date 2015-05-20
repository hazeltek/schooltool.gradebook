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
"""Activity implementation
"""
__docformat__ = 'reStructuredText'

import persistent.dict
from decimal import Decimal

import zope.interface
from zope import annotation
from zope.keyreference.interfaces import IKeyReference
from zope.security import proxy
from zope.component import queryAdapter, getAdapters, getUtility
from zope.schema.interfaces import IVocabularyFactory

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook import GradebookMessage as _
from schooltool.requirement import requirement, scoresystem
from schooltool.gradebook import interfaces
from schooltool.term.interfaces import IDateManager
from schooltool.course.interfaces import ISection

ACTIVITIES_KEY = 'schooltool.gradebook.activities'
CATEGORY_WEIGHTS_KEY = 'schooltool.gradebook.categoryweights'
COURSE_ACTIVITIES_KEY = 'schooltool.gradebook.course_activities'
COURSE_DEPLOYED_WORKSHEETS_KEY = 'schooltool.gradebook.course_deployed'


def ensureAtLeastOneWorksheet(worksheets, factory=None, title=None):
    return


def createSourceString(sourceObj):
    if interfaces.IActivity.providedBy(sourceObj):
        act_hash = unicode(hash(IKeyReference(sourceObj)))
        worksheet = sourceObj.__parent__
    else:
        act_hash = 'ave'
        worksheet = sourceObj
    section = worksheet.__parent__.__parent__
    sectionContainer = section.__parent__
    return '%s_%s_%s_%s' % (sectionContainer.__name__, section.__name__,
        unicode(hash(IKeyReference(worksheet))), act_hash)


def getSourceObj(source):
    if source is None:
        return None

    items = source.split('_')
    scid = items[0]
    ws_hash = items[-2]
    act_hash = items[-1]
    sid = '_'.join(items[1:-2])

    app = ISchoolToolApplication(None)
    sectionContainer = app['schooltool.course.section'].get(scid, None)
    if sectionContainer is None:
        return None

    section = sectionContainer.get(sid, None)
    if section is None:
        return None

    for worksheet in interfaces.IActivities(section).values():
        if ws_hash == unicode(hash(IKeyReference(worksheet))):
            break
    else:
        return None

    if act_hash == 'ave':
        return worksheet
    for key, activity in worksheet.items():
        if act_hash == unicode(hash(IKeyReference(activity))):
            return activity
    return None


def isHiddenSource(source):
    obj = getSourceObj(source)
    if obj is None:
        return True
    if interfaces.IActivityWorksheet.providedBy(obj):
        worksheet = obj
    else:
        worksheet = obj.__parent__
    return worksheet.hidden


def today():
    today = getUtility(IDateManager).today
    return today


class Worksheets(requirement.Requirement):
    zope.interface.implements(interfaces.IWorksheets)

    annotations_current_worksheet_key = None

    def getDefaultWorksheet(self):
        # order of preference is:
        # 1) first non-hidden personal sheet
        # 2) first non-hidden deployed sheet
        # 3) first sheet outright if all are hidden
        # 4) None if there are no worksheets at all
        firstDeployed, firstAbsolute = None, None
        for worksheet in self.all_worksheets:
            if firstAbsolute is None:
                firstAbsolute = worksheet
            if worksheet.deployed:
                if firstDeployed is None and not worksheet.hidden:
                    firstDeployed = worksheet
            elif not worksheet.hidden:
                return worksheet
        if firstDeployed is not None:
            return firstDeployed
        return firstAbsolute

    def getCurrentSectionWorksheets(self, person):
        if self.annotations_current_worksheet_key is None:
            return None
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if self.annotations_current_worksheet_key not in ann:
            ann[self.annotations_current_worksheet_key] = persistent.dict.PersistentDict()
        return ann[self.annotations_current_worksheet_key]

    @property
    def worksheets(self):
        return self.values()

    @property
    def all_worksheets(self):
        return [w for k, w in self.items()]

    def values(self):
        worksheets = super(Worksheets, self).values()
        return [w for w in worksheets if not w.hidden]

    def resetCurrentWorksheet(self, person):
        person = proxy.removeSecurityProxy(person)
        default = self.getDefaultWorksheet()
        self.setCurrentWorksheet(person, default)

    def getCurrentWorksheet(self, person):
        default = self.getDefaultWorksheet()
        current = self.getCurrentSectionWorksheets(person)
        if not current:
            return default
        section_id = hash(IKeyReference(self.__parent__))
        worksheet = current.get(section_id, default)
        if worksheet is not None and worksheet.hidden:
            return default
        return worksheet

    def setCurrentWorksheet(self, person, worksheet):
        current = self.getCurrentSectionWorksheets(person)
        worksheet = proxy.removeSecurityProxy(worksheet)
        section_id = hash(IKeyReference(self.__parent__))
        current[section_id] = worksheet

    def getCurrentActivities(self, person):
        worksheet = self.getCurrentWorksheet(person)
        if worksheet:
            return list(worksheet.values())
        else:
            return []


class Activities(Worksheets):
    zope.interface.implements(interfaces.IActivities)

    annotations_current_worksheet_key = 'schooltool.gradebook.currentworksheet'


class CourseActivities(requirement.Requirement):
    zope.interface.implements(interfaces.ICourseActivities)


class CourseDeployedWorksheets(requirement.Requirement):
    zope.interface.implements(interfaces.ICourseDeployedWorksheets)


class GenericWorksheet(requirement.Requirement):
    zope.interface.implements(interfaces.IWorksheet,
                              annotation.interfaces.IAttributeAnnotatable)

    deployed = False
    hidden = False


class WorksheetAnnotatableMixin(object):
    zope.interface.implements(annotation.interfaces.IAttributeAnnotatable)

    def getCategoryWeights(self):
        ann = annotation.interfaces.IAnnotations(self)
        if CATEGORY_WEIGHTS_KEY not in ann:
            ann[CATEGORY_WEIGHTS_KEY] = persistent.dict.PersistentDict()
        return ann[CATEGORY_WEIGHTS_KEY]

    def setCategoryWeight(self, category, weight):
        ann = annotation.interfaces.IAnnotations(self)
        if CATEGORY_WEIGHTS_KEY not in ann:
            ann[CATEGORY_WEIGHTS_KEY] = persistent.dict.PersistentDict()
        ann[CATEGORY_WEIGHTS_KEY][category] = weight


class Worksheet(GenericWorksheet, WorksheetAnnotatableMixin):
    zope.interface.implements(interfaces.IActivityWorksheet,
                              annotation.interfaces.IAttributeAnnotatable)

    def values(self):
        activities = []
        for activity in super(Worksheet, self).values():
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                if isHiddenSource(activity.source):
                    continue
            activities.append(activity)
        return activities

    def canAverage(self):
        return True


class ReportWorksheet(requirement.Requirement, WorksheetAnnotatableMixin):
    zope.interface.implements(interfaces.IReportWorksheet)

    deployed = False


class CourseWorksheet(requirement.Requirement, WorksheetAnnotatableMixin):
    zope.interface.implements(interfaces.ICourseWorksheet)

    deployed = False


class Activity(requirement.Requirement):
    zope.interface.implements(interfaces.IActivity)

    def __init__(self, title, category, scoresystem,
                 description=None, label=None, due_date=None, date=None):
        super(Activity, self).__init__(title)
        self.label = label
        self.description = description
        self.category = category
        self.scoresystem = scoresystem
        if not due_date:
            due_date = today()
        self.due_date = due_date
        if not date:
            date = today()
        self.date = date

    def __repr__(self):
        return '<%s %r>' %(self.__class__.__name__, self.title)


class ReportActivity(Activity):
    zope.interface.implements(interfaces.IReportActivity)


def getSectionActivities(context):
    '''IAttributeAnnotatable object to IActivities adapter.'''
    annotations = annotation.interfaces.IAnnotations(context)
    try:
        return annotations[ACTIVITIES_KEY]
    except KeyError:
        activities = Activities(_('Activities'))
        annotations[ACTIVITIES_KEY] = activities
        zope.container.contained.contained(
            activities, context, 'activities')
        return activities

# Convention to make adapter introspectable
getSectionActivities.factory = Activities


def getCourseActivities(context):
    '''IAttributeAnnotatable object to ICourseActivities adapter.'''
    annotations = annotation.interfaces.IAnnotations(context)
    try:
        return annotations[COURSE_ACTIVITIES_KEY]
    except KeyError:
        activities = CourseActivities(_('Course Activities'))
        annotations[COURSE_ACTIVITIES_KEY] = activities
        zope.container.contained.contained(
            activities, context, 'activities')
        return activities

# Convention to make adapter introspectable
getCourseActivities.factory = CourseActivities


def getCourseDeployedWorksheets(context):
    '''IAttributeAnnotatable object to ICourseDeployedWorksheets adapter.'''
    annotations = annotation.interfaces.IAnnotations(context)
    try:
        return annotations[COURSE_DEPLOYED_WORKSHEETS_KEY]
    except KeyError:
        worksheets = CourseDeployedWorksheets(_('Deployed Worksheets'))
        annotations[COURSE_DEPLOYED_WORKSHEETS_KEY] = worksheets
        zope.container.contained.contained(
            worksheets, context, 'deployed_worksheets')
        return worksheets

# Convention to make adapter introspectable
getCourseDeployedWorksheets.factory = CourseDeployedWorksheets


class LinkedActivity(Activity):
    zope.interface.implements(interfaces.ILinkedActivity)

    def __init__(self, external_activity, category, points, label,
                 due_date=None):
        custom = scoresystem.RangedValuesScoreSystem(
            u'generated', min=Decimal(0), max=Decimal(points))
        super(LinkedActivity, self).__init__(external_activity.title,
                                             category,
                                             custom,
                                             external_activity.description,
                                             label,
                                             due_date)
        self.source = external_activity.source
        self.external_activity_id = external_activity.external_activity_id

    @property
    def points(self):
        return int(self.scoresystem.max)

    @points.setter
    def points(self, value):
        self.scoresystem.max = Decimal(value)

    def getExternalActivity(self):
        section = self.__parent__.__parent__.__parent__
        adapter = queryAdapter(section, interfaces.IExternalActivities,
                               name=self.source)
        if adapter is not None:
            return adapter.getExternalActivity(self.external_activity_id)


class ExternalActivitiesSource(object):
    zope.interface.implements(interfaces.IExternalActivitiesSource)

    def __init__(self, context):
        self.section = context

    def activities(self):
        result = []
        for name, adapter in getAdapters((self.section,),
                                         interfaces.IExternalActivities):
            for external_activity in adapter.getExternalActivities():
                result.append((adapter, external_activity))
        return sorted(result, key=self.sortByTitles())

    def sortByTitles(self):
        return lambda x:(x[0].title, x[1].title)

    def __iter__(self):
        return iter(self.activities())

    def __len__(self):
        return len(self.activities())

    def __contains__(self, other_tuple):
        try:
            external_activity = other_tuple[1]
            return bool([value for value in self.activities()
                         if value[1] == external_activity])
        except (IndexError,):
            return False


class ExternalActivitiesVocabulary(object):
    zope.interface.implements(IVocabularyFactory)

    def __call__(self, context):
        try:
            section = ISection(context)
        except (TypeError,):
            linked_activity = proxy.removeSecurityProxy(context)
            section = ISection(linked_activity.__parent__)
        return ExternalActivitiesSource(section)


class LinkedColumnActivity(Activity):
    zope.interface.implements(interfaces.ILinkedColumnActivity)

    def __init__(self, title, category, label, source):
        super(LinkedColumnActivity, self).__init__(title, category, None, '',
            label)
        self.source = source

