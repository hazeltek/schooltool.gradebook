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
RESTive views for SchoolBellApplication

$Id$
"""
from zope.app import zapi
from schoolbell.app.rest import View, Template


class ApplicationView(View):
    """The root view for the application."""

    template = Template("www/app.pt", content_type="text/xml; charset=UTF-8")

    def getContainers(self):
        return [{'href': zapi.absoluteURL(self.context[key], self.request),
                 'title': key} for key in self.context.keys()]
