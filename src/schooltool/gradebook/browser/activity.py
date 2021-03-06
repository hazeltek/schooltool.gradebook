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
"""Activity Views.
"""
from decimal import Decimal, InvalidOperation

import xlwt
from StringIO import StringIO

from zope.cachedescriptors.property import Lazy
from zope.container.interfaces import INameChooser
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.i18n import translate
from zope.i18n.interfaces.locales import ICollator
from zope.interface import implements
from zope.publisher.browser import BrowserView
import zope.schema
from zope.security.checker import canWrite
from zope.security.interfaces import Unauthorized
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.traversing.api import getName
from zope.browser.interfaces import ITerms
from zope.schema.vocabulary import SimpleTerm
from zope.security.proxy import removeSecurityProxy
from zope.component import queryAdapter, getAdapter, queryUtility
from zope.component import getUtility
from zope import interface, schema
from zope.viewlet.viewlet import ViewletBase

from z3c.form import form as z3cform
from z3c.form import field, button, widget
from z3c.form.interfaces import DISPLAY_MODE

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.basicperson.interfaces import IDemographics
from schooltool.common.inlinept import InheritTemplate
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.course.interfaces import ISection, IInstructor
from schooltool.export import export
from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import createSourceString, getSourceObj
from schooltool.gradebook.activity import Activity, LinkedColumnActivity
from schooltool.gradebook.activity import LinkedActivity
from schooltool.gradebook.activity import Worksheet
from schooltool.gradebook.gradebook import canAverage
from schooltool.person.interfaces import IPerson
from schooltool.person.interfaces import IPersonFactory
from schooltool.gradebook.browser.gradebook import LinkedActivityGradesUpdater
from schooltool.requirement.interfaces import IRangedValuesScoreSystem
from schooltool.requirement.scoresystem import RangedValuesScoreSystem
from schooltool.term.interfaces import ITerm, IDateManager
from schooltool.skin import flourish

SUMMARY_TITLE = _('Summary')


class ILinkedActivityFields(interface.Interface):

    external_activity = schema.Choice(
        title=_(u"External Activity"),
        description=_(u"The external activity"),
        vocabulary="schooltool.gradebook.external_activities",
        required=True)


class LinkedActivityFields(object):

    def __init__(self, context):
        self.context = context

    @property
    def external_activity(self):
        section = self.context.__parent__.__parent__.__parent__
        adapter = getAdapter(section, interfaces.IExternalActivities,
                             name=self.context.source)
        return (adapter,
                adapter.getExternalActivity(self.context.external_activity_id))


class ActivitiesView(object):
    """A Group Container view."""

    __used_for__ = interfaces.IActivities

    @property
    def worksheets(self):
        """Get  a list of all worksheets."""
        pos = 0
        for worksheet in self.context.values():
            pos += 1
            yield {'name': getName(worksheet),
                   'title': worksheet.title,
                   'url': absoluteURL(worksheet, self.request) + '/manage.html',
                   'pos': pos,
                   'deployed': worksheet.deployed}

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

        if 'HIDE' in self.request:
            for name in self.request.get('hide', []):
                worksheet = removeSecurityProxy(self.context[name])
                worksheet.hidden = True
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


