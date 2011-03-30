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
Functional tests for schooltool.gradebook.

$Id$
"""

import unittest
import os
import datetime
import time

from zope.component import adapter
from zope.interface import implements, implementer
from zope.publisher.browser import BrowserView

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISection
from schooltool.testing.functional import collect_ftests
from schooltool.testing.functional import ZCMLLayer

from schooltool.gradebook.interfaces import IIndependentSectionJournalData

dir = os.path.abspath(os.path.dirname(__file__))
filename = os.path.join(dir, '../ftesting.zcml')

gradebook_functional_layer = ZCMLLayer(filename,
                                       __name__,
                                       'gradebook_functional_layer')


meetings = {}


class MeetingStub(object):

    __parent__ = None
    resources = []
    period_id = 'First'

    def __init__(self, meeting):
        parsed = time.strptime(meeting, '%B %d %Y')
        self.dtstart = datetime.datetime(*parsed[0:5])


class IndependentSectionJournalDataStub(object):
    implements(IIndependentSectionJournalData)

    def __init__(self, section):
        self.section = section
        self.students = {}

    def setGrade(self, student, meeting, grade):
        meeting_stub = meetings.setdefault(meeting, MeetingStub(meeting))
        self.students.setdefault(student, {})[meeting_stub] = grade

    def recordedMeetings(self, student):
        return self.students.get(student, {}).keys()

    def getGrade(self, student, meeting):
        return self.students.get(student, {}).get(meeting)


section_journal_data = {}


@adapter(ISection)
@implementer(IIndependentSectionJournalData)
def getSectionIndependentSectionJournalData(section):
    return section_journal_data.setdefault(section,
        IndependentSectionJournalDataStub(section))


class TestOnlyUpdateSectionJournalView(BrowserView):
    convert_grade = {'a': 'n', 't': 'p'}

    def __call__(self):
        for person in ISchoolToolApplication(None)['persons'].values():
            if person.first_name == self.request['student']:
                student = person
                break
        meeting = '%s %s 2010' % (self.request['month'], self.request['day'])
        grade = self.convert_grade[self.request['grade']]
        jd = IIndependentSectionJournalData(self.context)
        jd.setGrade(student, meeting, grade)


def test_suite():
    return collect_ftests(layer=gradebook_functional_layer)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
