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
"""Testing setup for schooltool.requirement

$Id$
"""
__docformat__ = 'reStructuredText'

from zope.interface import Interface
from zope.component import provideAdapter
from zope.keyreference.interfaces import IKeyReference

from schooltool.requirement import requirement, interfaces, evaluation

class KeyReferenceStub(object):
    """A stub implementation to allow testing of evaluations."""

    key_type_id = 'tests.path'

    def __init__(self, context):
        self.context = context

    def __call__(self):
        return self.context

    def __hash__(self):
        return id(self.context)

    def __cmp__(self, ref):
        return cmp((self.key_type_id, self.__hash__()),
                   (ref.key_type_id, ref.__hash__()))

def setUpRequirement(test=None):
    provideAdapter(requirement.getRequirement,
                   (Interface,),
                   interfaces.IRequirement)

def setUpEvaluation(test=None):
    provideAdapter(evaluation.getEvaluations,
                   (Interface,),
                   interfaces.IEvaluations)
    provideAdapter(KeyReferenceStub,
                   (Interface,),
                   IKeyReference)
