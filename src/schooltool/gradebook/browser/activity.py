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
"""Activity Views.

$Id$
"""
from decimal import Decimal, InvalidOperation

import zope.security.proxy
from zope.app.form.browser.editview import EditView
from zope.security.checker import canWrite
from zope.security.interfaces import Unauthorized
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.traversing.api import getName

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.app.browser import app
from schooltool.common import SchoolToolMessage as _
from schooltool.gradebook import interfaces
from schooltool.gradebook.category import getCategories
from schooltool.person.interfaces import IPerson


class ActivitiesView(object):
    """A Group Container view."""

    __used_for__ = interfaces.IActivities

    @property
    def worksheets(self):
        """Get  a list of all worksheets."""
        return sorted(self.context.values(), key=lambda x: x.title)

    @property
    def currentWorksheet(self):
        return self.context.getCurrentWorksheet(self.person)
    
    def activities(self):
        pos = 0
        for activity in self.context.getCurrentActivities(self.person):
            pos += 1
            yield {'name': getName(activity),
                   'title': activity.title,
                   'url': absoluteURL(activity, self.request),
                   'pos': pos}

    def positions(self):
        return range(1, len(self.currentWorksheet)+1)

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
                del self.currentWorksheet[name]

        elif 'DELETE_WORKSHEET' in self.request:
            name = self.request.get('DELETE_WORKSHEET')
            del self.context[name]
            self.context.resetCurrentWorksheet(self.person)

        elif 'form-submitted' in self.request:
            old_pos = 0
            for activity in self.context.getCurrentActivities(self.person):
                old_pos += 1
                name = getName(activity)
                if 'pos.'+name not in self.request:
                    continue
                new_pos = int(self.request['pos.'+name])
                if new_pos != old_pos:
                    self.currentWorksheet.changePosition(name, new_pos-1)
        
            """Handle change of current worksheet."""
            if 'currentWorksheet' in self.request:
                for worksheet in self.worksheets:
                    if worksheet.title == self.request['currentWorksheet']:
                        self.context.setCurrentWorksheet(self.person, worksheet)
                        break


class WorksheetAddView(app.BaseAddView):
    """A view for adding a worksheet."""

    def nextURL(self):
        person = IPerson(self.request.principal, None)
        self.context.context.resetCurrentWorksheet(person)
        return absoluteURL(self.context.context, self.request)


class ActivityAddView(app.BaseAddView):
    """A view for adding an activity."""

    def nextURL(self):
        return absoluteURL(self.context.context.__parent__, self.request)


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


class WorksheetDeleteView(object):
    """A view for deleting a worksheet."""

    def update(self):
        next_url = absoluteURL(self.context.__parent__, self.request)
        if 'CANCEL' in self.request:
            self.request.response.redirect(next_url)
        elif 'DELETE' in self.request:
            next_url += '?DELETE_WORKSHEET=' + self.context.__name__
            self.request.response.redirect(next_url)


class ActivityEditView(BaseEditView):
    """A view for editing activity info."""

    def nextURL(self):
        return absoluteURL(self.context.__parent__.__parent__, self.request)


class WeightCategoriesView(object):
    """A view for providing category weights for the worksheet context."""

    def nextURL(self):
        section = self.context.__parent__.__parent__
        return absoluteURL(section, self.request) + '/gradebook'

    def update(self):
        self.message = ''
        language = 'en' # XXX this need to be dynamic
        categories = getCategories(ISchoolToolApplication(None))

        newValues = {}
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())

        elif 'UPDATE_SUBMIT' in self.request:
            for category in sorted(categories.getKeys()):
                if category in self.request and self.request[category]:
                    value = self.request[category]
                    try:
                        value = Decimal(value)
                        if value < 0 or value > 100:
                            raise ValueError
                    except (InvalidOperation, ValueError):
                        self.message = _('$value is not a valid weight.',
                            mapping={'value': value})
                        break
                    newValues[category] = value
            else:
                total = 0
                for category in newValues:
                    total += newValues[category]
                if total != Decimal(100):
                    self.message = _('Category weights must add up to 100.')
                else:
                    for category in newValues:
                        self.context.setCategoryWeight(category, 
                            newValues[category] / 100)
                    self.request.response.redirect(self.nextURL())

        weights = self.context.getCategoryWeights()
        self.rows = []
        for category in sorted(categories.getKeys()):
            if category in self.request:
                weight = self.request[category]
            else:
                weight = str(weights.get(category, '') * 100)
                if '.' in weight:
                    while weight.endswith('0'):
                        weight = weight[:-1]
                    if weight[-1] == '.':
                        weight = weight[:-1]
            row = {
                'category': category,
                'category_value': categories.getValue(category, language),
                'weight': weight,
                }
            self.rows.append(row)

