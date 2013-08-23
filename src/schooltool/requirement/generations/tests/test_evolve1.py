# coding=UTF8
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Unit tests for schooltool.requirement.generations.evolve1
"""

import cPickle
from pprint import pprint
import unittest, doctest

from zope.interface import Interface, implements
from zope.app.generations.utility import getRootFolder
from zope.app.testing import setup
from zope.site import LocalSiteManager

from schooltool.requirement.generations.tests import (
    ContextStub, provideAdapters, provideUtilities)
from schooltool.requirement.generations.evolve1 import evolve


class IStubUtil(Interface):
    pass


class StubUtil(object):
    implements(IStubUtil)


class IOtherStubUtil(Interface):
    pass


class OtherStubUtil(object):
    implements(IOtherStubUtil)


class ISubclassUtil(IStubUtil):
    pass


class SubclassUtil(object):
    implements(ISubclassUtil)


def doctest_ZopeHasABug():
    """This test checks that there's still a bug in Zope: if you add two or more
    utilities providing same interface to the local site manager, it is not
    possible to cleanly remove them any more.

        >>> context = ContextStub()
        >>> root = getRootFolder(context)
        >>> sm = LocalSiteManager(root)
        >>> root.setSiteManager(sm)

    So, our site manager has no utilities:

        >>> print sm.utilities._provided.get(IStubUtil)
        None

        >>> pprint(sm.utilities._v_lookup._extendors)
        {}

    Let's add one:

        >>> foo = StubUtil()
        >>> sm.registerUtility(foo, IStubUtil, name='foo')

    Note that utility is registered and a subscription is added, hence the 2:

        >>> print sm.utilities._provided.get(IStubUtil)
        2

    Lookup cache also got updated.

        >>> sm.utilities._v_lookup.__class__
        <class 'zope.interface.adapter.VerifyingAdapterLookup'>

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>],
         <InterfaceClass zope.interface.Interface>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>]}

    Now, if we try to unregister:

        >>> sm.unregisterUtility(foo, IStubUtil, name='foo')
        True

    _provided and lookup are cleared:

        >>> print sm.utilities._provided.get(IStubUtil)
        None

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>: [],
        <InterfaceClass zope.interface.Interface>: []}

    And our database is not polluted.

        >>> pickle = cPickle.dumps(sm)
        >>> 'IStubUtil' in pickle
        False

    The trouble begins when we have more than one utility.

        >>> sm.registerUtility(foo, IStubUtil, name='foo')

        >>> print sm.utilities._provided.get(IStubUtil)
        2

        >>> bar = StubUtil()
        >>> sm.registerUtility(bar, IStubUtil, name='bar')

    Note the ref count jumps to 4, because bar is not the same component and
    gets another subscription (that is OK IMHO).

        >>> print sm.utilities._provided.get(IStubUtil)
        4

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>],
         <InterfaceClass zope.interface.Interface>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>]}

    Now, to the bug.  If we unregister utility, the adapter registry does not
    update the _provided correctly.

        >>> sm.unregisterUtility(foo, IStubUtil, name='foo')
        True

        >>> print sm.utilities._provided.get(IStubUtil)
        3

        >>> sm.unregisterUtility(bar, IStubUtil, name='bar')
        True

        >>> print sm.utilities._provided.get(IStubUtil)
        2

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>],
         <InterfaceClass zope.interface.Interface>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>]}

    Congratulations, you are now a proud owner of a polluted database:

        >>> pickle = cPickle.dumps(sm)
        >>> 'IStubUtil' in pickle
        True

    """


def doctest_removeUtils_one():
    """This test demonstrates that removeUtils (hack) works when there is
    only one utility.

        >>> context = ContextStub()
        >>> root = getRootFolder(context)
        >>> sm = LocalSiteManager(root)
        >>> root.setSiteManager(sm)

        >>> sm.utilities.__class__
        <class 'zope.site.site._LocalAdapterRegistry'>

        >>> foo = StubUtil()
        >>> sm.registerUtility(foo, IStubUtil, name='foo')

        >>> ho = SubclassUtil()
        >>> sm.registerUtility(ho, IOtherStubUtil, name='ho')

        >>> from schooltool.requirement.generations.evolve1 import removeUtils
        >>> removeUtils(sm, IStubUtil)

        >>> print sm.utilities._provided.get(IStubUtil)
        None

        >>> print sm.utilities._provided.get(IOtherStubUtil)
        2

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>],
         <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
            [],
         <InterfaceClass zope.interface.Interface>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>]}

        >>> pickle = cPickle.dumps(sm)
        >>> 'IStubUtil' in pickle
        False

    """


def doctest_removeUtils():
    """This test demonstrates that removeUtils (hack) can clean the persisted
    LocalAdapterRegistry from references to "provided" interface.  Other utilities
    are left intact.

        >>> context = ContextStub()
        >>> root = getRootFolder(context)
        >>> sm = LocalSiteManager(root)
        >>> root.setSiteManager(sm)

        >>> sm.utilities.__class__
        <class 'zope.site.site._LocalAdapterRegistry'>

        >>> foo = StubUtil()
        >>> sm.registerUtility(foo, IStubUtil, name='foo')

        >>> bar = StubUtil()
        >>> sm.registerUtility(bar, IStubUtil, name='bar')

        >>> ho = SubclassUtil()
        >>> sm.registerUtility(ho, IOtherStubUtil, name='ho')

        >>> from schooltool.requirement.generations.evolve1 import removeUtils
        >>> removeUtils(sm, IStubUtil)

        >>> print sm.utilities._provided.get(IStubUtil)
        None

        >>> print sm.utilities._provided.get(IOtherStubUtil)
        2

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>],
         <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
            [],
         <InterfaceClass zope.interface.Interface>:
            [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IOtherStubUtil>]}

        >>> pickle = cPickle.dumps(sm)
        >>> 'IStubUtil' in pickle
        False

    """


def doctest_removeUtils_subclass():
    """This test demonstrates that removeUtils (hack) is not designed to work
    in some cases.

        >>> context = ContextStub()
        >>> root = getRootFolder(context)
        >>> sm = LocalSiteManager(root)
        >>> root.setSiteManager(sm)

        >>> foo = StubUtil()
        >>> sm.registerUtility(foo, IStubUtil, name='foo')

        >>> bar = StubUtil()
        >>> sm.registerUtility(bar, IStubUtil, name='bar')

    As we use a subclass interface, the extendors are interesting to us:

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
             [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>],
         <InterfaceClass zope.interface.Interface>:
             [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>]}

        >>> hey = SubclassUtil()
        >>> sm.registerUtility(hey, ISubclassUtil, name='hey')

        >>> ho = SubclassUtil()
        >>> sm.registerUtility(hey, ISubclassUtil, name='ho')

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>,
               <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>],
         <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>],
         <InterfaceClass zope.interface.Interface>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>,
              <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>]}

    Stub utils are removed, but subclass utils are still there

        >>> from schooltool.requirement.generations.evolve1 import removeUtils

        >>> removeUtils(sm, IStubUtil)

        >>> pprint(sm.utilities._v_lookup._extendors)
        {<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.IStubUtil>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>],
         <InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>],
         <InterfaceClass zope.interface.Interface>:
              [<InterfaceClass schooltool.requirement.generations.tests.test_evolve1.ISubclassUtil>]}

        >>> pprint(dict(sm.getUtilitiesFor(ISubclassUtil)))
        {u'hey': <schooltool.requirement.generations.tests.test_evolve1.SubclassUtil object at ...>,
         u'ho': <schooltool.requirement.generations.tests.test_evolve1.SubclassUtil object at ...>}

        >>> pprint(dict(sm.getUtilitiesFor(IStubUtil)))
        {u'hey': <schooltool.requirement.generations.tests.test_evolve1.SubclassUtil object at ...>,
         u'ho': <schooltool.requirement.generations.tests.test_evolve1.SubclassUtil object at ...>}

    Is this acceptable?
    Are there any ICustomScoreSystem subclasses? - no

    """


def doctest_evolve1():
    """Evolution to generation 1.

    First, we'll set up the app object:

        >>> provideAdapters()
        >>> provideUtilities()
        >>> context = ContextStub()
        >>> app = getRootFolder(context)

        >>> sm = LocalSiteManager(app)
        >>> app.setSiteManager(sm)

    We'll set up our test with data that will be effected by running the
    evolve script:

        >>> from schooltool.requirement.interfaces import ICustomScoreSystem
        >>> from schooltool.requirement.scoresystem import (PassFail,
        ...     AmericanLetterScoreSystem, ExtendedAmericanLetterScoreSystem,
        ...     CustomScoreSystem)
        >>> for ss in [PassFail, AmericanLetterScoreSystem,
        ...            ExtendedAmericanLetterScoreSystem]:
        ...     custom_ss = CustomScoreSystem(ss.title, ss.description,
        ...         ss.scores, ss._bestScore, ss._minPassingScore)
        ...     app.getSiteManager().registerUtility(custom_ss,
        ...          ICustomScoreSystem, name=custom_ss.title)

    Finally, we'll run the evolve script, testing the effected values before and
    after:

        >>> from schooltool.requirement.scoresystem import (
        ...     SCORESYSTEM_CONTAINER_KEY)
        >>> SCORESYSTEM_CONTAINER_KEY in app
        False
        >>> sorted(app.getSiteManager().getUtilitiesFor(ICustomScoreSystem))
        [(u'Extended Letter Grade',
             <CustomScoreSystem u'Extended Letter Grade'>),
         (u'Letter Grade', <CustomScoreSystem u'Letter Grade'>),
         (u'Pass/Fail', <CustomScoreSystem u'Pass/Fail'>)]

        >>> evolve(context)

        >>> [ss for ss in app[SCORESYSTEM_CONTAINER_KEY].values()]
        [<CustomScoreSystem u'Letter Grade'>, <CustomScoreSystem u'Pass/Fail'>,
         <CustomScoreSystem u'Extended Letter Grade'>]
        >>> sorted(app.getSiteManager().getUtilitiesFor(ICustomScoreSystem))
        []

        >>> pickle = cPickle.dumps(sm)
        >>> 'ICustomScoreSystem' in pickle
        False

    """


def setUp(test):
    setup.placefulSetUp()
    setup.setUpTraversal()
    provideAdapters()
    provideUtilities()


def tearDown(test):
    setup.placefulTearDown()


def test_suite():
    optionflags = (doctest.ELLIPSIS |
                   doctest.NORMALIZE_WHITESPACE)
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=optionflags)


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

