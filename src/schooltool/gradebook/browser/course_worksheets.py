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

from schooltool.gradebook.interfaces import IActivities, IWorksheet
from schooltool.gradebook.activity import Worksheet, Activity


class FlourishManageCourseSheetsOverview(flourish.page.Content):
    """A flourish viewlet for showing deployed worksheets in course view"""

    body_template = ViewPageTemplateFile(
        'templates/f_manage_course_worksheets.pt')

    @property
    def schoolyear(self):
        return ISchoolYear(self.context)

    def sheets(self):
        return []


class FlourishCourseTemplatesView(flourish.page.Page):
    """A flourish view for managing course worksheet templates"""

    @property
    def worksheets(self):
        return IActivities(self.context).values()


class FlourishCourseWorksheetsLinks(flourish.page.RefineLinksViewlet):
    """flourish course worksheet templates add links viewlet."""


class FlourishCourseWorksheetAddView(flourish.form.AddForm):
    """flourish view for adding a course worksheet."""

    fields = field.Fields(IWorksheet).select('title')
    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Course Worksheet Details')

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishCourseWorksheetAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        url = absoluteURL(self.context, self.request)
        self.request.response.redirect(url)

    def create(self, data):
        worksheet = Worksheet(data['title'])
        return worksheet

    def add(self, worksheet):
        activities = IActivities(self.context)
        chooser = INameChooser(activities)
        name = chooser.chooseName(worksheet.title, worksheet)
        activities[name] = worksheet
        self._worksheet = worksheet
        return worksheet

    def nextURL(self):
        url = absoluteURL(self.context, self.request)
        return url + '/worksheet_templates.html'

    def updateActions(self):
        super(FlourishCourseWorksheetAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')

