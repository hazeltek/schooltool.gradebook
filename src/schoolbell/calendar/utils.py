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
Utility functions for SchoolBell calendaring.

These include various date manipulation routines.

$Id$
"""

import re
import calendar
from datetime import date, datetime, timedelta, time

from pytz import timezone

utc = timezone("UTC")


def prev_month(date):
    """Calculate the first day of the previous month for a given date.

        >>> prev_month(date(2004, 8, 1))
        datetime.date(2004, 7, 1)
        >>> prev_month(date(2004, 8, 31))
        datetime.date(2004, 7, 1)
        >>> prev_month(date(2004, 12, 15))
        datetime.date(2004, 11, 1)
        >>> prev_month(date(2005, 1, 28))
        datetime.date(2004, 12, 1)

    """
    return (date.replace(day=1) - timedelta(1)).replace(day=1)


def next_month(date):
    """Calculate the first day of the next month for a given date.

        >>> next_month(date(2004, 8, 1))
        datetime.date(2004, 9, 1)
        >>> next_month(date(2004, 8, 31))
        datetime.date(2004, 9, 1)
        >>> next_month(date(2004, 12, 15))
        datetime.date(2005, 1, 1)
        >>> next_month(date(2004, 2, 28))
        datetime.date(2004, 3, 1)
        >>> next_month(date(2004, 2, 29))
        datetime.date(2004, 3, 1)
        >>> next_month(date(2005, 2, 28))
        datetime.date(2005, 3, 1)

    """
    return (date.replace(day=28) + timedelta(7)).replace(day=1)


def week_start(date, first_day_of_week=0):
    """Calculate the first day of the week for a given date.

    Assuming that week starts on Mondays:

        >>> week_start(date(2004, 8, 19))
        datetime.date(2004, 8, 16)
        >>> week_start(date(2004, 8, 15))
        datetime.date(2004, 8, 9)
        >>> week_start(date(2004, 8, 14))
        datetime.date(2004, 8, 9)
        >>> week_start(date(2004, 8, 21))
        datetime.date(2004, 8, 16)
        >>> week_start(date(2004, 8, 22))
        datetime.date(2004, 8, 16)
        >>> week_start(date(2004, 8, 23))
        datetime.date(2004, 8, 23)

    Assuming that week starts on Sundays:

        >>> import calendar
        >>> week_start(date(2004, 8, 19), calendar.SUNDAY)
        datetime.date(2004, 8, 15)
        >>> week_start(date(2004, 8, 15), calendar.SUNDAY)
        datetime.date(2004, 8, 15)
        >>> week_start(date(2004, 8, 14), calendar.SUNDAY)
        datetime.date(2004, 8, 8)
        >>> week_start(date(2004, 8, 21), calendar.SUNDAY)
        datetime.date(2004, 8, 15)
        >>> week_start(date(2004, 8, 22), calendar.SUNDAY)
        datetime.date(2004, 8, 22)
        >>> week_start(date(2004, 8, 23), calendar.SUNDAY)
        datetime.date(2004, 8, 22)

    """
    assert 0 <= first_day_of_week < 7
    delta = date.weekday() - first_day_of_week
    if delta < 0:
        delta += 7
    return date - timedelta(delta)


def weeknum_bounds(year, weeknum):
    """Calculate the inclusive date bounds for a (year, weeknum) tuple.

    Week numbers are as defined in ISO 8601 and returned by
    datetime.date.isocalendar().

        >>> weeknum_bounds(2003, 52)
        (datetime.date(2003, 12, 22), datetime.date(2003, 12, 28))
        >>> weeknum_bounds(2004, 1)
        (datetime.date(2003, 12, 29), datetime.date(2004, 1, 4))
        >>> weeknum_bounds(2004, 2)
        (datetime.date(2004, 1, 5), datetime.date(2004, 1, 11))

    """
    # The first week of a year is at least 4 days long, so January 4th
    # is in the first week.
    firstweek = week_start(date(year, 1, 4), calendar.MONDAY)
    # move forward to the right week number
    weekstart = firstweek + timedelta(weeks=weeknum-1)
    weekend = weekstart + timedelta(days=6)
    return (weekstart, weekend)


def check_weeknum(year, weeknum):
    """Check to see whether a (year, weeknum) tuple refers to a real
    ISO week number.

        >>> check_weeknum(2004, 1)
        True
        >>> check_weeknum(2004, 53)
        True
        >>> check_weeknum(2004, 0)
        False
        >>> check_weeknum(2004, 54)
        False
        >>> check_weeknum(2003, 52)
        True
        >>> check_weeknum(2003, 53)
        False

    """
    weekstart, weekend = weeknum_bounds(year, weeknum)
    isoyear, isoweek, isoday = weekstart.isocalendar()
    return (year, weeknum) == (isoyear, isoweek)


def parse_date(value):
    """Parse a ISO-8601 YYYY-MM-DD date value.

    Examples:

        >>> parse_date('2003-09-01')
        datetime.date(2003, 9, 1)
        >>> parse_date('20030901')
        Traceback (most recent call last):
          ...
        ValueError: Invalid date: '20030901'
        >>> parse_date('2003-IX-01')
        Traceback (most recent call last):
          ...
        ValueError: Invalid date: '2003-IX-01'
        >>> parse_date('2003-09-31')
        Traceback (most recent call last):
          ...
        ValueError: Invalid date: '2003-09-31'
        >>> parse_date('2003-09-30-15-42')
        Traceback (most recent call last):
          ...
        ValueError: Invalid date: '2003-09-30-15-42'

    """
    try:
        y, m, d = map(int, value.split('-'))
        return date(y, m, d)
    except ValueError:
        raise ValueError("Invalid date: %r" % value)


def parse_datetime(s):
    """Parse a ISO 8601 date/time value.

    Only a small subset of ISO 8601 is accepted:

      YYYY-MM-DD HH:MM:SS
      YYYY-MM-DD HH:MM:SS.ssssss
      YYYY-MM-DDTHH:MM:SS
      YYYY-MM-DDTHH:MM:SS.ssssss

    Returns a datetime.datetime object without a time zone.

    Examples:

        >>> parse_datetime('2003-04-05 11:22:33.456789')
        datetime.datetime(2003, 4, 5, 11, 22, 33, 456789)

        >>> parse_datetime('2003-04-05 11:22:33.456')
        datetime.datetime(2003, 4, 5, 11, 22, 33, 456000)

        >>> parse_datetime('2003-04-05 11:22:33.45678999')
        datetime.datetime(2003, 4, 5, 11, 22, 33, 456789)

        >>> parse_datetime('01/02/03')
        Traceback (most recent call last):
          ...
        ValueError: Bad datetime: 01/02/03

    """
    m = re.match(r"(\d+)-(\d+)-(\d+)[ T](\d+):(\d+):(\d+)([.](\d+))?$", s)
    if not m:
        raise ValueError("Bad datetime: %s" % s)
    ssssss = m.groups()[7]
    if ssssss:
        ssssss = int((ssssss + "00000")[:6])
    else:
        ssssss = 0
    y, m, d, hh, mm, ss = map(int, m.groups()[:6])
    return datetime(y, m, d, hh, mm, ss, ssssss)


def parse_time(s):
    """Parse a ISO 8601 time value.

    Only a small subset of ISO 8601 is accepted:

      HH:MM
      HH:MM:SS

    Returns a datetime.time object without a time zone.

    Examples:

        >>> parse_time('11:22:33')
        datetime.time(11, 22, 33)

        >>> parse_time('11:22')
        datetime.time(11, 22)

        >>> parse_time('11:66')
        Traceback (most recent call last):
          ...
        ValueError: minute must be in 0..59

    """
    parts = s.split(":")
    hh, mm = map(int, parts[:2])
    ss = 0
    if len(parts) > 2:
        ss = int(parts[2])
    return time(hh, mm, ss)


def parse_timetz(s, tz=utc):
    """Timezone aware time parser.

    If no timezone preference is given, default to UTC.

        >>> t1 = parse_timetz('11:22:33')
        >>> t1.hour
        11
        >>> t1.minute
        22
        >>> t1.second
        33
        >>> t1.tzname()
        'UTC'

        >>> t2 = parse_timetz('11:22')
        >>> t2.hour
        11
        >>> t2.minute
        22
        >>> t2.second
        0
        >>> t2.tzname()
        'UTC'

        >>> eastern = timezone('US/Eastern')
        >>> teastern = parse_timetz('11:22', tz=eastern)
        >>> teastern.tzname()
        'EST'

        >>> parse_timetz('11:66')
        Traceback (most recent call last):
          ...
        ValueError: minute must be in 0..59


    """
    parts = s.split(":")
    hh, mm = map(int, parts[:2])
    ss = 0
    if len(parts) > 2:
        ss = int(parts[2])
    return time(hh, mm, ss, tzinfo=tz)

