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
Evolve database to generation 4.

Replace option storage with a simple container.
"""
from zope.annotation.interfaces import IAnnotations
from zope.app.generations.utility import findObjectsProviding
from zope.app.publication.zopepublication import ZopePublication
from zope.component.hooks import getSite, setSite

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook.category import CategoryContainer


VOCABULARY_NAME = 'schooltool.gradebook.activities'
CATEGORY_KEY = 'schooltool.gradebook.category'


def copyCategories(app, storage):
    vocab = storage.get(VOCABULARY_NAME)
    if vocab is None:
        return
    categories = app[CATEGORY_KEY] = CategoryContainer()

    for key in vocab.getKeys():
        val = vocab.queryValue(key, 'en')
        categories[key] = val

    categories.default_key = vocab.getDefaultKey()


def evolve(context):
    root = context.connection.root().get(ZopePublication.root_name, None)

    old_site = getSite()
    apps = findObjectsProviding(root, ISchoolToolApplication)
    for app in apps:
        ann = IAnnotations(app)
        if 'optionstorage' in ann:
            copyCategories(app, ann['optionstorage'])
            del ann['optionstorage'][VOCABULARY_NAME]
            if not ann['optionstorage']:
                del ann['optionstorage']

    setSite(old_site)
