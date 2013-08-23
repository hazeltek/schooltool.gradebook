#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2011 Shuttleworth Foundation
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
"""
Evolve database to generation 3.

Locates GradebookRoot members in GradebookRoot.
"""
import zope.event
from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite
from zope.container.contained import containedEvent

from schooltool.app.interfaces import ISchoolToolApplication


GRADEBOOK_ROOT_KEY = 'schooltool.gradebook'


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        gb = app.get(GRADEBOOK_ROOT_KEY)
        gb.templates, event = containedEvent(gb.templates, gb, 'templates')
        zope.event.notify(event)
        gb.deployed, event = containedEvent(gb.deployed, gb, 'deployed')
        zope.event.notify(event)
        gb.layouts, event = containedEvent(gb.layouts, gb, 'layouts')
        zope.event.notify(event)

    setSite(old_site)
