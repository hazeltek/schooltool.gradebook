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
Course Worksheet Views
"""

from zope.container.interfaces import INameChooser
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from zope.security.checker import canWrite
from zope.security.interfaces import Unauthorized
from zope.security.proxy import removeSecurityProxy
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.i18n import translate

from z3c.form import form, field, button

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook import GradebookMessage as _
from schooltool.common.inlinept import InheritTemplate
from schooltool.common.inlinept import InlineViewPageTemplate
from schooltool.course.interfaces import ISectionContainer, ISection
from schooltool.person.interfaces import IPerson
from schooltool.schoolyear.interfaces import ISchoolYear
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.skin import flourish
from schooltool.skin.flourish.page import TertiaryNavigationManager
from schooltool.term.interfaces import ITerm

from schooltool.gradebook.interfaces import (IActivities, ICourseWorksheet,
    ICourseDeployedWorksheets)
from schooltool.gradebook.activity import CourseWorksheet, Activity
from schooltool.gradebook.browser.activity import (FlourishActivityAddView,
    FlourishActivityEditView)


class FlourishCourseSchooYearMixin(object):
    """A flourish mixin class for any course view with need of schooyear"""

    @property
    def schoolyear(self):
        return ISchoolYear(self.context)


class FlourishManageCourseSheetsOverview(FlourishCourseSchooYearMixin,
                                         flourish.page.Content):
    """A flourish viewlet for showing deployed worksheets in course view"""

    body_template = ViewPageTemplateFile(
        'templates/f_manage_course_worksheets.pt')

    def sheets(self):
        return []


class FlourishCourseTemplatesView(flourish.page.Page):
    """A flourish view for managing course worksheet templates"""

    @property
    def title(self):
        return self.context.__parent__.title

    @property
    def worksheets(self):
        return tuple(removeSecurityProxy(self.context).values())


class FlourishCourseWorksheetsLinks(flourish.page.RefineLinksViewlet):
    """flourish course worksheet templates add links viewlet."""


class FlourishCourseWorksheetAddView(flourish.form.AddForm):
    """flourish view for adding a course worksheet."""

    fields = field.Fields(ICourseWorksheet).select('title')
    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Course Worksheet Details')

    @property
    def title(self):
        return self.context.__parent__.title

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishCourseWorksheetAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        url = absoluteURL(self.context, self.request)
        self.request.response.redirect(url)

    def create(self, data):
        worksheet = CourseWorksheet(data['title'])
        return worksheet

    def add(self, worksheet):
        chooser = INameChooser(self.context)
        name = chooser.chooseName(worksheet.title, worksheet)
        self.context[name] = worksheet
        self._worksheet = worksheet
        return worksheet

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def updateActions(self):
        super(FlourishCourseWorksheetAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class FlourishCourseWorksheetEditView(flourish.form.Form, form.EditForm):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Course Worksheet Template Information')
    fields = field.Fields(ICourseWorksheet).select('title')

    @property
    def title(self):
        return self.context.title

    def update(self):
        if 'form-submitted' in self.request:
            for activity in self.context.values():
                name = 'delete.%s' % activity.__name__
                if name in self.request:
                    del self.context[activity.__name__]
                    break
        return form.EditForm.update(self)

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishCourseWorksheetEditView, self).handleApply.func(self, action)
        # XXX: hacky sucessful submit check
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            self.request.response.redirect(self.nextURL())

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def nextURL(self):
        return absoluteURL(self.context.__parent__, self.request)

    def updateActions(self):
        super(FlourishCourseWorksheetEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class CourseWorksheetAddLinks(flourish.page.RefineLinksViewlet):
    """Course worksheet add links viewlet."""


class FlourishCourseActivityAddView(FlourishActivityAddView):
    legend = _('Course Activity Details')


class CourseActivityAddTertiaryNavigationManager(
    flourish.page.TertiaryNavigationManager):

    template = InlineViewPageTemplate("")


class FlourishCourseActivityEditView(FlourishActivityEditView):
    legend = _('Course Activity Details')

    def nextURL(self):
        return absoluteURL(self.context.__parent__, self.request)


class FlourishCourseWorksheetsBase(FlourishCourseSchooYearMixin):

    @property
    def deployed(self):
        return ICourseDeployedWorksheets(self.context)

    @property
    def activities(self):
        return IActivities(self.context)

    def sheets(self):
        return [sheet for sheet in self.all_sheets() if not sheet['checked']]

    def all_sheets(self):
        schoolyear = self.schoolyear
        deployments = {}
        for sheet in self.deployed.values():
            sheet = removeSecurityProxy(sheet)
            index = int(sheet.__name__[sheet.__name__.rfind('_') + 1:])
            deployment = deployments.setdefault(index, {
                'obj': sheet,
                'index': str(index),
                'checked': sheet.hidden,
                'terms': [False] * len(schoolyear),
                })
            for index, term in enumerate(schoolyear.values()):
                if sheet.__name__.startswith(term.__name__):
                    deployment['terms'][index] = True
        sheets = [v for k, v in sorted(deployments.items())]
        return ([sheet for sheet in sheets if not sheet['checked']] +
                [sheet for sheet in sheets if sheet['checked']])


class FlourishCourseWorksheetsView(FlourishCourseWorksheetsBase,
                                   flourish.page.Page):
    """A flourish view for managing corse worksheet deployment"""

    def __init__(self, context, request):
        super(FlourishCourseWorksheetsView, self).__init__(context, request)
        self.alternate_title = self.request.get('alternate_title')

    @property
    def subtitle(self):
        subtitle = _(u'Worksheets for ${year}',
                  mapping={'year': self.schoolyear.title})
        return translate(subtitle, context=self.request)

    @property
    def has_error(self):
        return self.no_template or self.no_title

    @property
    def no_template(self):
        return 'SUBMIT' in self.request and not self.request.get('template')

    @property
    def no_title(self):
        return ('SUBMIT' in self.request and
                not self.request.get('alternate_title'))

    @property
    def terms(self):
        result = [{
            'name': '',
            'title': _('-- Entire year --'),
            'selected': 'selected',
            }]
        for term in self.schoolyear.values():
            result.append({
                'name': term.__name__,
                'title': term.title,
                'selected': '',
                })
        return result

    @property
    def templates(self):
        result = [{
            'name': '',
            'title': _('-- Select a template --'),
            'selected': 'selected',
            }]
        for template in self.activities.values():
            result.append({
                'name': template.__name__,
                'title': template.title,
                'selected': '',
                })
        return result

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        if 'SUBMIT' in self.request:
            if self.request.get('template') and self.alternate_title:
                template = self.activities[self.request['template']]
                term = self.request.get('term')
                if term:
                    term = self.schoolyear[term]
                self.deploy(term, template)
                self.alternate_title = ''

    def deploy(self, term, template):
        # get the next index and title
        highest, title_index = 0, 0
        template_title = self.alternate_title
        for sheet in self.deployed.values():
            index = int(sheet.__name__[sheet.__name__.rfind('_') + 1:])
            if index > highest:
                highest = index
            if sheet.title.startswith(template_title):
                rest = sheet.title[len(template_title):]
                if not rest:
                    new_index = 1
                elif len(rest) > 1 and rest[0] == '-' and rest[1:].isdigit():
                    new_index = int(rest[1:])
            else:
                new_index = 0
            if new_index > title_index:
                title_index = new_index

        # copy worksheet template to the term or whole year
        if term:
            terms = [term]
        else:
            terms = self.schoolyear.values()
        for term in terms:
            deployedKey = '%s_%s' % (term.__name__, highest + 1)
            title = template_title
            if title_index:
                title += '-%s' % (title_index + 1)
            deployedWorksheet = Worksheet(title)
            self.deployed[deployedKey] = deployedWorksheet
            continue
            copyActivities(template, deployedWorksheet)

            # now copy the template to all sections in the term
            sections = ISectionContainer(term)
            for section in sections.values():
                worksheetCopy = Worksheet(deployedWorksheet.title)
                worksheetCopy.deployed = True
                self.activities[deployedWorksheet.__name__] = worksheetCopy
                copyActivities(deployedWorksheet, worksheetCopy)

    def nextURL(self):
        url = absoluteURL(ISchoolToolApplication(None), self.request)
        return url + '/manage'