class FlourishWorksheetsView(flourish.page.Page):
    """A flourish view of the gradebook's worksheets."""

    @property
    def title(self):
        return self.context.__parent__.title

    def positions(self):
        return range(1, len(self.context.values())+1)

    @property
    def worksheets(self):
        """Get  a list of all worksheets."""
        pos, visible, hidden = 1, [], []
        activities = removeSecurityProxy(self.context)
        for worksheet in activities.all_worksheets:
            result = {
               'name': getName(worksheet),
               'title': worksheet.title,
               'url': absoluteURL(worksheet, self.request) + '/edit.html',
               'pos': pos,
               'checked': not worksheet.hidden and 'checked' or '',
               'deployed': worksheet.deployed,
               }
            if worksheet.hidden:
                if not worksheet.deployed:
                    hidden.append(result)
            else:
                visible.append(result)
                pos += 1
        return visible + hidden

    def nextSummaryTitle(self):
        index = 1
        next = SUMMARY_TITLE
        while True:
            for worksheet in self.context.values():
                if worksheet.title == next:
                    break
            else:
                break
            index += 1
            next = SUMMARY_TITLE + str(index)
        return next

    def summaryFound(self):
        return self.nextSummaryTitle() != SUMMARY_TITLE

    def addSummary(self):
        overwrite = self.request.get('overwrite', '') == 'on'
        if overwrite:
            currentWorksheets = []
            for worksheet in self.context.values():
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
            currentWorksheets = [worksheet for worksheet in self.context.values()
                                 if not worksheet.deployed]
            summary = Worksheet(next)
            chooser = INameChooser(self.context)
            name = chooser.chooseName('', summary)
            self.context[name] = summary

        for worksheet in currentWorksheets:
            if worksheet.title.startswith(SUMMARY_TITLE):
                continue
            activity = LinkedColumnActivity(worksheet.title, u'assignment',
                '', createSourceString(worksheet))
            chooser = INameChooser(summary)
            name = chooser.chooseName('', activity)
            summary[name] = activity

    def update(self):
        if 'ADD_SUMMARY' in self.request:
            self.addSummary()

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

            visible = self.request.get('visible', [])
            activities = removeSecurityProxy(self.context)
            for worksheet in activities.all_worksheets:
                if worksheet.deployed:
                    continue
                if worksheet.hidden and worksheet.__name__ in visible:
                    worksheet.hidden = False
                elif not worksheet.hidden and worksheet.__name__ not in visible:
                    worksheet.hidden = True


class UnhideWorksheetsView(object):
    """A view for unhiding woksheets."""

    __used_for__ = interfaces.IActivities

    @property
    def worksheets(self):
        """Get  a list of all worksheets."""
        activities = removeSecurityProxy(self.context)
        for worksheet in activities.all_worksheets:
            if worksheet.hidden:
                yield {'name': getName(worksheet),
                       'title': worksheet.title}

    def canModify(self):
        return canWrite(self.context, 'title')

    def update(self):
        self.person = IPerson(self.request.principal, None)
        if self.person is None:
            raise Unauthorized("You don't have the permission to do this.")

        if 'UNHIDE' in self.request:
            for name in self.request.get('unhide', []):
                worksheet = removeSecurityProxy(self.context[name])
                worksheet.hidden = False
            self.request.response.redirect(self.nextURL())
        elif 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())

    def nextURL(self):
        return absoluteURL(self.context, self.request)


class ActivityAddView(z3cform.AddForm):
    """A view for adding an activity."""
    label = _("Add new activity")
    template = ViewPageTemplateFile('templates/add_edit_activity.pt')

    fields = field.Fields(interfaces.IActivity)
    fields = fields.select('title', 'label', 'due_date', 'description',
                           'category')
    fields += field.Fields(IRangedValuesScoreSystem).select('min', 'max')

    def updateActions(self):
        super(ActivityAddView, self).updateActions()
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
        scoresystem = RangedValuesScoreSystem(
            u'generated', min=data['min'], max=data['max'])
        activity = Activity(data['title'], data['category'], scoresystem,
                            data['description'], data['label'],
                            data.get('due_date'))
        return activity

    def add(self, activity):
        """Add activity to the worksheet."""
        chooser = INameChooser(self.context)
        name = chooser.chooseName('', activity)
        self.context[name] = activity
        return activity

    def nextURL(self):
        return absoluteURL(self.context, self.request)


