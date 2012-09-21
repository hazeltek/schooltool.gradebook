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

from zope.app.generations.utility import findObjectsProviding, getRootFolder
from zope.component.hooks import getSite, setSite
from zope.container.interfaces import INameChooser

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.requirement.scoresystem import (SCORESYSTEM_CONTAINER_KEY,
    ScoreSystemContainer)
from schooltool.requirement.interfaces import ICustomScoreSystem


def removeUtils(site_manager, provided):
    """HACK: this does not work properly in generic case!"""
    utilities = list(site_manager.getUtilitiesFor(provided))
    if not utilities:
        return

    for key, util in utilities:
        site_manager.unregisterUtility(util, provided, key)

    n_provided = site_manager.utilities._provided.get(provided)
    if not n_provided:
        return

    del site_manager.utilities._provided[provided]
    site_manager.utilities._v_lookup.remove_extendor(provided)


def evolve(context):
    root = getRootFolder(context)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        setSite(app)
        if SCORESYSTEM_CONTAINER_KEY not in app:
            app[SCORESYSTEM_CONTAINER_KEY] = ScoreSystemContainer()
        scoresystems = app[SCORESYSTEM_CONTAINER_KEY]

        site_manager = app.getSiteManager()
        chooser = INameChooser(scoresystems)
        utilities = list(site_manager.getUtilitiesFor(ICustomScoreSystem))
        for key, util in utilities:
            name = chooser.chooseName('', util)
            scoresystems[name] = util

        removeUtils(site_manager, ICustomScoreSystem)

    setSite(old_site)

