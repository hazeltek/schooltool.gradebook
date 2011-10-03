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
"""Worksheet Views.

$Id$
"""

from zope.container.interfaces import INameChooser
from zope.security.checker import canWrite
from zope.security.interfaces import Unauthorized
from zope.traversing.api import getName
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.publisher.browser import BrowserView
from zope.app.form.browser.editview import EditView

from z3c.form import form, field, button

from schooltool.app.browser import app
from schooltool.common.inlinept import InheritTemplate
from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook import interfaces
from schooltool.gradebook.activity import Worksheet
from schooltool.person.interfaces import IPerson
from schooltool.skin import flourish


class WorksheetGradebookView(BrowserView):
    """A view that redirects from the worksheet to its gradebook."""

    def __init__(self, context, request):
        super(WorksheetGradebookView, self).__init__(context, request)
        url = absoluteURL(self.context, self.request) + '/gradebook'
        self.request.response.redirect(url)

    def __call__(self):
        return "Redirecting..."


class WorksheetManageView(object):
    """A Worksheet view."""

    __used_for__ = interfaces.IWorksheet
    
    def activities(self):
        pos = 0
        for activity in list(self.context.values()):
            pos += 1
            url = absoluteURL(activity, self.request)
            if interfaces.ILinkedColumnActivity.providedBy(activity):
                url += '/editLinkedColumn.html'
            yield {'name': getName(activity),
                   'title': activity.title,
                   'url': url,
                   'pos': pos,
                   'deployed': self.context.deployed}

    def isTemplate(self):
        return interfaces.IReportWorksheet.providedBy(self.context)

    def canModify(self):
        return canWrite(self.context, 'title')

    def positions(self):
        return range(1, len(self.context.values())+1)

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
            for activity in self.context.values():
                old_pos += 1
                name = getName(activity)
                if 'pos.'+name not in self.request:
                    continue
                new_pos = int(self.request['pos.'+name])
                if new_pos != old_pos:
                    self.context.changePosition(name, new_pos-1)

    @property
    def noActivitiesMessage(self):
        return _('This worksheet has no activities.')


class WorksheetAddView(app.BaseAddView):
    """A view for adding a worksheet."""

    def nextURL(self):
        #person = IPerson(self.request.principal, None)
        #self.context.context.resetCurrentWorksheet(person)
        return absoluteURL(self.context.context, self.request)


class FlourishWorksheetAddView(flourish.form.AddForm):
    """flourish view for adding a worksheet."""

    fields = field.Fields(interfaces.IWorksheet).select('title')
    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Worksheet Details')

    @button.buttonAndHandler(_('Submit'), name='add')
    def handleAdd(self, action):
        super(FlourishWorksheetAddView, self).handleAdd.func(self, action)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        person = IPerson(self.request.principal, None)
        if person is None:
            worksheet = self.context._getDefaultWorksheet()
        else:
            worksheet = self.context.getCurrentWorksheet(person)
        if worksheet is None:
            url = absoluteURL(self.context.__parent__, self.request)
        else:
            url = absoluteURL(worksheet, self.request) + '/gradebook'
        self.request.response.redirect(url)

    def create(self, data):
        self.worksheet = Worksheet(data['title'])
        return self.worksheet

    def add(self, worksheet):
        chooser = INameChooser(self.context)
        name = chooser.chooseName(worksheet.title, worksheet)
        self.context[name] = worksheet
        return worksheet

    def nextURL(self):
        return absoluteURL(self.worksheet, self.request)

    def updateActions(self):
        super(FlourishWorksheetAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class BaseEditView(EditView):
    """A base class for edit views that need special redirect."""

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        else:
            status = EditView.update(self)
            if 'UPDATE_SUBMIT' in self.request and not self.errors:
                self.request.response.redirect(self.nextURL())
            return status


class WorksheetEditView(BaseEditView):
    """A view for editing worksheet info."""

    def nextURL(self):
        return absoluteURL(self.context.__parent__, self.request)


class FlourishWorksheetEditView(flourish.form.Form, form.EditForm):

    template = InheritTemplate(flourish.page.Page.template)
    label = None
    legend = _('Worksheet Information')
    fields = field.Fields(interfaces.IWorksheet).select('title')

    @property
    def title(self):
        return self.context.title

    def update(self):
        return form.EditForm.update(self)

    @button.buttonAndHandler(_('Submit'), name='apply')
    def handleApply(self, action):
        super(FlourishWorksheetEditView, self).handleApply.func(self, action)
        # XXX: hacky sucessful submit check
        if (self.status == self.successMessage or
            self.status == self.noChangesMessage):
            url = absoluteURL(self.context.__parent__, self.request)
            self.request.response.redirect(url)

    @button.buttonAndHandler(_("Cancel"))
    def handle_cancel_action(self, action):
        url = absoluteURL(self.context.__parent__, self.request)
        self.request.response.redirect(url)

    def updateActions(self):
        super(FlourishWorksheetEditView, self).updateActions()
        self.actions['apply'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')
