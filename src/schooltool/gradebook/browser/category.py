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
"""Category Views

$Id$
"""
__docformat__ = 'reStructuredText'

import urllib

import zope.interface
import zope.component
import zope.schema
from zope.security.proxy import removeSecurityProxy
from zope.app.form import utility
from zope.formlib.interfaces import IInputWidget
from zope.traversing.browser import absoluteURL
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.publisher.browser import BrowserView
from zope.traversing.browser.interfaces import IAbsoluteURL
from z3c.form import field, button, form
from z3c.form.interfaces import HIDDEN_MODE

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.table.table import simple_form_key
from schooltool.gradebook import GradebookMessage as _
from schooltool.gradebook.interfaces import ICategoryContainer
from schooltool.skin import flourish


def getKey(name):
    name = name.replace(' ', '')
    name = name.lower()
    return name.encode('utf-8').encode('punycode')


class ICategoriesForm(zope.interface.Interface):
    """Schema for the form."""

    categories = zope.schema.Set(
        title=_('Categories'),
        value_type=zope.schema.Choice(
            vocabulary="schooltool.gradebook.category-vocabulary")
        )

    newCategory = zope.schema.TextLine(
        title=_("New Category"),
        required=False)

    defaultCategory = zope.schema.Choice(
        title=_("Default Category"),
        vocabulary="schooltool.gradebook.category-vocabulary")


class CategoryOverview(object):

    message = None

    def __init__(self, context, request):
        self.categories = ICategoryContainer(ISchoolToolApplication(None))
        super(CategoryOverview, self).__init__(context, request)

    def getData(self):
        return {'categories': [],
                'newCategory': '',
                'defaultCategory': self.categories.default_key}

    def update(self):
        if 'REMOVE' in self.request:
            keys = utility.getWidgetsData(
                self, ICategoriesForm, names=['categories'])['categories']
            if not keys:
                return
            for key in keys:
                del self.categories[key]
            self.message = _('Categories successfully deleted.')

        elif 'ADD' in self.request:
            value = utility.getWidgetsData(
                self, ICategoriesForm, names=['newCategory'])['newCategory']
            if not value:
                return
            name = unicode(value).encode('punycode')
            self.categories[name] = value
            self.message = _('Category successfully added.')

        elif 'CHANGE' in self.request:
            key = utility.getWidgetsData(self, ICategoriesForm,
                names=['defaultCategory'])['defaultCategory']
            self.categories.default_key = key
            self.message = _('Default category successfully changed.')

        utility.setUpWidgets(
            self, self.schema, IInputWidget, initial=self.getData(),
            ignoreStickyValues=True, names=self.fieldNames)


class CategoryContainerAbsoluteURLAdapter(BrowserView):

    zope.component.adapts(ICategoryContainer, IBrowserRequest)
    zope.interface.implements(IAbsoluteURL)

    def __str__(self):
        app = ISchoolToolApplication(None)
        url = str(zope.component.getMultiAdapter(
                (app, self.request), name='absolute_url'))
        return url + '/activity_categories'

    __call__ = __str__


class CategoriesAddLinks(flourish.page.RefineLinksViewlet):
    """Manager for Add links."""


class ICategoryForm(zope.interface.Interface):

    title = zope.schema.TextLine(
        title=_(u'Title'),
        required=True)


class FlourishCategoryAddView(flourish.form.AddForm):
    legend = _('Category')
    fields = field.Fields(ICategoryForm)

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    @button.buttonAndHandler(_('Add'))
    def handle_add_action(self, action):
        flourish.form.AddForm.handleAdd.func(self, action)

    @button.buttonAndHandler(_('Cancel'))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def create(self, data):
        return data['title']

    def add(self, title):
        key = unicode(title).encode('punycode')
        self.context[key] = title

    def updateActions(self):
        super(FlourishCategoryAddView, self).updateActions()
        self.actions['add'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class ICategoryEditForm(ICategoryForm):

    title = zope.schema.TextLine(
        title=_(u'Title'),
        required=True)

    category = zope.schema.TextLine(
        title=_(u'Category'),
        required=True)


class FlourishCategoryEditView(flourish.form.Form, form.EditForm):
    legend = _('Category')
    fields = field.Fields(ICategoryEditForm)
    data = None

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    @button.buttonAndHandler(_('Submit'), name='submit')
    def handleSubmit(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        changes = self.applyChanges(data)
        category = self.data['category']
        if (changes and category and
            category in self.context):

            # XXX: stupid Zope.
            del self.context[category]

            self.context[category] = self.data['title']
            self.status = self.successMessage
        else:
            self.status = self.noChangesMessage
        self.request.response.redirect(self.nextURL())

    @button.buttonAndHandler(_('Make Default'), name='make_default')
    def handleMakeDefault(self, action):
        data, errors = self.extractData()
        category = data['category']
        if (category and category in self.context):
            self.context.default_key = category
        self.request.response.redirect(self.nextURL())

    @button.buttonAndHandler(_('Cancel'))
    def handle_cancel_action(self, action):
        self.request.response.redirect(self.nextURL())

    def getContent(self):
        return self.data

    def update(self):
        self.data = {}
        self.data['category'] = self.request.get('category', '')
        if self.data['category']:
            self.data['title'] = removeSecurityProxy(
                self.context.get(self.data['category']))
            if self.context.default_key == self.data['category']:
                self.data['default'] = True
        else:
            self.data['title'] = None
        super(FlourishCategoryEditView, self).update()
        self.widgets['category'].mode = HIDDEN_MODE

    def updateActions(self):
        super(FlourishCategoryEditView, self).updateActions()
        self.actions['submit'].addClass('button-ok')
        self.actions['make_default'].addClass('button-ok')
        self.actions['cancel'].addClass('button-cancel')


class FlourishCategoriesView(flourish.page.Page):

    def table(self):
        result = []
        for key, category in sorted(self.context.items()):
            result.append({
               'key': key,
               'form_key': urllib.quote(key),
               'title': removeSecurityProxy(category),
               })
        return result

    def update(self):
        deleted = False
        for key in list(self.context):
            delete_url = 'delete.%s' % urllib.quote(key)
            if delete_url in self.request:
                del self.context[key]
                deleted = True
        if deleted:
            self.request.response.redirect(self.request.URL)


def appTitleContentFactory(context, request, view, name):
    app = ISchoolToolApplication(None)
    return flourish.content.queryContentProvider(
        app, request, view, 'title')
