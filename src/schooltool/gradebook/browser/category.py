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
import zope.schema
from zope.app.form import utility
from zope.formlib.interfaces import IInputWidget

from schooltool.gradebook import GradebookMessage as _
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook.interfaces import ICategoryContainer


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
            name = urllib.quote(name)
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
