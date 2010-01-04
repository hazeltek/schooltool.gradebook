#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2006 Shuttleworth Foundation
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
schooltooo.requirement browser views.

$Id$
"""
import urllib

from zope.traversing.browser.absoluteurl import absoluteURL
from zope.app.form.browser.add import AddView
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile

from schooltool.gradebook import GradebookMessage as _
from schooltool.requirement.interfaces import IRequirement
from schooltool.skin.containers import ContainerView
from schooltool.table.batch import IterableBatch
from schooltool.app.browser.app import BaseEditView


class RequirementAddView(AddView):
    """A view for adding Requirements."""

    def nextURL(self):
        return absoluteURL(self.context.context, self.request)

    def update(self):
        if 'CANCEL' in self.request:
            self.request.response.redirect(self.nextURL())
        else:
            return AddView.update(self)


class RequirementView(ContainerView):
    """A Requirement view."""

    __used_for__ = IRequirement

    index_title = _("Requirement index")

    def __init__(self, context, request, depth=None):
        ContainerView.__init__(self, context, request)
        self.depth = depth
        if self.depth is None:
            self.depth = int(request.get('DEPTH', 3))

    def _search(self, searchstr, context):
        results = []
        for item in context.values():
            if searchstr.lower() in item.title.lower():
                results.append(item)
            results += self._search(searchstr, item)
        return results

    def update(self):
        if 'SEARCH' in self.request and 'CLEAR_SEARCH' not in self.request:
            searchstr = self.request['SEARCH'].lower()
            if self.request.get('RECURSIVE'):
                results = self._search(searchstr, self.context)
            else:
                results = [item for item in self.context.values()
                           if searchstr in item.title.lower()]
            extra_url = "&SEARCH=%s" % urllib.quote(self.request['SEARCH'])
        else:
            self.request.form['SEARCH'] = ''
            results = self.context.values()
            extra_url = ""

        self.batch = IterableBatch(results, self.request, sort_by='title',
                                   extra_url=extra_url)

    def listContentInfo(self):
        children = []
        if self.depth < 1:
            return []
        for child in self.batch:
            if IRequirement.providedBy(child):
                info = {}
                info['child'] = child
                thread = RequirementView(child, self.request, self.depth-1)
                info['thread'] = thread.subthread()
                children.append(info)
        return children

    subthread = ViewPageTemplateFile('subthread.pt')


class RequirementEditView(BaseEditView):
    """View for editing Requirements."""

    __used_for__ = IRequirement