class IActivityForm(interface.Interface):
    '''An interface used to build flourish activity forms'''

    title = zope.schema.TextLine(
        title=_(u"Title"),
        description=u'',
        required=True)

    label = zope.schema.TextLine(
        title=_(u"Column Label"),
        description=_("Limit to 5 characters or less."),
        required=False)

    due_date = zope.schema.Date(
        title=_("Due Date"),
        required=True)

    description = zope.schema.Text(
        title=_("Description"),
        required=False)

    category = zope.schema.Choice(
        title=_("Category"),
        description=_("Categories can be used to weigh different types of "
                      "activites differently when calculating averages.  The "
                      "list of categories can be set schoolwide set by your "
                      "system administrator."),
        vocabulary="schooltool.gradebook.category-vocabulary",
        required=True)

    max = zope.schema.Int(
        title=_(u'Full Credit Score'),
        description=_("This value must be an integer.  You may award extra "
                      "credit above this value."),
        required=True,
        default=100)

    min = zope.schema.Int(
        title=_(u'Minimum Score'),
        description=_('This value must be an integer.'),
        required=True,
        default=0)


class SimpleFormAdapter(object):

    def __init__(self, context):
        self.__dict__['context'] = removeSecurityProxy(context)

    def __setattr__(self, name, value):
        setattr(self.context, name, value)

    def __getattr__(self, name):
        return getattr(self.context, name)


class FlourishActivityAddView(flourish.form.AddForm, ActivityAddView):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Activity Details')

    fields = field.Fields(IActivityForm)

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishActivityAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        super(FlourishActivityAddView, self).handle_cancel_action.func(self,
            action)


class LinkedActivityAddView(z3cform.AddForm):
    """A view for adding a linked activity."""

    label = _(u"Add an External Activity")
    template = ViewPageTemplateFile('templates/add_edit_activity.pt')

    fields = field.Fields(ILinkedActivityFields,
                          interfaces.ILinkedActivity)
    fields = fields.select("external_activity", "label", "due_date",
                           "category", "points")

    def updateActions(self):
        super(LinkedActivityAddView, self).updateActions()
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
        external_activity = data.get("external_activity")[1]
        category = data.get("category")
        points = data.get("points")
        label = data.get("label")
        due_date = data.get("due_date")
        return LinkedActivity(external_activity, category, points,
                              label, due_date)

    def add(self, activity):
        """Add activity to the worksheet."""
        chooser = INameChooser(self.context)
        name = chooser.chooseName('', activity)
        self.context[name] = activity
        self.updateGrades(activity)
        return activity

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def updateGrades(self, linked_activity):
        LinkedActivityGradesUpdater().update(linked_activity, self.request)


class ILinkedActivityExternalActivity(interface.Interface):

    external_activity = schema.Choice(
        title=_(u"External Score Source"),
        vocabulary="schooltool.gradebook.external_activities",
        required=True)


class ILinkedActivityForm(IActivityForm):
    '''An interface used to build flourish external activity forms'''

    points = zope.schema.Int(
        title=_(u"Full Credit Score"),
        description=_("The point value of this activity will be calculated as "
                      "the full credit score multiplied by the percentage "
                      "value of the external score."),
        min=0,
        required=True,
        default=100)


class FlourishLinkedActivityAddView(flourish.form.AddForm,
                                    LinkedActivityAddView):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('External Score Details')

    fields = field.Fields(ILinkedActivityExternalActivity, ILinkedActivityForm)
    fields = fields.select("external_activity", "label", "due_date",
                           "category", "points")

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishLinkedActivityAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        super(FlourishLinkedActivityAddView, self).handle_cancel_action.func(
            self, action)


