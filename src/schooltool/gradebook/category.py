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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Activity Category
"""
__docformat__ = 'reStructuredText'

import urllib

import z3c.optionstorage.vocabulary
import zope.schema.vocabulary
from zope.interface import implements, implementer
from zope.component import adapter
from zope.schema.interfaces import IIterableVocabulary, IVocabularyTokenized
from zope.container.btree import BTreeContainer

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook.interfaces import ICategoryContainer


CATEGORIES_KEY = 'schooltool.gradebook.category'


# BBB: for old data.fs'es
class CategoryVocabulary(z3c.optionstorage.vocabulary.OptionStorageVocabulary):
    pass


class CategoryContainer(BTreeContainer):
    implements(ICategoryContainer)

    default_key = None

    @property
    def default(self):
        return self.get(self.default_key)


class CategoriesVocabulary(object):
    """Vocabulary of categories."""
    implements(IIterableVocabulary, IVocabularyTokenized)

    def __init__(self, context):
        self.context = context

    def __len__(self):
        return len(self.container)

    def __contains__(self, key):
        return key in self.container

    def getTermByToken(self, token):
        terms = [self.getTerm(key) for key in self.container]
        by_token = dict([(term.token, term) for term in terms])
        if token not in by_token:
            raise LookupError(token)
        return by_token[token]

    def getTerm(self, key):
        return zope.schema.vocabulary.SimpleTerm(
            key,
            token=urllib.quote(unicode(key)),
            title=self.container[key])

    def __iter__(self):
        for key in sorted(self.container):
            yield self.getTerm(key)

    @property
    def container(self):
        app = ISchoolToolApplication(None)
        return ICategoryContainer(app)


def categoryVocabularyFactory():
    return CategoriesVocabulary


@adapter(ISchoolToolApplication)
@implementer(ICategoryContainer)
def getCategories(app):
    return app.get(CATEGORIES_KEY)
