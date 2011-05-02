#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008 Shuttleworth Foundation
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
Evolve database to generation 1.

Moves custom score system utilities to the new scoresystems container.
"""

from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite
from zope.container.contained import contained
from zope.container.interfaces import INameChooser

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.requirement.scoresystem import (SCORESYSTEM_CONTAINER_KEY,
    ScoreSystemContainer)
from schooltool.requirement.interfaces import ICustomScoreSystem


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        setSite(app)
        sm = app.getSiteManager()
        scoresystems = app[SCORESYSTEM_CONTAINER_KEY] = ScoreSystemContainer()
        contained(scoresystems, root, 'scoresystems')
        chooser = INameChooser(scoresystems)
        for key, util in sm.getUtilitiesFor(ICustomScoreSystem):
            name = chooser.chooseName('', util)
            scoresystems[name] = util
            sm.unregisterUtility(util, ICustomScoreSystem, key)

    setSite(old_site)

