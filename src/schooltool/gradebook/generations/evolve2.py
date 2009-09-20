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

Moves hard-coded score system utilities to the app site manager.
"""

from zope.app.zopeappgenerations import getRootFolder
from zope.security.proxy import removeSecurityProxy

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.requirement.interfaces import ICustomScoreSystem
from schooltool.requirement.scoresystem import CustomScoreSystem


def evolve(context):
    """Adds abbreviation column to all custom score systems"""

    app = getRootFolder(context)
    sm = app.getSiteManager()
    for name, util in sorted(sm.getUtilitiesFor(ICustomScoreSystem)):
        util = removeSecurityProxy(util)
        new_scores = []
        for score, value, percent in util.scores:
            new_scores.append([score, '', value, percent])
        util.scores = new_scores

