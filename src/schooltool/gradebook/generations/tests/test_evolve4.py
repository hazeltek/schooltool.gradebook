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
Unit tests for schooltool.gradebook.generations.evolve4
"""

import unittest, doctest

from persistent.mapping import PersistentMapping
from zope.annotation.interfaces import IAnnotations
from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup
from zope.component.hooks import getSite, setSite
from zope.site import LocalSiteManager

from schooltool.gradebook.generations.tests import ContextStub
from schooltool.gradebook.generations.evolve4 import evolve

VOCABULARY_NAME = 'schooltool.gradebook.activities'
CATEGORY_KEY = 'schooltool.gradebook.category'


class VocabularyStub(dict):

    default_key = None

    def getKeys(self):
        return self.keys()

    def queryValue(self, key, lang):
        assert lang == 'en'
        return self.get(key)

    def getDefaultKey(self):
        return self.default_key


def addOptionStorage(app, storages={}, default=None):
    annotations = IAnnotations(app)
    storage = PersistentMapping()
    for st_key, data in storages.items():
        storage[st_key] = VocabularyStub(data)
        storage[st_key].default_key = default
    annotations['optionstorage'] = storage


def doctest_evolve4():
    r"""Evolution to generation 4.

    First, we'll set up the app object:

        >>> context = ContextStub()
        >>> app = getRootFolder(context)
        >>> app.setSiteManager(LocalSiteManager(app))
        >>> setSite(app)

        >>> addOptionStorage(app, {VOCABULARY_NAME: {
        ...     u'assignment': u'Assignment',
        ...     u'essay': u'Essay',
        ...     u'homework': u'Homework',
        ...     }}, default=u'essay')

        >>> CATEGORY_KEY in app
        False

        >>> anns = IAnnotations(app)
        >>> 'optionstorage' in anns
        True

    Let's evolve.

        >>> evolve(context)

    Category container was added to app, it's values copied from
    respective option storage container:

        >>> cats = app[CATEGORY_KEY]
        >>> cats
        <schooltool.gradebook.category.CategoryContainer ...>

        >>> cats.default_key
        u'essay'

        >>> sorted(cats.items())
        [(u'assignment', u'Assignment'),
         (u'essay', u'Essay'),
         (u'homework', u'Homework')]

    Optionstorage was removed from annotations completely.

        >>> anns = IAnnotations(app)

        >>> 'optionstorage' in anns
        False

    """


def doctest_evolve4_garbage_storages():
    r"""Evolution to generation 4.

    First, we'll set up the app object:

        >>> context = ContextStub()
        >>> app = getRootFolder(context)
        >>> app.setSiteManager(LocalSiteManager(app))
        >>> setSite(app)

        >>> addOptionStorage(app, {VOCABULARY_NAME: {
        ...         u'assignment': u'Assignment',
        ...         u'essay': u'Essay',
        ...         u'homework': u'Homework'},
        ...         'some.plugin.data': {}
        ...     },
        ...     default=u'essay')

        >>> CATEGORY_KEY in app
        False

        >>> anns = IAnnotations(app)
        >>> 'optionstorage' in anns
        True

    Let's evolve.

        >>> evolve(context)

    Category container was added to app, it's values copied from
    respective option storage container:

        >>> cats = app[CATEGORY_KEY]
        >>> cats
        <schooltool.gradebook.category.CategoryContainer ...>

        >>> cats.default_key
        u'essay'

        >>> sorted(cats.items())
        [(u'assignment', u'Assignment'),
         (u'essay', u'Essay'),
         (u'homework', u'Homework')]

    But this time, option storage was left with plugins' data.

        >>> anns = IAnnotations(app)

        >>> 'optionstorage' in anns
        True

        >>> sorted(anns['optionstorage'])
        ['some.plugin.data']

    """


def setUp(test):
    setup.placelessSetUp()
    setup.setUpAnnotations()
    setSite()

def tearDown(test):
    setSite()
    setup.placelessTearDown()


def test_suite():
    optionflags = (doctest.ELLIPSIS
                   | doctest.NORMALIZE_WHITESPACE
                   | doctest.REPORT_NDIFF
                   | doctest.REPORT_ONLY_FIRST_FAILURE)
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=optionflags)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
