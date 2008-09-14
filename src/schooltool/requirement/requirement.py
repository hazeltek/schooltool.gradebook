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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""Requirement Implementation

$Id$
"""

__docformat__ = 'restructuredtext'

import BTrees.OOBTree
import persistent
import persistent.list
import zope.event
import zope.interface
import zope.app.container.contained
import zope.lifecycleevent
from zope import component
from zope import annotation
from zope.app.keyreference.interfaces import IKeyReference
from zope.app.container.interfaces import IObjectRemovedEvent
import zope.security.proxy

from schooltool.requirement import interfaces


REQUIREMENT_KEY = "schooltool.requirement"


def getRequirementKey(requirement):
    """Get the reference key for any requirement."""
    return IKeyReference(requirement)


class Requirement(persistent.Persistent,
                  zope.app.container.contained.Contained):
    """A persistent requirement using a BTree for sub-requirements"""
    zope.interface.implements(interfaces.IRequirement)

    def __init__(self, title):
        super(Requirement, self).__init__()
        # See interfaces.IRequirement
        self.title = title
        # Storage for contained requirements
        self._data = BTrees.OOBTree.OOBTree()
        # List of keys that describe the order of the contained requirements
        self._order = persistent.list.PersistentList()

    def changePosition(self, name, pos):
        """See interfaces.IRequirement"""
        old_pos = self._order.index(name)
        self._order.remove(name)
        self._order.insert(pos, name)
        zope.app.container.contained.notifyContainerModified(self)

    def keys(self):
        """See interface `IReadContainer`"""
        return self._order

    def __iter__(self):
        """See interface `IReadContainer`"""
        return iter(self.keys())

    def __getitem__(self, key):
        """See interface `IReadContainer`"""
        return self._data[key]

    def get(self, key, default=None):
        """See interface `IReadContainer`"""
        try:
            return self[key]
        except KeyError:
            return default

    def values(self):
        """See interface `IReadContainer`"""
        return [value for key, value in self.items()]

    def __len__(self):
        """See interface `IReadContainer`"""
        return len(self.keys())

    def items(self):
        """See interface `IReadContainer`"""
        for key in self.keys():
            yield key, self[key]

    def __contains__(self, key):
        """See interface `IReadContainer`"""
        return key in self.keys()

    has_key = __contains__

    def __setitem__(self, key, newobject):
        """See interface `IWriteContainer`"""
        newobject, event = zope.app.container.contained.containedEvent(
            newobject, self, key)
        self._data[key] = newobject
        if key not in self._order:
            self._order.append(key)
        if event:
            zope.event.notify(event)
            zope.lifecycleevent.modified(self)

    def __delitem__(self, key):
        """See interface `IWriteContainer`"""
        zope.app.container.contained.uncontained(self._data[key], self, key)
        del self._data[key]
        self._order.remove(key)

    def updateOrder(self, order):
        """See zope.app.container.interfaces.IOrderedContainer"""
        if set(self._order) != set(order):
            raise ValueError("Incompatible key set.")

        self._order = persistent.list.PersistentList(order)
        zope.app.container.contained.notifyContainerModified(self)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.title)


def getRequirement(context):
    """Adapt an ``IHaveRequirement`` object to ``IRequirement``."""
    annotations = annotation.interfaces.IAnnotations(context)
    try:
        return annotations[REQUIREMENT_KEY]
    except KeyError:
        ## TODO: support generic objects without titles
        requirement = Requirement(getattr(context, "title", None))
        annotations[REQUIREMENT_KEY] = requirement
        zope.app.container.contained.contained(
            requirement, context, u'++requirement++')
        return requirement
# Convention to make adapter introspectable
getRequirement.factory = Requirement


class requirementNamespace(object):
    """Used to traverse to the requirements of an object"""

    def __init__(self, ob, request=None):
        self.context = ob

    def traverse(self, name, ignore):
        reqs = interfaces.IRequirement(self.context)
        return reqs