class ActivityEditView(z3cform.EditForm):
    """Edit form for basic person."""
    z3cform.extends(z3cform.EditForm)
    template = ViewPageTemplateFile('templates/add_edit_activity.pt')

    fields = field.Fields(interfaces.IActivity)
    fields = fields.select('title', 'label', 'due_date', 'description',
                           'category')

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def updateActions(self):
        super(ActivityEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    def applyChanges(self, data):
        super(ActivityEditView, self).applyChanges(data)
        self.request.response.redirect(self.nextURL())

    @property
    def label(self):
        return _(u'Change information for ${fullname}',
                 mapping={'fullname': self.context.title})

    def nextURL(self):
        next = self.request.get('nexturl')
        if next:
            return next
        worksheet = self.context.__parent__
        return absoluteURL(worksheet, self.request) + '/manage.html'


class FlourishActivityEditView(flourish.form.Form,
                               ActivityEditView):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Activity Details')

    fields = field.Fields(IActivityForm).omit('max', 'min')

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishActivityEditView, self).handleApply.func(self, action)
        # XXX: hacky sucessful submit check
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            self.request.response.redirect(self.nextURL())

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def nextURL(self):
        next = self.request.get('nexturl')
        if next:
            return next
        worksheet = self.context.__parent__
        return absoluteURL(worksheet, self.request) + '/gradebook'


class LinkedActivityEditView(z3cform.EditForm):
    """Edit form for linked activity."""

    z3cform.extends(z3cform.EditForm)
    template = ViewPageTemplateFile('templates/add_edit_activity.pt')
    label = _(u'Edit External Activity')

    fields = field.Fields(ILinkedActivityFields, mode=DISPLAY_MODE)
    fields += field.Fields(interfaces.ILinkedActivity)
    fields = fields.select("external_activity", "title", 'label',
                           'due_date', "description", "category",
                           "points")

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def updateActions(self):
        super(LinkedActivityEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

    def applyChanges(self, data):
        super(LinkedActivityEditView, self).applyChanges(data)
        self.request.response.redirect(self.nextURL())

    def nextURL(self):
        worksheet = self.context.__parent__
        return absoluteURL(worksheet, self.request)


class FlourishLinkedActivityEditView(flourish.form.Form,
                                     LinkedActivityEditView):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('External Score Details')

    fields = field.Fields(ILinkedActivityExternalActivity, mode=DISPLAY_MODE)
    fields += field.Fields(ILinkedActivityForm)
    fields = fields.select("external_activity", "title", 'label',
                           'due_date', "description", "category",
                           "points")

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishLinkedActivityEditView, self).handleApply.func(self, action)
        # XXX: hacky sucessful submit check
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            self.request.response.redirect(self.nextURL())

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())


class WeightCategoriesView(object):
    """A view for providing category weights for the worksheet context."""

    def title(self):
        return _('Category weights for worksheet ${worksheet}',
                 mapping={'worksheet': self.context.title})

    def nextURL(self):
        section = self.context.__parent__.__parent__
        return absoluteURL(section, self.request) + '/gradebook'

    def update(self):
        self.message = ''
        categories = interfaces.ICategoryContainer(ISchoolToolApplication(None))
        newValues = {}
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        elif 'UPDATE_SUBMIT' in self.request:
            for category in sorted(categories.keys()):
                if category in self.request and self.request[category].strip():
                    value = self.request[category].strip()
                    try:
                        value = Decimal(value)
                        if value < 0 or value > 100:
                            raise ValueError
                    except (InvalidOperation, ValueError):
                        self.message = _('$value is not a valid weight.',
                            mapping={'value': value})
                        break
                else:
                    value = None
                newValues[category] = value
            else:
                for category, value in newValues.items():
                    if value is not None:
                        value = value / 100
                    self.context.setCategoryWeight(category, value)
                self.request.response.redirect(self.nextURL())

    def rows(self):
        weights = self.context.getCategoryWeights()
        categories = interfaces.ICategoryContainer(ISchoolToolApplication(None))
        result = []
        for category in sorted(categories.keys()):
            if category in self.request:
                weight = self.request[category]
            else:
                weight = weights.get(category)
                if weight is not None:
                    weight = unicode(weights.get(category) * 100)
                    if '.' in weight:
                        while weight.endswith('0'):
                            weight = weight[:-1]
                        if weight[-1] == '.':
                            weight = weight[:-1]
            row = {
                'category': category,
                'category_value': categories[category],
                'weight': weight,
                }
            result.append(row)
        return result


