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
"""Activity implementation

$Id$
"""
__docformat__ = 'reStructuredText'

import persistent.dict
import rwproperty
from decimal import Decimal

import zope.interface
from zope import annotation
from zope.container.interfaces import INameChooser
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
CURRENT_WORKSHEET_KEY = 'schooltool.gradebook.currentworksheet'
CATEGORY_WEIGHTS_KEY = 'schooltool.gradebook.categoryweights'


def ensureAtLeastOneWorksheet(activities):
    # only create Sheet1 if no personal worksheet (hidden or not) is found
    for worksheet in activities.all_worksheets:
        if not worksheet.deployed:
            return
    sheet1 = Worksheet(_('Sheet1'))
    chooser = INameChooser(activities)
    name = chooser.chooseName('', sheet1)
    activities[name] = sheet1


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
    for activity in worksheet.values():
        if act_hash == unicode(hash(IKeyReference(activity))):
            return activity
    return None


def isHiddenSource(source):
    obj = getSourceObj(source)
    if obj is None:
        return True
    if interfaces.IWorksheet.providedBy(obj):
        worksheet = obj
    else:
        worksheet = obj.__parent__
    return worksheet.hidden


def today():
    today = getUtility(IDateManager).today
    return today


class Activities(requirement.Requirement):
    zope.interface.implements(interfaces.IActivities)

    def _getDefaultWorksheet(self):
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

    @property
    def worksheets(self):
        return self.values()

    @property
    def all_worksheets(self):
        return [w for k, w in self.items()]

    def values(self):
        worksheets = super(Activities, self).values()
        return [w for w in worksheets if not w.hidden]

    def resetCurrentWorksheet(self, person):
        person = proxy.removeSecurityProxy(person)
        default = self._getDefaultWorksheet()
        self.setCurrentWorksheet(person, default)

    def getCurrentWorksheet(self, person):
        person = proxy.removeSecurityProxy(person)
        ann = annotation.interfaces.IAnnotations(person)
        if CURRENT_WORKSHEET_KEY not in ann:
            ann[CURRENT_WORKSHEET_KEY] = persistent.dict.PersistentDict()
        default = self._getDefaultWorksheet()
        section_id = hash(IKeyReference(self.__parent__))
        worksheet = ann[CURRENT_WORKSHEET_KEY].get(section_id, default)
        if worksheet is not None and worksheet.hidden:
            return default
        return worksheet

    def setCurrentWorksheet(self, person, worksheet):
        person = proxy.removeSecurityProxy(person)
        worksheet = proxy.removeSecurityProxy(worksheet)
        ann = annotation.interfaces.IAnnotations(person)
        if CURRENT_WORKSHEET_KEY not in ann:
            ann[CURRENT_WORKSHEET_KEY] = persistent.dict.PersistentDict()
        section_id = hash(IKeyReference(self.__parent__))
        ann[CURRENT_WORKSHEET_KEY][section_id] = worksheet

    def getCurrentActivities(self, person):
        worksheet = self.getCurrentWorksheet(person)
        if worksheet:
            return list(worksheet.values())
        else:
            return []


class Worksheet(requirement.Requirement):
    zope.interface.implements(interfaces.IWorksheet, 
                              annotation.interfaces.IAttributeAnnotatable)

    deployed = False
    hidden = False

    def values(self):
        activities = []
        for activity in super(Worksheet, self).values():
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                if isHiddenSource(activity.source):
                    continue
            activities.append(activity)
        return activities

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


class ReportWorksheet(requirement.Requirement):
    zope.interface.implements(interfaces.IReportWorksheet)

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
        # Make sure that the sections activities include all the activities of
        # the courses as well
        annotations[ACTIVITIES_KEY] = activities
        zope.container.contained.contained(
            activities, context, 'activities')
        return activities

# Convention to make adapter introspectable
getSectionActivities.factory = Activities


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

    @rwproperty.getproperty
    def points(self):
        return int(self.scoresystem.max)

    @rwproperty.setproperty
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

