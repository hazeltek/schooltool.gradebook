#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2003 Shuttleworth Foundation
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
Unit tests for the schooltool.calendar module.

$Id$
"""

import unittest
import calendar
from pprint import pformat
from datetime import date, timedelta, datetime
from StringIO import StringIO
from zope.interface.verify import verifyObject
from zope.testing.doctestunit import DocTestSuite
from schooltool.tests.helpers import diff, dedent, sorted
from schooltool.tests.utils import EqualsSortedMixin
from schooltool.interfaces import ISchooldayModel


class TestSchooldayModel(unittest.TestCase):

    def test_interface(self):
        from schooltool.cal import SchooldayModel
        from schooltool.interfaces import ISchooldayModel, ISchooldayModelWrite
        from schooltool.interfaces import ILocation

        cal = SchooldayModel(date(2003, 9, 1), date(2003, 12, 24))
        verifyObject(ISchooldayModel, cal)
        verifyObject(ISchooldayModelWrite, cal)
        verifyObject(ILocation, cal)

    def testAddRemoveSchoolday(self):
        from schooltool.cal import SchooldayModel

        cal = SchooldayModel(date(2003, 9, 1), date(2003, 9, 14))

        self.assert_(not cal.isSchoolday(date(2003, 9, 1)))
        self.assert_(not cal.isSchoolday(date(2003, 9, 2)))
        self.assertRaises(ValueError, cal.isSchoolday, date(2003, 9, 15))

        cal.add(date(2003, 9, 2))
        self.assert_(cal.isSchoolday(date(2003, 9, 2)))
        cal.remove(date(2003, 9, 2))
        self.assert_(not cal.isSchoolday(date(2003, 9, 2)))
        self.assertRaises(ValueError, cal.add, date(2003, 9, 15))
        self.assertRaises(ValueError, cal.remove, date(2003, 9, 15))

    def testReset(self):
        from schooltool.cal import SchooldayModel
        cal = SchooldayModel(date(2003, 9, 1), date(2003, 9, 15))
        cal.addWeekdays(1, 3, 5)

        new_first, new_last = date(2003, 8, 1), date(2003, 9, 30)
        cal.reset(new_first, new_last)

        self.assertEqual(cal.first, new_first)
        self.assertEqual(cal.last, new_last)
        for d in cal:
            self.assert_(not cal.isSchoolday(d))

        self.assertRaises(ValueError, cal.reset, new_last, new_first)

    def testMarkWeekday(self):
        from schooltool.cal import SchooldayModel
        cal = SchooldayModel(date(2003, 9, 1), date(2003, 9, 17))
        for day in 1, 8, 15:
            self.assert_(not cal.isSchoolday(date(2003, 9, day)))

        cal.addWeekdays(calendar.MONDAY)
        for day in 1, 8, 15:
            self.assert_(cal.isSchoolday(date(2003, 9, day)))
            self.assert_(not cal.isSchoolday(date(2003, 9, day+1)))

        cal.removeWeekdays(calendar.MONDAY, calendar.TUESDAY)
        for day in 1, 8, 15:
            self.assert_(not cal.isSchoolday(date(2003, 9, day)))
            self.assert_(not cal.isSchoolday(date(2003, 9, day+1)))

        cal.addWeekdays(calendar.MONDAY, calendar.TUESDAY)
        for day in 1, 8, 15:
            self.assert_(cal.isSchoolday(date(2003, 9, day)))
            self.assert_(cal.isSchoolday(date(2003, 9, day+1)))

    def test_contains(self):
        from schooltool.cal import SchooldayModel
        cal = SchooldayModel(date(2003, 9, 1), date(2003, 9, 16))
        self.assert_(date(2003, 8, 31) not in cal)
        self.assert_(date(2003, 9, 17) not in cal)
        for day in range(1, 17):
            self.assert_(date(2003, 9, day) in cal)
        self.assertRaises(TypeError, cal.__contains__, 'some string')


class TestPeriod(unittest.TestCase):

    def test(self):
        from schooltool.cal import Period
        dt1 = datetime(2001, 2, 3, 14, 30, 5)
        dt2 = datetime(2001, 2, 3, 16, 35, 20)
        td = dt2 - dt1
        p1 = Period(dt1, dt2)
        self.assertEquals(p1.start, dt1)
        self.assertEquals(p1.end, dt2)
        self.assertEquals(p1.duration, td)

        p2 = Period(dt1, td)
        self.assertEquals(p2.start, dt1)
        self.assertEquals(p2.end, dt2)
        self.assertEquals(p2.duration, td)

        self.assertEquals(p1, p2)

        p = Period(dt1, timedelta(0))
        self.assertEquals(p.start, dt1)
        self.assertEquals(p.end, dt1)
        self.assertEquals(p.duration, timedelta(0))

        self.assertRaises(ValueError, Period, dt2, dt1)
        self.assertRaises(ValueError, Period, dt1, -td)

    def test_overlap(self):
        from schooltool.cal import Period
        from schooltool.common import parse_datetime
        p1 = Period(parse_datetime("2004-01-01 12:00:00"),
                    timedelta(hours=1))
        p2 = Period(parse_datetime("2004-01-01 11:30:00"),
                    timedelta(hours=1))
        p3 = Period(parse_datetime("2004-01-01 12:30:00"),
                    timedelta(hours=1))
        p4 = Period(parse_datetime("2004-01-01 11:00:00"),
                    timedelta(hours=3))

        self.assert_(p1.overlaps(p2))
        self.assert_(p2.overlaps(p1))

        self.assert_(p1.overlaps(p3))
        self.assert_(p3.overlaps(p1))

        self.assert_(not p2.overlaps(p3))
        self.assert_(not p3.overlaps(p2))

        self.assert_(p1.overlaps(p4))
        self.assert_(p4.overlaps(p1))

        self.assert_(p1.overlaps(p1))


class TestVEvent(unittest.TestCase):

    def test_add(self):
        from schooltool.cal import VEvent, ICalParseError
        vevent = VEvent()
        value, params = 'bar', {'VALUE': 'TEXT'}
        vevent.add('foo', value, params)
        self.assertEquals(vevent._props, {'FOO': [(value, params)]})
        value2 = 'guug'
        vevent.add('fie', value2)
        self.assertEquals(vevent._props, {'FOO': [(value, params)],
                                          'FIE': [(value2, {})]})
        vevent.add('fie', value, params)
        self.assertEquals(vevent._props, {'FOO': [(value, params)],
                                          'FIE': [(value2, {}),
                                                  (value, params)]})

        # adding a singleton property twice
        vevent.add('uid', '1')
        self.assertRaises(ICalParseError, vevent.add, 'uid', '2')

    def test_hasProp(self):
        from schooltool.cal import VEvent
        vevent = VEvent()
        vevent.add('foo', 'bar', {})
        self.assert_(vevent.hasProp('foo'))
        self.assert_(vevent.hasProp('Foo'))
        self.assert_(not vevent.hasProp('baz'))

    def test__getType(self):
        from schooltool.cal import VEvent
        vevent = VEvent()
        vevent.add('x-explicit', '', {'VALUE': 'INTEGER'})
        vevent.add('dtstart', 'implicit type', {})
        vevent.add('x-default', '', {})
        self.assertEquals(vevent._getType('x-explicit'), 'INTEGER')
        self.assertEquals(vevent._getType('dtstart'), 'DATE-TIME')
        self.assertEquals(vevent._getType('x-default'), 'TEXT')
        self.assertEquals(vevent._getType('X-Explicit'), 'INTEGER')
        self.assertEquals(vevent._getType('DtStart'), 'DATE-TIME')
        self.assertEquals(vevent._getType('X-Default'), 'TEXT')
        self.assertRaises(KeyError, vevent._getType, 'nonexistent')

    def test_getOne(self):
        from schooltool.cal import VEvent
        vevent = VEvent()

        vevent.add('foo', 'bar', {})
        self.assertEquals(vevent.getOne('foo'), 'bar')
        self.assertEquals(vevent.getOne('Foo'), 'bar')
        self.assertEquals(vevent.getOne('baz'), None)
        self.assertEquals(vevent.getOne('baz', 'quux'), 'quux')
        self.assertEquals(vevent.getOne('dtstart', 'quux'), 'quux')

        vevent.add('int-foo', '42', {'VALUE': 'INTEGER'})
        vevent.add('int-bad', 'xyzzy', {'VALUE': 'INTEGER'})
        self.assertEquals(vevent.getOne('int-foo'), 42)
        self.assertEquals(vevent.getOne('Int-Foo'), 42)
        self.assertRaises(ValueError, vevent.getOne, 'int-bad')

        vevent.add('date-foo', '20030405', {'VALUE': 'DATE'})
        vevent.add('date-bad1', '20030405T1234', {'VALUE': 'DATE'})
        vevent.add('date-bad2', '2003', {'VALUE': 'DATE'})
        vevent.add('date-bad3', '200301XX', {'VALUE': 'DATE'})
        self.assertEquals(vevent.getOne('date-Foo'), date(2003, 4, 5))
        self.assertRaises(ValueError, vevent.getOne, 'date-bad1')
        self.assertRaises(ValueError, vevent.getOne, 'date-bad2')
        self.assertRaises(ValueError, vevent.getOne, 'date-bad3')

        vevent.add('datetime-foo1', '20030405T060708', {'VALUE': 'DATE-TIME'})
        vevent.add('datetime-foo2', '20030405T060708Z', {'VALUE': 'DATE-TIME'})
        vevent.add('datetime-bad1', '20030405T010203444444',
                                                        {'VALUE': 'DATE-TIME'})
        vevent.add('datetime-bad2', '2003', {'VALUE': 'DATE-TIME'})
        self.assertEquals(vevent.getOne('datetime-foo1'),
                          datetime(2003, 4, 5, 6, 7, 8))
        self.assertEquals(vevent.getOne('Datetime-Foo2'),
                          datetime(2003, 4, 5, 6, 7, 8))
        self.assertRaises(ValueError, vevent.getOne, 'datetime-bad1')
        self.assertRaises(ValueError, vevent.getOne, 'datetime-bad2')

        vevent.add('dur-foo1', '+P11D', {'VALUE': 'DURATION'})
        vevent.add('dur-foo2', '-P2W', {'VALUE': 'DURATION'})
        vevent.add('dur-foo3', 'P1DT2H3M4S', {'VALUE': 'DURATION'})
        vevent.add('dur-foo4', 'PT2H', {'VALUE': 'DURATION'})
        vevent.add('dur-bad1', 'xyzzy', {'VALUE': 'DURATION'})
        self.assertEquals(vevent.getOne('dur-foo1'), timedelta(days=11))
        self.assertEquals(vevent.getOne('Dur-Foo2'), -timedelta(weeks=2))
        self.assertEquals(vevent.getOne('Dur-Foo3'),
                          timedelta(days=1, hours=2, minutes=3, seconds=4))
        self.assertEquals(vevent.getOne('DUR-FOO4'), timedelta(hours=2))
        self.assertRaises(ValueError, vevent.getOne, 'dur-bad1')

        vevent.add('unknown', 'magic', {'VALUE': 'UNKNOWN-TYPE'})
        self.assertEquals(vevent.getOne('unknown'), 'magic')

    def test_iterDates(self):
        from schooltool.cal import VEvent
        vevent = VEvent()
        vevent.all_day_event = True
        vevent.dtstart = date(2003, 1, 2)
        vevent.dtend = date(2003, 1, 5)
        vevent.duration = timedelta(days=3)
        vevent.rdates = []
        vevent.exdates = []
        self.assertEquals(list(vevent.iterDates()),
                    [date(2003, 1, 2), date(2003, 1, 3), date(2003, 1, 4)])

        vevent.all_day_event = False;
        self.assertRaises(ValueError, list, vevent.iterDates())

    def test_iterDates_with_rdate_exdate(self):
        from schooltool.cal import VEvent
        vevent = VEvent()
        vevent.all_day_event = True
        vevent.dtstart = date(2003, 1, 5)
        vevent.dtend = date(2003, 1, 6)
        vevent.duration = timedelta(days=1)
        vevent.rdates = [date(2003, 1, 2), date(2003, 1, 8), date(2003, 1, 8)]
        vevent.exdates = []
        expected = [date(2003, 1, 2), date(2003, 1, 5), date(2003, 1, 8)]
        self.assertEquals(list(vevent.iterDates()), expected)

        vevent.exdates = [date(2003, 1, 6)]
        expected = [date(2003, 1, 2), date(2003, 1, 5), date(2003, 1, 8)]
        self.assertEquals(list(vevent.iterDates()), expected)

        vevent.exdates = [date(2003, 1, 2), date(2003, 1, 2)]
        expected = [date(2003, 1, 5), date(2003, 1, 8)]
        self.assertEquals(list(vevent.iterDates()), expected)

        vevent.exdates = [date(2003, 1, 5)]
        expected = [date(2003, 1, 2), date(2003, 1, 8)]
        self.assertEquals(list(vevent.iterDates()), expected)

        vevent.dtend = date(2003, 1, 7)
        vevent.duration = timedelta(days=2)
        vevent.exdates = [date(2003, 1, 5), date(2003, 1, 3)]
        expected = [date(2003, 1, 2), date(2003, 1, 3),
                    date(2003, 1, 8), date(2003, 1, 9)]
        self.assertEquals(list(vevent.iterDates()), expected)

    def test_validate_error_cases(self):
        from schooltool.cal import VEvent, ICalParseError

        vevent = VEvent()
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', 'xyzzy', {'VALUE': 'TEXT'})
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('dtend', '20010203T0000', {'VALUE': 'DATE-TIME'})
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('dtend', '20010203', {'VALUE': 'DATE'})
        vevent.add('duration', 'P1D', {})
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('duration', 'two years', {'VALUE': 'TEXT'})
        self.assertRaises(ICalParseError, vevent.validate)

    def test_validate_all_day_events(self):
        from schooltool.cal import VEvent, ICalParseError

        vevent = VEvent()
        vevent.add('summary', 'An event', {})
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.validate()
        self.assert_(vevent.all_day_event)
        self.assertEquals(vevent.summary, 'An event')
        self.assertEquals(vevent.dtend, date(2001, 2, 4))
        self.assertEquals(vevent.duration, timedelta(days=1))

        vevent = VEvent()
        vevent.add('summary', 'An\\nevent\\; with backslashes', {})
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('dtend', '20010205', {'VALUE': 'DATE'})
        vevent.validate()
        self.assertEquals(vevent.summary, 'An\nevent; with backslashes')
        self.assert_(vevent.all_day_event)
        self.assertEquals(vevent.dtstart, date(2001, 2, 3))
        self.assertEquals(vevent.dtend, date(2001, 2, 5))
        self.assertEquals(vevent.duration, timedelta(days=2))

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('duration', 'P2D')
        vevent.validate()
        self.assertEquals(vevent.summary, None)
        self.assert_(vevent.all_day_event)
        self.assertEquals(vevent.dtstart, date(2001, 2, 3))
        self.assertEquals(vevent.dtend, date(2001, 2, 5))
        self.assertEquals(vevent.duration, timedelta(days=2))

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('dtend', '20010201', {'VALUE': 'DATE'})
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', '20010203', {'VALUE': 'DATE'})
        vevent.add('dtend', '20010203', {'VALUE': 'DATE'})
        self.assertRaises(ICalParseError, vevent.validate)

    def test_validate_not_all_day_events(self):
        from schooltool.cal import VEvent, ICalParseError

        vevent = VEvent()
        vevent.add('dtstart', '20010203T040506')
        vevent.validate()
        self.assert_(not vevent.all_day_event)
        self.assertEquals(vevent.dtstart, datetime(2001, 2, 3, 4, 5, 6))
        self.assertEquals(vevent.dtend, datetime(2001, 2, 3, 4, 5, 6))
        self.assertEquals(vevent.duration, timedelta(days=0))
        self.assertEquals(vevent.rdates, [])

        vevent = VEvent()
        vevent.add('dtstart', '20010203T040000')
        vevent.add('dtend', '20010204T050102')
        vevent.validate()
        self.assert_(not vevent.all_day_event)
        self.assertEquals(vevent.dtstart, datetime(2001, 2, 3, 4, 0, 0))
        self.assertEquals(vevent.dtend, datetime(2001, 2, 4, 5, 1, 2))
        self.assertEquals(vevent.duration, timedelta(days=1, hours=1,
                                                     minutes=1, seconds=2))

        vevent = VEvent()
        vevent.add('dtstart', '20010203T040000')
        vevent.add('duration', 'P1DT1H1M2S')
        vevent.validate()
        self.assert_(not vevent.all_day_event)
        self.assertEquals(vevent.dtstart, datetime(2001, 2, 3, 4, 0, 0))
        self.assertEquals(vevent.dtend, datetime(2001, 2, 4, 5, 1, 2))
        self.assertEquals(vevent.duration, timedelta(days=1, hours=1,
                                                     minutes=1, seconds=2))

        vevent = VEvent()
        vevent.add('dtstart', '20010203T010203')
        vevent.add('dtend', '20010203T010202')
        self.assertRaises(ICalParseError, vevent.validate)

        vevent = VEvent()
        vevent.add('dtstart', '20010203T010203')
        vevent.add('rdate', '20010205T040506')
        vevent.add('exdate', '20010206T040506')
        vevent.validate()
        self.assertEquals(vevent.rdates, [datetime(2001, 2, 5, 4, 5, 6)])
        self.assertEquals(vevent.exdates, [datetime(2001, 2, 6, 4, 5, 6)])

    def test_extractListOfDates(self):
        from schooltool.cal import VEvent, Period, ICalParseError

        vevent = VEvent()
        vevent.add('rdate', '20010205T040506')
        vevent.add('rdate', '20010206T040506,20010207T000000Z')
        vevent.add('rdate', '20010208', {'VALUE': 'DATE'})
        vevent.add('rdate', '20010209T000000/20010210T000000',
                   {'VALUE': 'PERIOD'})
        rdates = vevent._extractListOfDates('RDATE', vevent.rdate_types, False)
        expected = [datetime(2001, 2, 5, 4, 5, 6),
                    datetime(2001, 2, 6, 4, 5, 6),
                    datetime(2001, 2, 7, 0, 0, 0),
                    date(2001, 2, 8),
                    Period(datetime(2001, 2, 9), datetime(2001, 2, 10)),
                   ]
        self.assertEqual(expected, rdates,
                         diff(pformat(expected), pformat(rdates)))

        vevent = VEvent()
        vevent.add('rdate', '20010205T040506', {'VALUE': 'TEXT'})
        self.assertRaises(ICalParseError, vevent._extractListOfDates, 'RDATE',
                                          vevent.rdate_types, False)

        vevent = VEvent()
        vevent.add('exdate', '20010205T040506/P1D', {'VALUE': 'PERIOD'})
        self.assertRaises(ICalParseError, vevent._extractListOfDates, 'EXDATE',
                                          vevent.exdate_types, False)

        vevent = VEvent()
        vevent.add('rdate', '20010208', {'VALUE': 'DATE'})
        rdates = vevent._extractListOfDates('RDATE', vevent.rdate_types, True)
        expected = [date(2001, 2, 8)]
        self.assertEqual(expected, rdates,
                         diff(pformat(expected), pformat(rdates)))

        vevent = VEvent()
        vevent.add('rdate', '20010205T040506', {'VALUE': 'DATE-TIME'})
        self.assertRaises(ICalParseError, vevent._extractListOfDates, 'RDATE',
                                          vevent.rdate_types, True)

        vevent = VEvent()
        vevent.add('rdate', '20010209T000000/20010210T000000',
                   {'VALUE': 'PERIOD'})
        self.assertRaises(ICalParseError, vevent._extractListOfDates, 'RDATE',
                                          vevent.rdate_types, True)


class TestICalReader(unittest.TestCase):

    example_ical = dedent("""
        BEGIN:VCALENDAR
        VERSION
         :2.0
        PRODID
         :-//Mozilla.org/NONSGML Mozilla Calendar V1.0//EN
        METHOD
         :PUBLISH
        BEGIN:VEVENT
        UID
         :956630271
        SUMMARY
         :Christmas Day
        CLASS
         :PUBLIC
        X-MOZILLA-ALARM-DEFAULT-UNITS
         :minutes
        X-MOZILLA-ALARM-DEFAULT-LENGTH
         :15
        X-MOZILLA-RECUR-DEFAULT-UNITS
         :weeks
        X-MOZILLA-RECUR-DEFAULT-INTERVAL
         :1
        DTSTART
         ;VALUE=DATE
         :20031225
        DTEND
         ;VALUE=DATE
         :20031226
        DTSTAMP
         :20020430T114937Z
        END:VEVENT
        END:VCALENDAR
        BEGIN:VCALENDAR
        VERSION
         :2.0
        PRODID
         :-//Mozilla.org/NONSGML Mozilla Calendar V1.0//EN
        METHOD
         :PUBLISH
        BEGIN:VEVENT
        UID
         :911737808
        SUMMARY
         :Boxing Day
        CLASS
         :PUBLIC
        X-MOZILLA-ALARM-DEFAULT-UNITS
         :minutes
        X-MOZILLA-ALARM-DEFAULT-LENGTH
         :15
        X-MOZILLA-RECUR-DEFAULT-UNITS
         :weeks
        X-MOZILLA-RECUR-DEFAULT-INTERVAL
         :1
        DTSTART
         ;VALUE=DATE
         :20030501
        DTSTAMP
         :20020430T114937Z
        END:VEVENT
        BEGIN:VEVENT
        DTSTART;VALUE=DATE:20031225
        SUMMARY:Christmas again!
        END:VEVENT
        END:VCALENDAR
        """)

    def test_markNonSchooldays(self):
        from schooltool.cal import ICalReader, SchooldayModel
        from schooltool.cal import markNonSchooldays
        cal = SchooldayModel(date(2003, 9, 01), date(2004, 01, 01))
        file = StringIO(self.example_ical)
        reader = ICalReader(file)
        cal.addWeekdays(0, 1, 2, 3, 4)
        self.assert_(cal.isSchoolday(date(2003, 12, 24)))
        self.assert_(cal.isSchoolday(date(2003, 12, 25)))
        self.assert_(cal.isSchoolday(date(2003, 12, 26)))
        markNonSchooldays(reader, cal)
        self.assert_(cal.isSchoolday(date(2003, 12, 24)))
        self.assert_(not cal.isSchoolday(date(2003, 12, 25)))
        self.assert_(cal.isSchoolday(date(2003, 12, 26)))

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    BEGIN:VEVENT
                    DTSTART:20030902T124500
                    DURATION:PT0H15M
                    SUMMARY:Nap
                    END:VEVENT
                    END:VCALENDAR
                    """)))
        markNonSchooldays(reader, cal)
        self.assert_(cal.isSchoolday(date(2003, 9, 2)))

    def test_iterEvents(self):
        from schooltool.cal import ICalReader, ICalParseError
        file = StringIO(self.example_ical)
        reader = ICalReader(file)
        result = list(reader.iterEvents())
        self.assertEqual(len(result), 3)
        vevent = result[0]
        self.assertEqual(vevent.getOne('x-mozilla-recur-default-units'),
                         'weeks')
        self.assertEqual(vevent.getOne('dtstart'), date(2003, 12, 25))
        self.assertEqual(vevent.dtstart, date(2003, 12, 25))
        self.assertEqual(vevent.getOne('dtend'), date(2003, 12, 26))
        self.assertEqual(vevent.dtend, date(2003, 12, 26))
        vevent = result[1]
        self.assertEqual(vevent.getOne('dtstart'), date(2003, 05, 01))
        self.assertEqual(vevent.dtstart, date(2003, 05, 01))
        vevent = result[2]
        self.assertEqual(vevent.getOne('dtstart'), date(2003, 12, 25))
        self.assertEqual(vevent.dtstart, date(2003, 12, 25))

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    BEGIN:VEVENT
                    DTSTART;VALUE=DATE:20010203
                    BEGIN:VALARM
                    X-PROP:foo
                    END:VALARM
                    END:VEVENT
                    END:VCALENDAR
                    """)))
        result = list(reader.iterEvents())
        self.assertEquals(len(result), 1)
        vevent = result[0]
        self.assert_(vevent.hasProp('dtstart'))
        self.assert_(not vevent.hasProp('x-prop'))

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    BEGIN:VEVENT
                    DTSTART;VALUE=DATE:20010203
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    BEGIN:VEVENT
                    DTSTART;VALUE=DATE:20010203
                    END:VCALENDAR
                    END:VEVENT
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    END:VCALENDAR
                    X-PROP:foo
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    END:VCALENDAR
                    BEGIN:VEVENT
                    END:VEVENT
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    BEGIN:VCALENDAR
                    BEGIN:VEVENT
                    DTSTART;VALUE=DATE:20010203
                    END:VEVENT
                    END:VCALENDAR
                    END:UNIVERSE
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    DTSTART;VALUE=DATE:20010203
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(dedent("""
                    This is just plain text
                    """)))
        self.assertRaises(ICalParseError, list, reader.iterEvents())

        reader = ICalReader(StringIO(""))
        self.assertEquals(list(reader.iterEvents()), [])

    def test_iterRow(self):
        from schooltool.cal import ICalReader
        file = StringIO("key1\n"
                        " :value1\n"
                        "key2\n"
                        " ;VALUE=foo\n"
                        " :value2\n"
                        "key3;VALUE=bar:value3\n")
        reader = ICalReader(file)
        self.assertEqual(list(reader._iterRow()),
                         [('KEY1', 'value1', {}),
                          ('KEY2', 'value2', {'VALUE': 'FOO'}),
                          ('KEY3', 'value3', {'VALUE': 'BAR'})])

        file = StringIO("key1:value1\n"
                        "key2;VALUE=foo:value2\n"
                        "key3;VALUE=bar:value3\n")
        reader = ICalReader(file)
        self.assertEqual(list(reader._iterRow()),
                         [('KEY1', 'value1', {}),
                          ('KEY2', 'value2', {'VALUE': 'FOO'}),
                          ('KEY3', 'value3', {'VALUE': 'BAR'})])

        file = StringIO("key1:value:with:colons:in:it\n")
        reader = ICalReader(file)
        self.assertEqual(list(reader._iterRow()),
                         [('KEY1', 'value:with:colons:in:it', {})])

        reader = ICalReader(StringIO("ke\r\n y1\n\t:value\r\n  1 \r\n ."))
        self.assertEqual(list(reader._iterRow()),
                         [('KEY1', 'value 1 .', {})])

    def test_parseRow(self):
        from schooltool.cal import ICalReader, ICalParseError
        parseRow = ICalReader._parseRow
        self.assertEqual(parseRow("key:"), ("KEY", "", {}))
        self.assertEqual(parseRow("key:value"), ("KEY", "value", {}))
        self.assertEqual(parseRow("key:va:lu:e"), ("KEY", "va:lu:e", {}))
        self.assertRaises(ICalParseError, parseRow, "key but no value")
        self.assertRaises(ICalParseError, parseRow, ":value but no key")
        self.assertRaises(ICalParseError, parseRow, "bad name:")

        self.assertEqual(parseRow("key;param=:value"),
                         ("KEY", "value", {'PARAM': ''}))
        self.assertEqual(parseRow("key;param=pvalue:value"),
                         ("KEY", "value", {'PARAM': 'PVALUE'}))
        self.assertEqual(parseRow('key;param=pvalue;param2=value2:value'),
                         ("KEY", "value", {'PARAM': 'PVALUE',
                                           'PARAM2': 'VALUE2'}))
        self.assertEqual(parseRow('key;param="pvalue":value'),
                         ("KEY", "value", {'PARAM': 'pvalue'}))
        self.assertEqual(parseRow('key;param=pvalue;param2="value2":value'),
                         ("KEY", "value", {'PARAM': 'PVALUE',
                                           'PARAM2': 'value2'}))
        self.assertRaises(ICalParseError, parseRow, "k;:no param")
        self.assertRaises(ICalParseError, parseRow, "k;a?=b:bad param")
        self.assertRaises(ICalParseError, parseRow, "k;a=\":bad param")
        self.assertRaises(ICalParseError, parseRow, "k;a=\"\177:bad param")
        self.assertRaises(ICalParseError, parseRow, "k;a=\001:bad char")
        self.assertEqual(parseRow("key;param=a,b,c:value"),
                         ("KEY", "value", {'PARAM': ['A', 'B', 'C']}))
        self.assertEqual(parseRow('key;param=a,"b,c",d:value'),
                         ("KEY", "value", {'PARAM': ['A', 'b,c', 'D']}))


class TestDateRange(unittest.TestCase):

    def test(self):
        from schooltool.cal import DateRange
        from schooltool.interfaces import IDateRange

        dr = DateRange(date(2003, 1, 1), date(2003, 1, 31))
        verifyObject(IDateRange, dr)

        # __contains__
        self.assert_(date(2002, 12, 31) not in dr)
        self.assert_(date(2003, 2, 1) not in dr)
        for day in range(1, 32):
            self.assert_(date(2003, 1, day) in dr)

        # __iter__
        days = list(dr)
        self.assertEqual(len(days), 31)
        self.assertEqual(len(dr), 31)

        days = DateRange(date(2003, 1, 1), date(2003, 1, 2))
        self.assertEqual(list(days), [date(2003, 1, 1), date(2003, 1, 2)])

        days = DateRange(date(2003, 1, 1), date(2003, 1, 1))
        self.assertEqual(list(days), [date(2003, 1, 1)])

        self.assertRaises(ValueError, DateRange,
                          date(2003, 1, 2), date(2003, 1, 1))


class TestCalendar(unittest.TestCase, EqualsSortedMixin):

    def test(self):
        from schooltool.cal import Calendar
        from schooltool.interfaces import ICalendar, ICalendarWrite, ILocation
        cal = Calendar()
        verifyObject(ICalendar, cal)
        verifyObject(ICalendarWrite, cal)
        verifyObject(ILocation, cal)

    def test_iter(self):
        from schooltool.cal import Calendar
        from schooltool.cal import CalendarEvent

        cal = Calendar()
        self.assertEqual(list(cal), [])

        ev1 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(minutes=10),
                            "English")

        cal.addEvent(ev1)
        self.assertEqual(list(cal), [ev1])

    def makeCal(self, events):
        from schooltool.cal import Calendar
        cal = Calendar()
        for event in events:
            cal.addEvent(event)
        return cal

    def test_byDate(self):
        from schooltool.cal import CalendarEvent

        ev1 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(minutes=10),
                            "English")
        ev2 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "Latin")
        ev3 = CalendarEvent(datetime(2003, 11, 26, 10, 0),
                            timedelta(minutes=10),
                            "German")

        cal = self.makeCal([ev1, ev2, ev3])
        self.assertEqual(list(cal.byDate(date(2003, 11, 26))), [ev3])

        # event end date within the period
        ev4 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(1),
                            "Solar eclipse")
        cal = self.makeCal([ev1, ev2, ev3, ev4])
        self.assertEqualSorted(list(cal.byDate(date(2003, 11, 26))),
                               [ev3, ev4])

        # calendar daterange is within the event period
        ev4 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(2),
                            "Solar eclipse")
        cal = self.makeCal([ev1, ev2, ev3, ev4])
        self.assertEqualSorted(list(cal.byDate(date(2003, 11, 26))),
                               [ev3, ev4])

        # only the event start date falls within the period
        ev4 = CalendarEvent(datetime(2003, 11, 26, 10, 0),
                            timedelta(2),
                            "Solar eclipse")
        cal = self.makeCal([ev1, ev2, ev3, ev4])
        self.assertEqualSorted(list(cal.byDate(date(2003, 11, 26))),
                               [ev3, ev4])

        # the event is after the period
        ev4 = CalendarEvent(datetime(2003, 11, 27, 10, 0),
                            timedelta(2),
                            "Solar eclipse")
        cal = self.makeCal([ev1, ev2, ev3, ev4])
        self.assertEqualSorted(list(cal.byDate(date(2003, 11, 26))),
                               [ev3])

    def test_clear(self):
        from schooltool.cal import CalendarEvent
        ev1 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(minutes=10),
                            "English")
        ev2 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "Latin")
        cal = self.makeCal([ev1, ev2])
        cal.clear()
        self.assertEquals(list(cal), [])

    def test_removeEvent(self):
        from schooltool.cal import CalendarEvent
        ev1 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(minutes=10),
                            "English")
        ev2 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "Latin")
        cal = self.makeCal([ev1, ev2])
        cal.removeEvent(CalendarEvent(datetime(2003, 11, 25, 10, 0),
                                      timedelta(minutes=10),
                                      "English"))
        self.assertEquals(list(cal), [ev2])

    def test_update(self):
        from schooltool.cal import CalendarEvent
        ev1 = CalendarEvent(datetime(2003, 11, 25, 10, 0),
                            timedelta(minutes=10),
                            "English")
        ev2 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "Latin")
        ev3 = CalendarEvent(datetime(2003, 11, 26, 10, 0),
                            timedelta(minutes=10),
                            "German")
        cal = self.makeCal([ev1, ev2])
        cal.update(self.makeCal([ev2, ev3]))
        self.assertEquals(sorted(list(cal)), sorted([ev1, ev2, ev3]))


class TestCalendarPersistence(unittest.TestCase):
    """A functional test for timetables persistence."""

    def setUp(self):
        from ZODB.DB import DB
        from ZODB.MappingStorage import MappingStorage
        self.db = DB(MappingStorage())
        self.datamgr = self.db.open()

    def test_SchooldayModel(self):
        from schooltool.cal import SchooldayModel
        from transaction import get_transaction
        sm = SchooldayModel(date(2003, 9, 1), date(2003, 9, 30))
        self.datamgr.root()['sm'] = sm
        get_transaction().commit()

        d1 = date(2003, 9, 15)
        d2 = date(2003, 9, 16)
        sm.add(d1)
        sm.add(d2)
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            sm2 = datamgr.root()['sm']
            self.assert_(sm2.isSchoolday(d1))
            self.assert_(sm2.isSchoolday(d2))
        finally:
            get_transaction().abort()
            datamgr.close()

        sm.remove(d1)
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            sm2 = datamgr.root()['sm']
            self.assert_(not sm2.isSchoolday(d1))
            self.assert_(sm2.isSchoolday(d2))
        finally:
            get_transaction().abort()
            datamgr.close()

        sm.reset(date(2003, 9, 1), date(2003, 9, 30))
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            sm2 = datamgr.root()['sm']
            self.assert_(not sm2.isSchoolday(d1))
            self.assert_(not sm2.isSchoolday(d2))
        finally:
            get_transaction().abort()
            datamgr.close()

    def test_Calendar(self):
        from schooltool.cal import Calendar, CalendarEvent
        from transaction import get_transaction
        cal = Calendar()
        self.datamgr.root()['cal'] = cal
        get_transaction().commit()

        e = CalendarEvent(datetime(2001, 2, 3, 4, 5, 6), timedelta(1), "xyzzy")
        cal.addEvent(e)
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            cal2 = datamgr.root()['cal']
            self.assertEquals(list(cal2), [e])
        finally:
            get_transaction().abort()
            datamgr.close()

        cal.clear()
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            cal2 = datamgr.root()['cal']
            self.assertEquals(list(cal2), [])
        finally:
            get_transaction().abort()
            datamgr.close()

        cal3 = Calendar()
        cal3.addEvent(e)
        cal.update(cal3)
        get_transaction().commit()

        try:
            datamgr = self.db.open()
            cal2 = datamgr.root()['cal']
            self.assertEquals(list(cal2), [e])
        finally:
            get_transaction().abort()
            datamgr.close()


class TestCalendarEvent(unittest.TestCase):

    def test(self):
        from schooltool.cal import CalendarEvent
        from schooltool.interfaces import ICalendarEvent

        owner = object()
        context = object()

        ce = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                           timedelta(minutes=10),
                           "reality check")
        verifyObject(ICalendarEvent, ce)
        self.assert_(ce.unique_id)

        ce_ = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "reality check",
                            unique_id="I am unique",
                            location="PoV")
        self.assertEquals(ce_.unique_id, "I am unique")
        self.assertEquals(ce_.location, "PoV")

        ce1 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "reality check")
        ce2 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "realty check")
        ce3 = CalendarEvent(datetime(2003, 11, 25, 12, 1),
                            timedelta(minutes=10),
                            "reality check")
        ce4 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=11),
                            "reality check")
        ce5 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "reality check", owner=owner)
        ce6 = CalendarEvent(datetime(2003, 11, 25, 12, 0),
                            timedelta(minutes=10),
                            "reality check", owner=owner,
                            context=context)
        self.assertEquals(ce, ce1)
        self.assertNotEquals(ce, ce2)
        self.assertNotEquals(ce, ce3)
        self.assertNotEquals(ce, ce4)
        self.assertNotEquals(ce, ce5)
        self.assertNotEquals(ce5, ce6)
        self.assertRaises(AttributeError, setattr, ce, 'dtstart', 'not-ro')
        self.assertRaises(AttributeError, setattr, ce, 'duration', 'not-ro')
        self.assertRaises(AttributeError, setattr, ce, 'title', 'not-ro')
        self.assertRaises(AttributeError, setattr, ce, 'owner', 'not-ro')
        self.assertRaises(AttributeError, setattr, ce, 'context', 'not-ro')
        self.assertRaises(AttributeError, setattr, ce, 'location', 'not-ro')


class TestCalendarOwnerMixin(unittest.TestCase):

    def test(self):
        from schooltool.cal import CalendarOwnerMixin
        from schooltool.interfaces import ICalendarOwner
        com = CalendarOwnerMixin()
        verifyObject(ICalendarOwner, com)
        self.assert_(com.calendar.__parent__ is com)
        self.assertEquals(com.calendar.__name__, 'calendar')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(DocTestSuite('schooltool.cal'))
    suite.addTest(unittest.makeSuite(TestDateRange))
    suite.addTest(unittest.makeSuite(TestSchooldayModel))
    suite.addTest(unittest.makeSuite(TestPeriod))
    suite.addTest(unittest.makeSuite(TestVEvent))
    suite.addTest(unittest.makeSuite(TestICalReader))
    suite.addTest(unittest.makeSuite(TestCalendar))
    suite.addTest(unittest.makeSuite(TestCalendarPersistence))
    suite.addTest(unittest.makeSuite(TestCalendarEvent))
    suite.addTest(unittest.makeSuite(TestCalendarOwnerMixin))
    return suite