class FlourishWeightCategoriesView(WeightCategoriesView, flourish.page.Page):
    """A flourish view for providing category weights for the worksheet."""


class ExternalActivitiesTerms(object):
    """Terms for external activities"""

    implements(ITerms)

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def getTerm(self, value):
        try:
            adapter = value[0]
            external_activity = value[1]
            title = "%s - %s" % (adapter.title, external_activity.title)
            token = "%s-%s" % (external_activity.source,
                             external_activity.external_activity_id)
            return SimpleTerm(value=value, title=title, token=token)
        except (AttributeError, IndexError,):
            return SimpleTerm(value=None,
                              title=_(u"The external activity couldn't be"
                                      u" found"), token="")

    def getValue(self, token):
        source = token.split("-")[0]
        external_activity_id = token.split("-")[-1]
        adapter = queryAdapter(self.context.section,
                               interfaces.IExternalActivities,
                               name=source)
        if adapter is not None and \
           adapter.getExternalActivity(external_activity_id) is not None:
            external_activity = adapter.getExternalActivity(external_activity_id)
            external_activity.source = adapter.source
            external_activity.external_activity_id = external_activity_id
            return (adapter, external_activity)
        raise LookupError(token)


class UpdateGradesActionMenuViewlet(ViewletBase):
    """Viewlet for hiding update grades button for broken linked activities"""

    def external_activity_exists(self):
        return self.context.getExternalActivity() is not None


class WorksheetsExportView(export.ExcelExportView):
    """A view for exporting worksheets to a XLS file"""

    @Lazy
    def name_sorting_columns(self):
        return getUtility(IPersonFactory).columns()

    @property
    def base_filename(self):
        section = self.context.__parent__
        activities = self.context
        filename = '%s %s' % (section.title, activities.title)
        filename = filename.replace(' ', '_')
        return filename

    def print_headers(self, ws, worksheet):
        row = 2
        gradebook = interfaces.IGradebook(worksheet)
        activities = gradebook.getWorksheetActivities(worksheet)
        header_labels = ['ID']
        for column in self.name_sorting_columns:
            header_labels.append(column.title)
        header_labels.extend([activity.title for activity in activities])
        headers = [export.Header(label) for label in header_labels]
        for col, header in enumerate(headers):
            self.write(ws, row, col, header.data, **header.style)

    def print_grades(self, ws, worksheet):
        gradebook = interfaces.IGradebook(worksheet)
        activities = gradebook.getWorksheetActivities(worksheet)
        starting_row = 3
        collator = ICollator(self.request.locale)
        factory = getUtility(IPersonFactory)
        sorting_key = lambda x: factory.getSortingKey(x, collator)
        students = sorted(gradebook.students, key=sorting_key)
        for row, student in enumerate(students):
            cells = [export.Text(IDemographics(student).get('ID', ''))]
            for column in self.name_sorting_columns:
                cells.append(export.Text(getattr(student, column.name)))
            for activity in activities:
                score = gradebook.getScore(student, activity)
                if not score:
                    value = ''
                else:
                    value = score.value
                cells.append(export.Text(value))
            for col, cell in enumerate(cells):
                self.write(ws, starting_row+row, col, cell.data, **cell.style)

    def print_worksheet_header(self, ws, worksheet):
        row = 0
        headers = [export.Header('Worksheet'),
                   export.Text(worksheet.title)]
        for col, header in enumerate(headers):
            self.write(ws, row, col, header.data, **header.style)

    def export_worksheets(self, wb):
        self.task_progress.force('worksheets', active=True)
        documents = self.context.values()
        for i, worksheet in enumerate(documents):
            ws = wb.add_sheet(str(i+1))
            self.print_worksheet_header(ws, worksheet)
            self.print_headers(ws, worksheet)
            self.print_grades(ws, worksheet)
            
            self.progress('worksheets', export.normalized_progress(
                    i, len(documents)))
        self.finish('worksheets')

    def addImporters(self, progress):
        progress.add('worksheets', 
                     title=_('Worksheets'), progress=0.0)

    def render(self, workbook):
        datafile = StringIO()
        workbook.save(datafile)
        data = datafile.getvalue()
        self.setUpHeaders(data)
        return data

    def __call__(self):
        self.makeProgress()
        self.task_progress.title = _("Exporting worksheets")
        self.addImporters(self.task_progress)

        wb = xlwt.Workbook()
        self.export_worksheets(wb)

        self.task_progress.title = _("Export complete")
        return wb


