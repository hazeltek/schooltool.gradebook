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

from schooltool.gradebook.interfaces import (IActivities, ICourseActivities,
     ICourseWorksheet, ICourseDeployedWorksheets, IGradebookRoot)
from schooltool.gradebook.activity import CourseWorksheet, Activity, Worksheet
from schooltool.gradebook.browser.activity import (FlourishActivityAddView,
    FlourishActivityEditView)
from schooltool.gradebook.browser.report_card import copyActivities


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
        return absoluteURL(self._worksheet, self.request)

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


class FlourishCourseWorksheetsBase(object):

    @property
    def course(self):
        return self.context

    @property
    def schoolyear(self):
        return ISchoolYear(self.course)

    def deployed(self, course):
        return ICourseDeployedWorksheets(course)

    def activities(self, course):
        return ICourseActivities(course)

    def sheets(self):
        return [sheet for sheet in self.all_sheets() if sheet['checked']]

    def all_sheets(self):
        schoolyear = self.schoolyear
        deployments = {}
        for nm, sheet in self.deployed(self.course).items():
            sheet = removeSecurityProxy(sheet)
            index = int(sheet.__name__[sheet.__name__.rfind('_') + 1:])
            deployment = deployments.setdefault(index, {
                'obj': sheet,
                'index': str(index),
                'checked': not sheet.hidden,
                'terms': [False] * len(schoolyear),
                })
            for index, term in enumerate(schoolyear.values()):
                prefix = 'course_%s_%s' % (self.course.__name__, term.__name__)
                if sheet.__name__.startswith(prefix):
                    deployment['terms'][index] = True
        sheets = [v for k, v in sorted(deployments.items())]
        return ([sheet for sheet in sheets if sheet['checked']] +
                [sheet for sheet in sheets if not sheet['checked']])

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

    def getNewIndex(self, sheet, template_title):
        if sheet.title.startswith(template_title):
            rest = sheet.title[len(template_title):]
            if not rest:
                return 1
            elif len(rest) > 1 and rest[0] == '-' and rest[1:].isdigit():
                return int(rest[1:])
        return 0

    def deploy(self, course, term, template):
        # get the next index and title
        highest, title_index = 0, 0
        template_title = self.alternate_title
        for sheet in self.deployed(course).values():
            index = int(sheet.__name__[sheet.__name__.rfind('_') + 1:])
            if index > highest:
                highest = index
            new_index = self.getNewIndex(sheet, template_title)
            if new_index > title_index:
                title_index = new_index
        root = IGradebookRoot(ISchoolToolApplication(None))
        prefix = self.schoolyear.__name__ + '_'
        for sheet in root.deployed.values():
            if sheet.__name__.startswith(prefix):
                new_index = self.getNewIndex(sheet, template_title)
                if new_index > title_index:
                    title_index = new_index
        title = template_title
        if title_index:
            title += '-%s' % (title_index + 1)

        # copy worksheet template to the term or whole year
        if term:
            terms = [term]
        else:
            terms = self.schoolyear.values()
        for term in terms:
            deployedKey = 'course_%s_%s_%s' % (course.__name__,
                                               term.__name__, highest + 1)
            deployedWorksheet = Worksheet(title)
            self.deployed(course)[deployedKey] = deployedWorksheet
            copyActivities(removeSecurityProxy(template), deployedWorksheet)

            # now copy the template to all sections in the term
            sections = ISectionContainer(term)
            for section in sections.values():
                if course not in section.courses:
                    continue
                worksheetCopy = Worksheet(deployedWorksheet.title)
                worksheetCopy.deployed = True
                IActivities(section)[deployedWorksheet.__name__] = worksheetCopy
                copyActivities(deployedWorksheet, worksheetCopy)


class FlourishManageCourseWorksheetTemplatesOverview(flourish.page.Content):
    """A flourish viewlet for showing worksheet templates in course view"""

    body_template = ViewPageTemplateFile(
        'templates/f_manage_course_worksheet_templates.pt')


class FlourishManageCourseSheetsOverview(FlourishCourseWorksheetsBase,
                                         flourish.page.Content):
    """A flourish viewlet for showing deployed worksheets in course view"""

    body_template = ViewPageTemplateFile(
        'templates/f_manage_course_worksheets.pt')


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
    def templates(self):
        result = [{
            'name': '',
            'title': _('-- Select a template --'),
            'selected': 'selected',
            }]
        for template in self.activities(self.course).values():
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
                activities = self.activities(self.course)
                template = activities[self.request['template']]
                term = self.request.get('term')
                if term:
                    term = self.schoolyear[term]
                self.deploy(self.course, term, template)
                self.alternate_title = ''

    def nextURL(self):
        return absoluteURL(self.context, self.request)


