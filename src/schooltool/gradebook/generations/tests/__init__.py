"""
Tests for generation scripts.
"""

from persistent.interfaces import IPersistent

from zope.keyreference.interfaces import IKeyReference
from zope.app.publication.zopepublication import ZopePublication
from zope.app.testing.setup import setUpAnnotations
from zope.component import provideAdapter, provideUtility
from zope.interface import implements

from schooltool.app.app import SchoolToolApplication
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISection
from schooltool.gradebook.activity import getSectionActivities
from schooltool.gradebook.interfaces import IGradebookRoot, IActivities
from schooltool.gradebook.gradebook_init import getGradebookRoot
from schooltool.requirement.evaluation import getEvaluations
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.interfaces import IHaveEvaluations
from schooltool.term.interfaces import IDateManager
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.schoolyear.schoolyear import getSchoolYearContainer
from schooltool.gradebook.tests import stubs


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


def provideAdapters():
    setUpAnnotations()
    provideAdapter(StupidKeyReference, [IPersistent], IKeyReference)
    provideAdapter(getGradebookRoot, adapts=(ISchoolToolApplication,), 
                                     provides=IGradebookRoot)
    provideAdapter(getSectionActivities, adapts=(ISection,), 
                                         provides=IActivities)
    provideAdapter(getEvaluations, adapts=(IHaveEvaluations,), 
                                   provides=IEvaluations)
    provideAdapter(getSchoolYearContainer, adapts=(ISchoolToolApplication,), 
                                           provides=ISchoolYearContainer)


def provideUtilities():
    provideUtility(stubs.DateManagerStub(), IDateManager, '')