class LinkedColumnBase(BrowserView):
    """Base class for add/edit linked column views"""
    def __init__(self, context, request):
        super(LinkedColumnBase, self).__init__(context, request)
        self.addForm = True
        if interfaces.IActivityWorksheet.providedBy(self.context):
            self.currentWorksheet = self.context
        else:
            self.currentWorksheet = self.context.__parent__
            self.addForm = False
        self.person = IPerson(self.request.principal)

    def title(self):
        if interfaces.IActivityWorksheet.providedBy(self.context):
            return ''
        else:
            return self.context.title

    def label(self):
        if interfaces.IActivityWorksheet.providedBy(self.context):
            return ''
        else:
            return self.context.label

    def getCategories(self):
        categories = interfaces.ICategoryContainer(ISchoolToolApplication(None))

        results = []
        if self.addForm:
            default_category = defaultCategory(None)
        else:
            default_category = self.context.category
        for category in sorted(categories.keys()):
            result = {
                'name': category,
                'value': categories[category],
                'selected': category == default_category and 'selected' or None,
                }
            results.append(result)
        return results

    def isLinked(self, activity):
        return interfaces.ILinkedColumnActivity.providedBy(activity)

    def getRows(self):
        term_dict = {}
        for section in IInstructor(self.person).sections():
            term = ITerm(section)
            term_dict.setdefault(term, []).append(section)
        results = []
        for term in sorted(term_dict.keys(), key=lambda t: t.first):
            term_disp = term.title
            for section_index, section in enumerate(term_dict[term]):
                section_disp = section.title
                worksheets = interfaces.IActivities(section).values()
                worksheets = [worksheet for worksheet in worksheets
                              if not worksheet.deployed
                              and len(worksheet.values())
                              and worksheet != self.currentWorksheet]
                for ws_index, worksheet in enumerate(worksheets):
                    ws_disp = worksheet.title
                    activities = [activity for activity in worksheet.values()
                                  if not self.isLinked(activity)]
                    for act_index, activity in enumerate(activities):
                        result = {
                            'term': term_disp,
                            'section': section_disp,
                            'worksheet': ws_disp,
                            'activity_name': createSourceString(activity),
                            'activity_value': activity.title,
                            }
                        results.append(result)
                        term_disp = section_disp = ws_disp = ''
                    if len(activities) and canAverage(worksheet,
                                                      self.currentWorksheet):
                        result = {
                            'term': '',
                            'section': '',
                            'worksheet': '',
                            'activity_name': createSourceString(worksheet),
                            'activity_value': _('Average'),
                            }
                        results.append(result)
        return results

    def getRequestSource(self):
        for key in self.request:
            parts = key.split('_')
            if len(parts) > 3:
                try:
                    sourceObj = getSourceObj(key)
                    if sourceObj is not None:
                        return key
                except:
                    pass
        return None

    def buildUpdateTarget(self, target=None):
        title = self.request['title']
        label = self.request['label']
        category = self.request['category']
        source = self.getRequestSource()
        if not title:
            sourceObj = getSourceObj(source)
            if sourceObj is not None:
                title = sourceObj.title
        if target is None:
            return LinkedColumnActivity(title, category, label, source)
        else:
            target.title = title
            target.label = label
            target.category = category
            target.source = source


