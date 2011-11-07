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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Evolve database to generation 5.

Fix deployed report sheet keys to allow for hide/unhide feature.
"""
from zope.annotation.interfaces import IAnnotations
from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.schoolyear.interfaces import ISchoolYearContainer

from schooltool.gradebook.interfaces import IGradebookRoot, IActivities


def fixYear(year, app):
    root = IGradebookRoot(app)
    year_dict, index = {}, 0
    for sheet in root.deployed.values():
        for term in year.values():
            key = '%s_%s' % (year.__name__, term.__name__)
            if sheet.__name__.startswith(key):
                rest = sheet.__name__[len(key):]
                if not rest:
                    break
                elif len(rest) > 1 and rest[0] == '-' and rest[1:].isdigit():
                    break
        else:
            continue
        index += 1
        new_key = '%s_%s' % (key, index)
        year_dict[sheet.__name__] = new_key

    for key, new_key in year_dict.items():
        sheet = root.deployed[key]
        sheet.__name__ = new_key
        root.deployed[new_key] = sheet
        del root.deployed[key]

        for sections in app['schooltool.course.section'].values():
            for section in sections.values():
                activities = IActivities(section)
                if key in activities:
                    sheet = activities[key]
                    sheet.__name__ = new_key
                    activities[new_key] = sheet
                    del activities[key]


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        for year in ISchoolYearContainer(app).values():
            fixYear(year, app)
    setSite(old_site)