class CourseWorksheetsActionLinks(flourish.page.RefineLinksViewlet):
    """Course worksheets view action links viewlet."""


class FlourishHideUnhideCourseWorkheetsView(FlourishCourseWorksheetsBase,
                                            flourish.page.Page):
    """A flourish view for hiding/unhiding course worksheet deployments"""

    @property
    def subtitle(self):
        title = _(u'Hide/unhide Deployed Worksheets for ${year}',
                  mapping={'year': self.schoolyear.title})
        return translate(title, context=self.request)

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        elif 'SUBMIT' in self.request:
            visible = self.request.get('visible', [])
            schoolyear = self.schoolyear
            for nm, sheet in self.deployed(self.course).items():
                sheet = removeSecurityProxy(sheet)
                index = sheet.__name__[sheet.__name__.rfind('_') + 1:]
                self.handleSheet(sheet, index, visible)
            self.request.response.redirect(self.nextURL())

    def handleSheet(self, sheet, index, visible):
        if index not in visible and not sheet.hidden:
            sheet.hidden = True
        elif index in visible and sheet.hidden:
            sheet.hidden = False
        else:
            return
        schoolyear = self.schoolyear
        for term in schoolyear.values():
            deployedKey = 'course_%s_%s_%s' % (self.context.__name__,
                                               term.__name__, index)
            if sheet.__name__ == deployedKey:
                for section in ISectionContainer(term).values():
                    if self.context not in section.courses:
                        continue
                    activities = IActivities(section)
                    activities[deployedKey].hidden = sheet.hidden
                return

    def nextURL(self):
        url = absoluteURL(self.context, self.request)
        return url + '/deployed_worksheets.html'


class DeployAsCourseWorksheetLinkViewlet(flourish.page.LinkViewlet):

    @property
    def enabled(self):
        gradebook = removeSecurityProxy(self.context)
        worksheet = gradebook.context
        if worksheet.hidden:
            return False
        courses = list(ISection(gradebook).courses)
        if not courses:
            return False
        for course in courses:
            if not flourish.canEdit(course):
                return False
        return super(DeployAsCourseWorksheetLinkViewlet, self).enabled


class FlourishDeployAsCourseWorksheetView(FlourishCourseWorksheetsBase,
                                          flourish.page.Page):
    """A flourish view for deploying current gradebook worksheet as a
       course worksheet.  If form data is valid, it creates a course
       worksheet template as a copy of the context and then deploys that
       to the course for the given term.."""

    @property
    def schoolyear(self):
        return ISchoolYear(ISection(self.context))

    @property
    def courses(self):
        courses = []
        request_courses = self.request.get('courses', [])
        for course in ISection(self.context).courses:
            if not flourish.canEdit(course):
                continue
            checked = ('SUBMIT' not in self.request or
                       course.__name__ in request_courses)
            courses.append({
                'name': course.__name__,
                'title': course.title,
                'checked':  checked and 'checked' or '',
                'obj': course,
                })
        return courses

    @property
    def request_courses(self):
        course_names = [course['name'] for course in self.courses]
        if len(course_names) < 2:
            return course_names
        return [course for course in self.request.get('courses', [])
                if course in course_names]

    @property
    def has_error(self):
        return self.no_course or self.no_title

    @property
    def no_course(self):
        return ('SUBMIT' in self.request and self.courses
                and not self.request_courses)

    @property
    def no_title(self):
        return 'SUBMIT' in self.request and not self.alternate_title

    @property
    def alternate_title(self):
        if 'alternate_title' in self.request:
            return self.request['alternate_title']
        return self.context.title

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        if 'SUBMIT' in self.request:
            if not self.has_error:
                request_courses = self.request_courses
                term = self.request.get('term')
                if term:
                    term = self.schoolyear[term]
                for course_dict in self.courses:
                    course = course_dict['obj']
                    if course.__name__ not in request_courses:
                        continue
                    template = Worksheet(self.alternate_title)
                    activities = self.activities(course)
                    chooser = INameChooser(activities)
                    name = chooser.chooseName(template.title, template)
                    activities[name] = template
                    copyActivities(removeSecurityProxy(self.context), template)
                    self.deploy(course, term, template)
                self.request.response.redirect(self.nextURL())

    def nextURL(self):
        return absoluteURL(self.context, self.request) + '/gradebook'