class AddLinkedColumnView(LinkedColumnBase):
    """View for adding a linked column to the gradebook"""

    def viewTitle(self):
        return _('Add Linked Column')

    def actionURL(self):
        return absoluteURL(self.context, self.request) + '/addLinkedColumn.html'

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def update(self):
        if 'form-submitted' not in self.request:
            return
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        else:
            activity = self.buildUpdateTarget()
            chooser = INameChooser(self.context)
            name = chooser.chooseName('', activity)
            self.context[name] = activity
            self.request.response.redirect(self.nextURL())


class FlourishLinkedColumnAddView(flourish.page.Page, AddLinkedColumnView):
    """flourish view for adding a linked column to the gradebook"""

    def object_title(self):
        return LinkedColumnBase.title(self)

    def object_label(self):
        return LinkedColumnBase.label(self)

    def update(self):
        AddLinkedColumnView.update(self)


class EditLinkedColumnView(LinkedColumnBase):
    """View for editing a linked column in the gradebook"""

    def viewTitle(self):
        sourceObj = getSourceObj(self.context.source)
        if sourceObj is None:
            details = ''
        else:
            if interfaces.IActivityWorksheet.providedBy(sourceObj):
                act_disp = _('Average')
                worksheet = sourceObj
            else:
                act_disp = sourceObj.title
                worksheet = sourceObj.__parent__
            section = ISection(worksheet)
            term = ITerm(section)
        details = ' (%s - %s - %s - %s)' % (term.title,
            list(section.courses)[0].title, worksheet.title, act_disp)
        return _('Edit Linked Column') + details

    def actionURL(self):
        return absoluteURL(self.context, self.request) + '/editLinkedColumn.html'

    def nextURL(self):
        return absoluteURL(self.context.__parent__, self.request)

    def update(self):
        if 'form-submitted' not in self.request:
            return
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        else:
            self.buildUpdateTarget(self.context)
            self.request.response.redirect(self.nextURL())


class FlourishEditLinkedColumnView(flourish.page.Page, EditLinkedColumnView):
    """flourish view for adding a linked column to the gradebook"""

    def object_title(self):
        return LinkedColumnBase.title(self)

    def object_label(self):
        return LinkedColumnBase.label(self)

    def actionURL(self):
        return absoluteURL(self.context, self.request) + '/edit.html'

    def update(self):
        EditLinkedColumnView.update(self)


def defaultCategory(adapter):
    categories = interfaces.ICategoryContainer(ISchoolToolApplication(None))
    return categories.default_key


ActivityDefaultCategory = widget.ComputedWidgetAttribute(
    defaultCategory,
    field=interfaces.IActivity['category']
    )


ActivityFormDefaultCategory = widget.ComputedWidgetAttribute(
    defaultCategory,
    field=IActivityForm['category']
    )


def defaultDueDate(adapter):
    today = queryUtility(IDateManager).today
    return today


ActivityDefaultDueDate = widget.ComputedWidgetAttribute(
    defaultDueDate,
    field=interfaces.IActivity['due_date']
    )


ActivityFormDefaultDueDate = widget.ComputedWidgetAttribute(
    defaultDueDate,
    field=IActivityForm['due_date']
    )


class ActivityAddTertiaryNavigationManager(flourish.page.TertiaryNavigationManager):

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
        path = self.request['PATH_INFO']
        current = path[path.rfind('/')+1:]
        actions = [
            ('addActivity.html', _('Activity')),
            ('addLinkedColumn.html', _('Linked Column')),
            ('addLinkedActivity.html', _('External Score')),
            ]
        for action, title in actions:
            url = '%s/%s' % (absoluteURL(self.context, self.request), action)
            title = translate(title, context=self.request)
            result.append({
                'class': action == current and 'active' or None,
                'viewlet': u'<a href="%s">%s</a>' % (url, title),
                })
        return result

