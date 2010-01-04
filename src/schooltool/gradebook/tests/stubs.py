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
"""
Stubs for Gradebook-related Tests

"""
from decimal import Decimal
import zope.interface

from schooltool.gradebook import interfaces


class ExternalActivityStub(object):

    zope.interface.implements(interfaces.IExternalActivity)
    
    def __init__(self, source, ID, title, description=None, grades={}):
        self.source = source
        self.external_activity_id = ID
        self.title = title
        self.description = description
        self.grades = grades

    def getGrade(self, student):
        return self.grades.get(student.username)

    def __repr__(self):
        return '<ExternalActivity %r>' % (self.title)

    def __eq__(self, other):
        return other is not None and \
               self.source == other.source and \
               self.external_activity_id == other.external_activity_id


class ExternalActivitiesStub(object):

    source = ""
    title = u""

    def __init__(self, context):
        pass
    
    def __repr__(self):
        return '<ExternalActivities...>'

    def getExternalActivities(self):
        return sorted(self.activities.values(),
                      key=lambda x:x.external_activity_id)

    def getExternalActivity(self, external_activity_id):
        return self.activities.get(external_activity_id)


class SomeProductStub(ExternalActivitiesStub):

    source = "someproduct"
    title = u"Some Product"
    activities = {u"some1": \
                  ExternalActivityStub(u"someproduct",
                                       u"some1",
                                       u"Some1",
                                       u"Some1 description",
                                       grades={"paul": Decimal("0.5")})}


class ThirdPartyStub(ExternalActivitiesStub):

    source = "thirdparty"
    title = u"Third Party"
    activities = {u"third1": ExternalActivityStub(u"thirdparty", u"third1",
                                                  u"Third1"),
                  u"third2": ExternalActivityStub(u"thirdparty", u"third2",
                                                  u"Third2"),
                  u"third3": ExternalActivityStub(u"thirdparty", u"third3",
                                                  u"Third3")}


class SampleSource(ExternalActivitiesStub):

    source = "samplesource"
    title = u"Sample Source"
    activities = {"hardware": ExternalActivityStub(u"samplesource",
                                                   u"hardware",
                                                   u"Hardware",
                                                   u"Hardware description",
                                                   grades={"claudia": \
                                                           Decimal("0.4"),
                                                           "tom": \
                                                           Decimal("0.6")}),
                  "html": ExternalActivityStub(u"samplesource",
                                               u"html",
                                               u"HTML",
                                               grades={"claudia": \
                                                       Decimal("0.8"),
                                                       "paul": \
                                                       Decimal("0.5")})}

    def __init__(self, context):
        self.section = context
        result = []
        for name, activity in self.activities.items():
            activity.__parent__ = context
            result.append((name, activity))
        self.activities = dict(result)
            
