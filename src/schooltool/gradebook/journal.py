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

from zope.interface import implements

from schooltool.gradebook import interfaces
from schooltool.gradebook import GradebookMessage as _
from schooltool.requirement.scoresystem import UNSCORED

try:
    from schooltool.lyceum.journal.interfaces import ISectionJournalData
    from schooltool.lyceum.journal.journal import ABSENT, TARDY
except ImportError:
    def ISectionJournalData(section):
        return None
    ABSENT = 'n'
    TARDY = 'p'


# adapt section to gradebook's ISectionJournalData interface, returning
# real ISectionJournalData
def getSectionJournalData(section):
    return ISectionJournalData(section)


class JournalSource(object):

    implements(interfaces.IExternalActivities)

    source = "journalsource"
    title = _('Journal')

    def __init__(self, context):
        self.context = context
        self.activities = [JournalExternalActivity(self)]
        self.__parent__ = context

    def getExternalActivities(self):
        return self.activities

    def getExternalActivity(self, external_activity_id):
        return self.activities[0]


class JournalExternalActivity(object):

    implements(interfaces.IExternalActivity)

    title = _('Journal Average')
    description = None
    external_activity_id = 'journal_average'

    def __init__(self, context):
        self.context = context
        section = context.context
        self.journal_data = getSectionJournalData(section)
        self.__parent__ = section
        self.source = context.source

    def getGrade(self, student):
        grades = []
        for meeting, score in self.journal_data.gradedMeetings(student):
            grade = score.value
            if grade is UNSCORED:
                continue
            try:
                grade = score.scoreSystem.getNumericalValue(grade)
            except ValueError:
                continue
            grades.append(grade)
        if len(grades):
            # XXX: should return fractional value of scoresystem max
            return float(sum(grades)) / float(10 * len(grades))

    def __eq__(self, other):
        return interfaces.IExternalActivity.providedBy(other) and \
               self.source == other.source and \
               self.external_activity_id == other.external_activity_id
