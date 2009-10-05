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
Report Card Views
"""

from zope.app.component.vocabulary import UtilityVocabulary, UtilityTerm
from zope.app.container.interfaces import INameChooser
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import adapts, queryUtility
from zope.interface import Interface, implements
from zope.schema import Choice, Int
from zope.security.checker import canWrite
from zope.security.interfaces import Unauthorized
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL

from z3c.form import form, field, button

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.common import SchoolToolMessage as _
from schooltool.course.interfaces import ISectionContainer, ISection
from schooltool.person.interfaces import IPerson
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.term.interfaces import ITerm, IDateManager

from schooltool.gradebook.interfaces import IGradebookRoot
from schooltool.gradebook.interfaces import IActivities, IReportActivity
from schooltool.gradebook.activity import Worksheet, Activity, ReportActivity
from schooltool.gradebook.category import getCategories
from schooltool.gradebook.gradebook_init import ReportLayout, ReportColumn
from schooltool.gradebook.gradebook_init import OutlineActivity
from schooltool.requirement.interfaces import ICommentScoreSystem
from schooltool.requirement.interfaces import IScoreSystem
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.requirement.scoresystem import RangedValuesScoreSystem

ABSENT_HEADING = _('Absent')
TARDY_HEADING = _('Tardy')
ABSENT_KEY = 'absent'
TARDY_KEY = 'tardy'

def copyActivities(sourceWorksheet, destWorksheet):
    """Copy the activities from the source worksheet to the destination."""

    for key, activity in sourceWorksheet.items():
        activityCopy = Activity(activity.title, activity.category,
                                activity.scoresystem, activity.description,
                                activity.label)
        destWorksheet[key] = activityCopy


class TemplatesView(object):
    """A view for managing report sheet templates"""

    @property
    def worksheets(self):
        """Get  a list of all worksheets."""
        pos = 0
        for worksheet in self.context.values():
            pos += 1
            yield {'name': getName(worksheet),
                   'title': worksheet.title,
                   'url': absoluteURL(worksheet, self.request),
                   'pos': pos}

    def positions(self):
        return range(1, len(self.context.values())+1)

    def canModify(self):
        return canWrite(self.context, 'title')

    def update(self):
        self.person = IPerson(self.request.principal, None)
        if self.person is None:
            # XXX ignas: i had to do this to make the tests pass,
            # someone who knows what this code should do if the user
            # is unauthenticated should add the relevant code
            raise Unauthorized("You don't have the permission to do this.")

        if 'DELETE' in self.request:
            for name in self.request.get('delete', []):
                del self.context[name]

        elif 'form-submitted' in self.request:
            old_pos = 0
            for worksheet in self.context.values():
                old_pos += 1
                name = getName(worksheet)
                if 'pos.'+name not in self.request:
                    continue
                new_pos = int(self.request['pos.'+name])
                if new_pos != old_pos:
                    self.context.changePosition(name, new_pos-1)


def ReportScoreSystemsVocabulary(context):
    vocab = UtilityVocabulary(context, interface=IScoreSystem)
    rangedTerm = UtilityTerm('ranged', _('-- Use range below --'))
    vocab._terms[rangedTerm.token] = rangedTerm
    return vocab


class IReportScoreSystem(Interface):
    """A schema used to choose an existing score system."""

    scoresystem = Choice(
        title=_('Score System'),
        description=_('Choose an existing score system or use range below'),
        vocabulary='schooltool.gradebook.reportscoresystems',
        required=True)

    min = Int(
        title=_("Minimum"),
        description=_("Lowest integer score value possible"),
        min=0,
        required=False)

    max = Int(
        title=_("Maximum"),
        description=_("Highest integer score value possible"),
        min=0,
        required=False)


class ReportScoresSystem(object):
    implements(IReportScoreSystem)
    adapts(IReportActivity)

    def __init__(self, context):
        self.__dict__['context'] = context

    def isRanged(self, ss):
        return (IRangedValuesScoreSystem.providedBy(ss) and
                ss.title == 'generated')

    def getValue(self, name, default):
        if default is None:
            default = 0
        value = self.__dict__.get(name, default)
        if value is None:
            return default
        return value

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        ss = self.context.scoresystem

        if name == 'scoresystem':
            if value == 'ranged':
                if self.isRanged(ss):
                    minimum = self.getValue('min', ss.min)
                    maximum = self.getValue('max', ss.max)
                else:
                    minimum = self.getValue('min', 0)
                    maximum = self.getValue('max', 100)
                self.context.scoresystem = RangedValuesScoreSystem(u'generated', 
                    min=minimum, max=maximum)
            else:
                self.context.scoresystem = value

        else: # min, max
            if self.isRanged(ss):
                minimum = self.getValue('min', ss.min)
                maximum = self.getValue('max', ss.max)
                self.context.scoresystem = RangedValuesScoreSystem(u'generated', 
                    min=minimum, max=maximum)

    def __getattr__(self, name):
        ss = self.context.scoresystem
        if ss is None:
            return None
        rv = None
        if self.isRanged(ss):
            if name == 'scoresystem':
                rv = 'ranged'
            elif name == 'min':
                rv = ss.min
            elif name == 'max':
                rv = ss.max
        else:
            if name == 'scoresystem':
                rv = ss
        return rv


class ReportActivityAddView(form.AddForm):
    """A view for adding an activity."""
    label = _("Add new activity")
    template = ViewPageTemplateFile('add_edit_report_activity.pt')

    fields = field.Fields(IReportActivity)
    fields = fields.select('title', 'label', 'description')
    fields += field.Fields(IReportScoreSystem)

    def updateActions(self):
        super(ReportActivityAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    @button.buttonAndHandler(_('Add'), name='add')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        obj = self.createAndAdd(data)
        if obj is not None:
            # mark only as finished if we get the new object
            self._finishedAdd = True

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        url = absoluteURL(self.context, self.request)
        self.request.response.redirect(url)

    def create(self, data):
        categories = getCategories(ISchoolToolApplication(None))
        if data['scoresystem'] == 'ranged':
            minimum = data['min']
            if minimum is None:
                minimum = 0
            maximum = data['max']
            if maximum is None:
                maximum = 100
            scoresystem = RangedValuesScoreSystem(u'generated', 
                min=minimum, max=maximum)
        else:
            scoresystem = data['scoresystem']
        activity = ReportActivity(data['title'], categories.getDefaultKey(), 
                                  scoresystem, data['description'],
                                  data['label'])
        return activity

    def add(self, activity):
        """Add activity to the worksheet."""
        chooser = INameChooser(self.context)
        name = chooser.chooseName('', activity)
        self.context[name] = activity
        return activity

    def nextURL(self):
        return absoluteURL(self.context, self.request)


class ReportActivityEditView(form.EditForm):
    """Edit form for basic person."""
    form.extends(form.EditForm)
    template = ViewPageTemplateFile('add_edit_report_activity.pt')

    fields = field.Fields(IReportActivity)
    fields = fields.select('title', 'label', 'description')
    fields += field.Fields(IReportScoreSystem)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def updateActions(self):
        super(ReportActivityEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    def applyChanges(self, data):
        super(ReportActivityEditView, self).applyChanges(data)
        self.request.response.redirect(self.nextURL())

    @property
    def label(self):
        return _(u'Change information for ${fullname}',
                 mapping={'fullname': self.context.title})

    def nextURL(self):
        return absoluteURL(self.context.__parent__, self.request)


class DeployReportWorksheetBaseView(object):
    """The base class for deploying a report sheet template"""

    @property
    def worksheets(self):
        """Get  a list of all report worksheets."""
        root = IGradebookRoot(ISchoolToolApplication(None))
        for worksheet in root.templates.values():
            yield {'name': getName(worksheet),
                   'title': worksheet.title}

    def update(self):
        if 'form-submitted' in self.request:
            if 'DEPLOY' in self.request:
                self.deploy()
            self.request.response.redirect(self.nextURL())

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def deployTerm(self, term):
        root = IGradebookRoot(ISchoolToolApplication(None))
        worksheet = root.templates[self.request['reportWorksheet']]

        # copy worksheet template to the term
        schoolyear = ISchoolYear(term)
        deployedKey = '%s_%s' % (schoolyear.__name__, term.__name__)
        deployedWorksheet = Worksheet(worksheet.title)
        chooser = INameChooser(root.deployed)
        name = chooser.chooseName(deployedKey, deployedWorksheet)
        root.deployed[name] = deployedWorksheet
        copyActivities(worksheet, deployedWorksheet)

        # now copy the template to all sections in the term
        sections = ISectionContainer(term)
        for section in sections.values():
            activities = IActivities(section)
            worksheetCopy = Worksheet(deployedWorksheet.title)
            worksheetCopy.deployed = True
            activities[deployedWorksheet.__name__] = worksheetCopy
            copyActivities(deployedWorksheet, worksheetCopy)


class DeployReportWorksheetSchoolYearView(DeployReportWorksheetBaseView):
    """A view for deploying a report sheet template to a schoolyear"""

    def deploy(self):
        for term in self.context.values():
            self.deployTerm(term)


class DeployReportWorksheetTermView(DeployReportWorksheetBaseView):
    """A view for deploying a report sheet template to a term"""

    def deploy(self):
        self.deployTerm(self.context)


class LayoutReportCardView(object):
    """A view for laying out the columns of the schoolyear's report card"""

    @property
    def columns(self):
        """Get  a list of the existing layout columns."""
        results = []
        root = IGradebookRoot(ISchoolToolApplication(None))
        schoolyearKey = self.context.__name__
        if schoolyearKey in root.layouts:
            current_columns = root.layouts[schoolyearKey].columns
        else:
            current_columns  = []
        for index, column in enumerate(current_columns):
            result = {
                'source_name': 'Column%s' % (index + 1),
                'source_value': column.source,
                'heading_name': 'Heading%s' % (index + 1),
                'heading_value': column.heading,
                }
            results.append(result)
        return results

    @property
    def outline_activities(self):
        """Get  a list of the existing layout outline activities."""
        results = []
        root = IGradebookRoot(ISchoolToolApplication(None))
        schoolyearKey = self.context.__name__
        if schoolyearKey in root.layouts:
            current_activities = root.layouts[schoolyearKey].outline_activities
        else:
            current_activities  = []
        for index, activity in enumerate(current_activities):
            result = {
                'source_name': 'Activity%s' % (index + 1),
                'source_value': activity.source,
                'heading_name': 'ActivityHeading%s' % (index + 1),
                'heading_value': activity.heading,
                }
            results.append(result)
        return results

    @property
    def column_choices(self):
        return self.choices(no_journal=False)

    @property
    def activity_choices(self):
        return self.choices(no_comment=False)

    def choices(self, no_comment=True, no_journal=True):
        """Get  a list of the possible choices for layout activities."""
        results = []
        root = IGradebookRoot(ISchoolToolApplication(None))
        for term in self.context.values():
            deployedKey = '%s_%s' % (self.context.__name__, term.__name__)
            for key in root.deployed:
                if key.startswith(deployedKey):
                    deployedWorksheet = root.deployed[key]
                    for activity in deployedWorksheet.values():
                        if ICommentScoreSystem.providedBy(activity.scoresystem):
                            if no_comment: 
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
        if not no_journal:
            result = {
                'name': ABSENT_HEADING,
                'value': ABSENT_KEY,
                }
            results.append(result)
            result = {
                'name': TARDY_HEADING,
                'value': TARDY_KEY,
                }
            results.append(result)
        return results

    def update(self):
        if 'Update' in self.request or 'OK' in self.request:
            columns = self.updatedColumns()
            outline_activities = self.updatedOutlineActivities()

            root = IGradebookRoot(ISchoolToolApplication(None))
            schoolyearKey = self.context.__name__
            if schoolyearKey not in root.layouts:
                if not len(columns):
                    return
                root.layouts[schoolyearKey] = ReportLayout()
            layout = root.layouts[schoolyearKey]
            layout.columns = columns
            layout.outline_activities = outline_activities

            if 'OK' in self.request:
                self.request.response.redirect(self.nextURL())

    def updatedColumns(self):
        columns = []
        index = 1
        while True:
            source_name = 'Column%s' % index
            heading_name = 'Heading%s' % index
            index += 1
            if source_name not in self.request:
                break
            if 'delete' in self.request:
                if source_name in self.request['delete']:
                    continue
            column = ReportColumn(self.request[source_name], 
                                  self.request[heading_name])
            columns.append(column)
        if len(self.request['new_source']):
            column = ReportColumn(self.request['new_source'], 
                                  self.request['new_heading'])
            columns.append(column)
        return columns

    def updatedOutlineActivities(self):
        activities = []
        index = 1
        while True:
            source_name = 'Activity%s' % index
            heading_name = 'ActivityHeading%s' % index
            index += 1
            if source_name not in self.request:
                break
            if 'delete' in self.request:
                if source_name in self.request['delete']:
                    continue
            column = OutlineActivity(self.request[source_name], 
                                     self.request[heading_name])
            activities.append(column)
        if len(self.request['new_activity_source']):
            column = OutlineActivity(self.request['new_activity_source'], 
                                     self.request['new_activity_heading'])
            activities.append(column)
        return activities

    def nextURL(self):
        return absoluteURL(self.context, self.request)


def handleSectionAdded(event):
    """Make sure the same worksheets are deployed to newly added sections."""

    obj = event.object
    if not ISection.providedBy(obj):
        return
    root = IGradebookRoot(ISchoolToolApplication(None))
    term = ITerm(obj)
    schoolyear = ISchoolYear(term)
    deployedKey = '%s_%s' % (schoolyear.__name__, term.__name__)
    for key in root.deployed:
        if key.startswith(deployedKey):
            deployedWorksheet = root.deployed[key]
            activities = IActivities(obj)
            worksheetCopy = Worksheet(deployedWorksheet.title)
            worksheetCopy.deployed = True
            activities[key] = worksheetCopy
            copyActivities(deployedWorksheet, worksheetCopy)

