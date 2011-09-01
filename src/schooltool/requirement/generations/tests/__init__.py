"""
Tests for generation scripts.
"""
import datetime

from persistent.interfaces import IPersistent

from zope.keyreference.interfaces import IKeyReference
from zope.app.publication.zopepublication import ZopePublication
from zope.app.testing.setup import setUpAnnotations
from zope.component import provideAdapter, provideUtility
from zope.interface import implements

from schooltool.app.app import SchoolToolApplication
from schooltool.term.interfaces import IDateManager


class ContextStub(object):
    """Stub for the context argument passed to evolve scripts.

        >>> from zope.app.generations.utility import getRootFolder
        >>> context = ContextStub()
        >>> getRootFolder(context) is context.root_folder
        True
    """

    class ConnectionStub(object):
        def __init__(self, root_folder):
            self.root_folder = root_folder
        def root(self):
            return {ZopePublication.root_name: self.root_folder}

    def __init__(self):
        self.root_folder = SchoolToolApplication()
        self.connection = self.ConnectionStub(self.root_folder)


_d = {}

class StupidKeyReference(object):
    implements(IKeyReference)
    key_type_id = 'StupidKeyReference'
    def __init__(self, ob):
        global _d
        self.id = id(ob)
        _d[self.id] = ob
    def __call__(self):
        return _d[self.id]
    def __hash__(self):
        return self.id
    def __cmp__(self, other):
        return cmp(hash(self), hash(other))


class DateManagerStub(object):
    implements(IDateManager)

    def __init__(self):
        self.current_term = None
        self.today = datetime.date(2011, 1, 23)


def provideAdapters():
    setUpAnnotations()
    provideAdapter(StupidKeyReference, [IPersistent], IKeyReference)


def provideUtilities():
    provideUtility(DateManagerStub(), IDateManager, '')

