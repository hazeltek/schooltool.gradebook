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
Level-related Tests
"""

__docformat__ = 'restructuredtext'

import datetime
import persistent
from BTrees.OOBTree import OOBTree

import zope.event
from zope.interface import implements
from zope.component import adapts
from zope.annotation.interfaces import IAnnotations
from zope.container.contained import Contained, containedEvent
from zope.lifecycleevent import ObjectRemovedEvent
from zope.location import location
from zope.keyreference.interfaces import IKeyReference
from zope.traversing.api import getParent, getName

from schooltool.requirement import interfaces
from schooltool.requirement.scoresystem import UNSCORED


EVALUATIONS_KEY = "schooltool.evaluations"


def getRequirementList(req, recurse=True):
    result = []
    for value in req.values(): # loop through your children
        if recurse:
            result += getRequirementList(value) # append their children...
        else:
            result.append(value) # just append the child
    result.append(req) # append the object itself
    return result


class Evaluations(persistent.Persistent, Contained):
    """Evaluations mapping.

    This particular implementation uses the ``zope.keyreference`` package
    to generate the keys of the requirements. Any key that is passed in could
    be the requirement or the ``IKeyReference`` of the requirement. This
    implementation will always convert the key to provide ``IKeyReference``
    before treating it as a true key.

    Another feature of this implementation is that if you set an evaluation
    for a requirement that has already an evaluation, then the old evaluation
    is simply overridden. The ``IContainer`` interface would raise a duplicate
    name error.
    """
    implements(interfaces.IEvaluations)

    _history = None

    def __init__(self, items=None):
        super(Evaluations, self).__init__()

        self._btree = OOBTree()
        for name, value in items or []:
            self[name] = value

    def __getitem__(self, key):
        """See zope.interface.common.mapping.IItemMapping"""
        return self._btree[IKeyReference(key)]

    def __delitem__(self, key):
        """See zope.interface.common.mapping.IWriteMapping"""
        value = self[key]
        del self._btree[IKeyReference(key)]
        self.appendToHistory(key, value)
        event = ObjectRemovedEvent(value, self)
        zope.event.notify(event)

    def __setitem__(self, requirement, value):
        """See zope.interface.common.mapping.IWriteMapping"""
        key = IKeyReference(requirement)
        if (key in self._btree or
            self.getHistory(requirement)):
            current = self._btree.get(key, None)
            self.appendToHistory(requirement, current)
        self._btree[key] = value
        value, event = containedEvent(value, self)
        zope.event.notify(event)

    def get(self, key, default=None):
        """See zope.interface.common.mapping.IReadMapping"""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        """See zope.interface.common.mapping.IReadMapping"""
        return IKeyReference(key) in self._btree

    def keys(self):
        """See zope.interface.common.mapping.IEnumerableMapping"""
        # For now I decided to return the activities (as I think it is more
        # natural), though they are not the true keys as we know
        return [key() for key in self._btree.keys()]

    def __iter__(self):
        """See zope.interface.common.mapping.IEnumerableMapping"""
        return iter(self.keys())

    def values(self):
        """See zope.interface.common.mapping.IEnumerableMapping"""
        return self._btree.values()

    def items(self):
        """See zope.interface.common.mapping.IEnumerableMapping"""
        return [(key(), value) for key, value in self._btree.items()]

    def __len__(self):
        """See zope.interface.common.mapping.IEnumerableMapping"""
        return len(self._btree)

    def appendToHistory(self, requirement, evaluation):
        if self._history is None:
            self._history = OOBTree()
        key = IKeyReference(requirement)
        if key not in self._history:
            self._history[key] = persistent.list.PersistentList()
        self._history[key].append(evaluation)

    def getHistory(self, requirement):
        if self._history is None:
            return []
        key = IKeyReference(requirement)
        history = list(self._history.get(key, []))
        return history

    def addEvaluation(self, evaluation):
        """See interfaces.IEvaluations"""
        self[evaluation.requirement] = evaluation

    def getEvaluationsForRequirement(self, req, recurse=True):
        """See interfaces.IEvaluations"""
        requirements = getRequirementList(req, recurse)
        result = [(name, ev)
                  for name, ev in self.items()
                  if ev.requirement in requirements]
        result = Evaluations(result)
        location.locate(result, getParent(self), getName(self))
        return result

    def getEvaluationsOfEvaluator(self, evaluator):
        """See interfaces.IEvaluations"""
        result = [(name, ev)
                  for name, ev in self.items()
                  if ev.evaluator == evaluator]
        result = Evaluations(result)
        location.locate(result, getParent(self), getName(self))
        return result

    def __repr__(self):
        try:
            parent = getParent(self)
        except TypeError:
            parent = None
        return '<%s for %r>' % (self.__class__.__name__, parent)


class Score(object):
    implements(interfaces.IScore)

    def __init__(self, scoreSystem, value):
        self.scoreSystem = scoreSystem
        self._value = None
        self.value = value

    @apply
    def value():
        def get(self):
            return self._value

        def set(self, value):
            if not self.scoreSystem.isValidScore(value):
                raise ValueError('%r is not a valid score.' %value)
            if interfaces.IDiscreteValuesScoreSystem.providedBy(value):
                value = self.scoreSystem.fromUnicode(value)
            self._value = value
            # XXX mg: since it is a very bad idea to mix datetimes with tzinfo
            # and datetimes without tzinfo, I suggest using datetimes with
            # tzinfo everywhere.  Most of SchoolTool follows this convention,
            # (with the painful exception of schooltool.timetable).
            self.time = datetime.datetime.utcnow()

        return property(get, set)

    def __nonzero__(self):
        return self.value is not UNSCORED


class Evaluation(Contained, Score):
    implements(interfaces.IEvaluation)

    def __init__(self, requirement, scoreSystem, value, evaluator):
        Contained.__init__(self)
        Score.__init__(self, scoreSystem, value)
        self.requirement = requirement
        self.evaluator = evaluator

    @property
    def evaluatee(self):
        try:
            return getParent(getParent(self))
        except TypeError:
            raise ValueError('Evaluation is not yet assigned to a evaluatee')

    def __repr__(self):
        return '<%s for %r, value=%r>' % (self.__class__.__name__,
                                          self.requirement, self.value)


class AbstractQueryAdapter(object):

    adapts(interfaces.IEvaluations)
    implements(interfaces.IEvaluationsQuery)

    def __init__(self, context):
        self.context = context

    def _query(self, *args, **kwargs):
        raise NotImplemented

    def __call__(self, *args, **kwargs):
        """See interfaces.IEvaluationsQuery"""
        result = Evaluations(self._query(*args, **kwargs))
        location.locate(
            result, getParent(self.context), getName(self.context))
        return result


def getEvaluations(context):
    """Adapt an ``IHaveEvaluations`` object to ``IEvaluations``."""
    annotations = IAnnotations(context)
    try:
        return annotations[EVALUATIONS_KEY]
    except KeyError:
        evaluations = Evaluations()
        annotations[EVALUATIONS_KEY] = evaluations
        location.locate(evaluations, zope.proxy.removeAllProxies(context),
                        '++evaluations++')
        return evaluations
# Convention to make adapter introspectable
getEvaluations.factory = Evaluations

