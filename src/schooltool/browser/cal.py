#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2004 Shuttleworth Foundation
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
Browser views for calendaring.

$Id$
"""

import itertools
import urllib
import calendar
from datetime import datetime, date, time, timedelta

from zope.app.traversing.api import traverse, getPath

from schooltool.browser import View, Template, absoluteURL, absolutePath
from schooltool.browser import AppObjectBreadcrumbsMixin
from schooltool.browser import Unauthorized
from schooltool.browser.auth import AuthenticatedAccess, PublicAccess
from schooltool.browser.auth import ACLViewAccess, ACLModifyAccess
from schooltool.browser.auth import ACLAddAccess
from schooltool.browser.auth import isManager
from schooltool.browser.acl import ACLView
from schooltool.auth import getACL
from schooltool.cal import CalendarEvent, DailyRecurrenceRule
from schooltool.cal import WeeklyRecurrenceRule, MonthlyRecurrenceRule
from schooltool.cal import YearlyRecurrenceRule
from schooltool.icalendar import Period
from schooltool.common import to_unicode, parse_date
from schooltool.component import getRelatedObjects
from schooltool.component import getOptions, relate
from schooltool.interfaces import IResource, ICalendar, ICalendarEvent
from schooltool.interfaces import ITimetableCalendarEvent
from schooltool.interfaces import IExceptionalTTCalendarEvent
from schooltool.interfaces import IInheritedCalendarEvent
from schooltool.interfaces import ModifyPermission
from schooltool.interfaces import IDailyRecurrenceRule, IWeeklyRecurrenceRule
from schooltool.interfaces import IYearlyRecurrenceRule, IMonthlyRecurrenceRule
from schooltool.timetable import TimetableException, ExceptionalTTCalendarEvent
from schooltool.timetable import getPeriodsForDay
from schooltool.translation import ugettext as _, TranslatableString
from schooltool.uris import URIMember, URIGroup, URICalendarListed
from schooltool.uris import URICalendarProvider
from schooltool.uris import URICalendarSubscription, URICalendarSubscriber
from schooltool.browser.widgets import TextWidget, SelectionWidget
from schooltool.browser.widgets import SequenceWidget
from schooltool.browser.widgets import TextAreaWidget, CheckboxWidget
from schooltool.browser.widgets import dateParser, timeParser, intParser
from schooltool.browser.widgets import timeFormatter

__metaclass__ = type


class BookingView(View, AppObjectBreadcrumbsMixin):

    __used_for__ = IResource

    authorization = AuthenticatedAccess

    template = Template('www/booking.pt')

    error = u""

    booked = False

    def __init__(self, context):
        View.__init__(self, context)
        # self.owner_widget created in do_GET()
        self.date_widget = TextWidget('start_date', _('Date'),
                                      parser=dateParser)
        self.time_widget = TextWidget('start_time', _('Time'),
                                      parser=timeParser,
                                      formatter=timeFormatter)
        self.duration_widget = TextWidget('duration', _('Duration'),
                                          unit=_('min.'),
                                          parser=intParser,
                                          validator=durationValidator,
                                          value=30)

    def listPersons(self):
        person_container = traverse(self.context, '/persons')
        persons = [(person.title, person)
                   for person in person_container.itervalues()
                   if self.request.security.canBook(person, self.context)]
        persons.sort()
        return [(person, title) for title, person in persons]

    def parse_owner(self, raw_value):
        if not raw_value:
            return None
        persons = traverse(self.context, '/persons')
        try:
            return persons[raw_value]
        except KeyError:
            raise ValueError(_("This user does not exist."))

    def format_owner(self, value):
        if value is None:
            return None
        return value.__name__

    def do_GET(self, request):
        people = self.listPersons()
        self.owner_widget = SelectionWidget('owner', _('Owner'), people,
                                            parser=self.parse_owner,
                                            formatter=self.format_owner)
        self.update()
        return View.do_GET(self, request)

    def update(self):
        request = self.request
        self.owner_widget.update(request)
        self.date_widget.update(request)
        self.time_widget.update(request)
        self.duration_widget.update(request)

        if 'CONFIRM_BOOK' not in request.args:
            # just set the initial values
            self.owner_widget.setValue(request.authenticated_user)
            return

        assert 'CONFIRM_BOOK' in request.args

        if self.isManager():
            self.owner_widget.require()
        self.date_widget.require()
        self.time_widget.require()
        self.duration_widget.require()
        errors = (self.owner_widget.error or self.date_widget.error or
                  self.time_widget.error or self.duration_widget.error)
        if errors:
            return

        start = datetime.combine(self.date_widget.value,
                                 self.time_widget.value)
        duration = timedelta(minutes=self.duration_widget.value)
        force = 'conflicts' in request.args
        if self.isManager():
            owner = self.owner_widget.value
        else:
            owner = request.authenticated_user
        self.booked = self.book(owner, start, duration, force=force)

    def book(self, owner, start, duration, force=False):
        if not force:
            p = Period(start, duration)
            for e in self.context.calendar:
                if p.overlaps(Period(e.dtstart, e.duration)):
                    self.error = _("The resource is busy"
                                   " at the specified time.")
                    return False
        if not self.request.security.canBook(owner, self.context):
            self.error = _("Sorry, you don't have permissions to book this"
                           " resource")
            return False

        title = _('%s booked by %s') % (self.context.title, owner.title)
        ev = CalendarEvent(start, duration, title, owner, self.context)
        self.context.calendar.addEvent(ev)
        owner.calendar.addEvent(ev)
        self.request.appLog(_("%s (%s) booked by %s (%s) at %s for %s") %
                            (getPath(self.context), self.context.title,
                             getPath(owner), owner.title, start, duration))
        return True


class BookingViewPopUp(BookingView):
    """Frameless BookingView"""

    template = Template('www/booking-popup.pt')


class CalendarDay:
    """A single day in a calendar.

    Attributes:
       'date'   -- date of the day (a datetime.date instance)
       'events' -- list of events that took place that day, sorted by start
                   time (in ascending order).

    """

    def __init__(self, date, events=None):
        self.date = date
        if events is None:
            self.events = []
        else:
            self.events = events

    def __cmp__(self, other):
        return cmp(self.date, other.date)


class CalendarBreadcrumbsMixin(AppObjectBreadcrumbsMixin):

    def breadcrumbs(self):
        owner = self.context.__parent__
        breadcrumbs = AppObjectBreadcrumbsMixin.breadcrumbs(self,
                                                            context=owner)
        breadcrumbs.append((_('Calendar'),
                            absoluteURL(self.request, owner, 'calendar')))
        return breadcrumbs


class CalendarViewBase(View, CalendarBreadcrumbsMixin):

    __used_for__ = ICalendar

    authorization = ACLViewAccess

    # Which day is considered to be the first day of the week (0 = Monday,
    # 6 = Sunday).  Currently hardcoded.  A similar value is also hardcoded
    # in schooltool.browser.timetable.
    first_day_of_week = 0

    _ = TranslatableString  # postpone translations

    month_names = {
        1: _("January"),
        2: _("February"),
        3: _("March"),
        4: _("April"),
        5: _("May"),
        6: _("June"),
        7: _("July"),
        8: _("August"),
        9: _("September"),
        10: _("October"),
        11: _("November"),
        12: _("December"),
    }

    day_of_week_names = {
        0: _("Monday"),
        1: _("Tuesday"),
        2: _("Wednesday"),
        3: _("Thursday"),
        4: _("Friday"),
        5: _("Saturday"),
        6: _("Sunday"),
    }

    short_day_of_week_names = {
        0: _("Mon"),
        1: _("Tue"),
        2: _("Wed"),
        3: _("Thu"),
        4: _("Fri"),
        5: _("Sat"),
        6: _("Sun"),
    }

    del _ # go back to immediate translations

    __url = None

    def _eventView(self, event):
        return CalendarEventView(event, self.context)

    def eventClass(self, event):
        return self._eventView(event).cssClass()

    def renderEvent(self, event, date):
        return self._eventView(event).full(self.request, date)

    def eventShort(self, event):
        return self._eventView(event).short(self.request)

    def eventHidden(self, event):
        view = self._eventView(event)
        view.request = self.request
        return view.isHidden()

    def update(self):
        if 'date' not in self.request.args:
            self.cursor = date.today()
        else:
            self.cursor = parse_date(self.request.args['date'][0])

    def calURL(self, cal_type, cursor=None):
        if cursor is None:
            cursor = self.cursor
        if self.__url is None:
            self.__url = absoluteURL(self.request, self.context)
        return  '%s/%s.html?date=%s' % (self.__url, cal_type, cursor)

    def iterEvents(self, first, last):
        """Iterate over events of selected calendars.

        Currently the personal calendar, the timetable calendar and the
        composite calendar is scanned.
        """
        private_cal = self.context.expand(first, last)
        owner = self.context.__parent__
        timetable_cal = owner.makeTimetableCalendar()
        composite_cal = owner.makeCompositeCalendar(first, last)
        return itertools.chain(private_cal, timetable_cal, composite_cal)

    def getDays(self, start, end):
        """Get a list of CalendarDay objects for a selected period of time.

        `start` and `end` (date objects) are bounds (half-open) for the result.

        Events spanning more than one day get included in all days they
        overlap.
        """
        events = {}
        day = start
        while day < end:
            events[day] = []
            day += timedelta(1)

        for event in self.iterEvents(start, end):
            if self.eventHidden(event):
                continue
            #  day1  day2  day3  day4  day5
            # |.....|.....|.....|.....|.....|
            # |     |  [-- event --)  |     |
            # |     |  ^  |     |  ^  |     |
            # |     |  `dtstart |  `dtend   |
            #        ^^^^^       ^^^^^
            #      first_day   last_day
            #
            # dtstart and dtend are datetime.datetime instances and point to
            # time instants.  first_day and last_day are datetime.date
            # instances and point to whole days.  Also note that [dtstart,
            # dtend) is a half-open interval, therefore
            #   last_day == dtend.date() - 1 day   when dtend.time() is 00:00
            #                                      and duration > 0
            #               dtend.date()           otherwise
            dtend = event.dtstart + event.duration
            first_day = event.dtstart.date()
            last_day = max(first_day, (dtend - dtend.resolution).date())
            # Loop through the intersection of two day ranges:
            #    [start, end) intersect [first_day, last_day]
            # Note that the first interval is half-open, but the second one is
            # closed.  Since we're dealing with whole days,
            #    [first_day, last_day] == [first_day, last_day + 1 day)
            day = max(start, first_day)
            limit = min(end, last_day + timedelta(1))
            while day < limit:
                events[day].append(event)
                day += timedelta(1)

        days = []
        day = start
        while day < end:
            events[day].sort()
            days.append(CalendarDay(day, events[day]))
            day += timedelta(1)
        return days

    def getWeek(self, dt):
        """Return the week that contains the day dt.

        Returns a list of CalendarDay objects.
        """
        start = week_start(dt, self.first_day_of_week)
        end = start + timedelta(7)
        return self.getDays(start, end)

    def getMonth(self, dt):
        """Return a nested list of days in the month that contains dt.

        Returns a list of lists of date objects.  Days in neighbouring
        months are included if they fall into a week that contains days in
        the current month.
        """
        weeks = []
        start_of_next_month = next_month(dt)
        start_of_week = week_start(dt.replace(day=1), self.first_day_of_week)
        while start_of_week < start_of_next_month:
            start_of_next_week = start_of_week + timedelta(7)
            weeks.append(self.getDays(start_of_week, start_of_next_week))
            start_of_week = start_of_next_week
        return weeks

    def getYear(self, dt):
        """Return the current year.

        This returns a list of quarters, each quarter is a list of months,
        each month is a list of weeks, and each week is a list of CalendarDays.
        """
        quarters = []
        for q in range(4):
            quarter = [self.getMonth(date(dt.year, month + (q * 3), 1))
                       for month in range(1, 4)]
            quarters.append(quarter)
        return quarters

    def dayEvents(self, date):
        """Return events for a day sorted by start time.

        Events spanning several days and overlapping with this day
        are included.
        """
        day = self.getDays(date, date + timedelta(1))[0]
        return day.events

    def addParam(self, key, value):
        uri = self.request.uri
        if '?' in uri:
            return "%s&%s=%s" % (uri, key, value)
        else:
            return "%s?%s=%s" % (uri, key, value)

    def dayTitle(self, day):
        day_of_week = unicode(self.day_of_week_names[day.weekday()])
        return _('%s, %s') % (day_of_week, day.strftime('%Y-%m-%d'))

    def monthTitle(self, date):
        return unicode(self.month_names[date.month])

    def prevDay(self):
        return self.cursor - timedelta(1)

    def nextDay(self):
        return self.cursor + timedelta(1)

    def prevMonth(self):
        """Return the first day of the previous month."""
        return prev_month(self.cursor)

    def nextMonth(self):
        """Return the first day of the next month."""
        return next_month(self.cursor)

    def do_POST(self, request):
        """Deal with overlay modification."""
        if 'OVERLAY' in request.args:
            if not request.authenticated_user:
                # This should never happen
                self.request.appLog(_("Anonymous overlay change attempted"))
                return self.do_GET(request)
            overlays = request.args.get('overlay', [])
            self._subscribeToCalendarProviders(overlays)
        return self.do_GET(request)

    def do_GET(self, request):
        # All the calendar views deal with self.cursor, which is not set until
        # self.update() is called
        self.update()
        return View.do_GET(self, request)

    def getMergedCalendarProviders(self):
        """List objects who's calendars the user subscribes to."""
        if self.request.authenticated_user:
            return [group for group in
                    getRelatedObjects(self.request.authenticated_user,
                            URICalendarProvider)]
        return []

    def checkedOverlay(self, calendar):
        # XXX could return a boolean
        if calendar in self.getMergedCalendarProviders():
            return "checked"
        return None

    def getPortletCalendars(self):
        """Return a list of calendars that the user chooses.

        The list defaults to all the groups a user has Membership in and
        includes any additional calendars that a user chooses on their
        information page.
        """
        calendars = []
        user = self.request.authenticated_user
        if user:
            calendars.extend(getRelatedObjects(user, URIGroup))
            calendars.extend(getRelatedObjects(user, URICalendarListed))
        return calendars

    def renderRow(self, week, month):
        """Do some HTML rendering in Python for performance.

        This gains us 0.4 seconds out of 0.6 on my machine.
        Here is the original piece of ZPT:

         <td class="cal_yearly_day" tal:repeat="day week">
          <a tal:condition="python:day.date.month == month[1][0].date.month"
             tal:content="day/date/day"
             tal:attributes="href python:view.calURL('daily', day.date);
                             class python:(len(day.events) > 0
                                           and 'cal_yearly_day_busy'
                                           or  'cal_yearly_day')"/>
         </td>
        """
        result = []

        for day in week:
            result.append('<td class="cal_yearly_day">')
            if day.date.month == month:
                if len(day.events):
                    cssClass = 'cal_yearly_day_busy'
                else:
                    cssClass = 'cal_yearly_day'
                # Let us hope that URLs will not contain < > & or "
                # This is somewhat related to
                #   http://issues.schooltool.org/issue96
                result.append('<a href="%s" class="%s">%s</a>' %
                              (self.calURL('daily', day.date), cssClass,
                               day.date.day))
            result.append('</td>')
        return "\n".join(result)

    def ellipsizeTitle(self, str):
        """For labels with limited space replace the tail with '...'."""
        if len(str) < 17:
             return str
        else:
             return str[:15] + '...'

    def getJumpToYears(self):
        """Return jump targets for five years centered on the current year."""
        this_year = datetime.today().year
        return [{'label': year, 'value': year}
                for year in range(this_year - 2, this_year + 3)]

    def getJumpToMonths(self):
        """Return a list of months for the drop down in the jump portlet."""
        months = []
        for k, v in self.month_names.items():
            months.append({'label': unicode(v), 'value': k})
        return months

    def canChooseCalendars(self):
        # XXX Docstring
        user = self.request.authenticated_user
        return isManager(user) or user is self.context.__parent__

    def getValue(self, obj):
        # XXX Docstring
        return getPath(obj)

    def _subscribeToCalendarProviders(self, providers):
        """Link user to CalendarProvider objects.

        Providers are passed as a list of paths.
        """

        # Unlink old calendar subscriptions.
        for link in \
                self.request.authenticated_user.listLinks(URICalendarProvider):
            link.unlink()

        for provider in providers:
            relate(URICalendarSubscription,
                   (self.request.authenticated_user, URICalendarSubscriber),
                   (traverse(self.context, provider), URICalendarProvider))

    def eventColors(self, event):
        """Figure out in what color to display events from this calendar.

        Fall back to the standard blue.
        """
        if IInheritedCalendarEvent.providedBy(event):
            path = getPath(event.calendar.__parent__)
            user = self.request.authenticated_user
            if user and path in user.cal_colors:
                return user.cal_colors[path]

        return ('#9db8d2', '#7590ae')

    def calendarColors(self, owner):
        """Figure out what color to display events from this calendar in.

        This is only used in the portlet-calendar-overlay macro.
        """
        path = getPath(owner)
        user = self.request.authenticated_user
        if user:
            if path in user.cal_colors.keys():
                return user.cal_colors[path]

        return ('transparent', 'transparent')


class DailyCalendarView(CalendarViewBase):
    """Daily calendar view.

    The events are presented as boxes on a 'sheet' with rows
    representing hours.

    The challenge here is to present the events as a table, so that
    the overlapping events are displayed side by side, and the size of
    the boxes illustrate the duration of the events.
    """

    __used_for__ = ICalendar

    authorization = ACLViewAccess

    template = Template("www/cal_daily.pt")

    starthour = 8
    endhour = 19

    def title(self):
        return self.dayTitle(self.cursor)

    def prev(self):
        return self.cursor - timedelta(1)

    def next(self):
        return self.cursor + timedelta(1)

    def getColumns(self):
        """Return the maximum number of events that are overlapping.

        Extends the event so that start and end times fall on hour
        boundaries before calculating overlaps.
        """
        width = [0] * 24
        daystart = datetime.combine(self.cursor, time())
        for event in self.dayEvents(self.cursor):
            t = daystart
            dtend = daystart + timedelta(1)
            for title, start, duration in self.calendarRows():
                if start <= event.dtstart < start + duration:
                    t = start
                if start < event.dtstart + event.duration <= start + duration:
                    dtend = start + duration
            while True:
                width[t.hour] += 1
                t += timedelta(hours=1)
                if t >= dtend:
                    break
        return max(width) or 1

    def _setRange(self, events):
        """Set the starthour and endhour attributes according to events.

        The range of the hours to display is the union of the range
        8:00-18:00 and time spans of all the events in the events
        list.
        """
        for event in events:
            start = datetime.combine(self.cursor, time(self.starthour))
            end = (datetime.combine(self.cursor, time()) +
                   timedelta(hours=self.endhour)) # endhour may be 24
            if event.dtstart < start:
                newstart = max(datetime.combine(self.cursor, time()),
                               event.dtstart)
                self.starthour = newstart.hour

            if event.dtstart + event.duration > end:
                newend = min(
                    datetime.combine(self.cursor, time()) + timedelta(1),
                    event.dtstart + event.duration + timedelta(0, 3599))
                self.endhour = newend.hour
                if self.endhour == 0:
                    self.endhour = 24

    def calendarRows(self):
        """Iterates over (title, start, duration) of time slots that make up
        the daily calendar.
        """
        if self.request.getCookie('cal_periods') != 'no':
            periods = getPeriodsForDay(self.cursor, self.context)
        else:
            periods = []
        today = datetime.combine(self.cursor, time())
        row_ends = [today + timedelta(hours=hour + 1)
                    for hour in range(self.starthour, self.endhour)]

        # Put starts and ends of periods into row_ends
        for period in periods:
            pstart = datetime.combine(self.cursor, period.tstart)
            pend = pstart + period.duration
            for point in row_ends:
                if pstart < point < pend:
                    row_ends.remove(point)
                if pstart not in row_ends:
                    row_ends.append(pstart)
                if pend not in row_ends:
                    row_ends.append(pend)

        if periods:
            row_ends.sort()

        def periodIsStarting(dt):
            if not periods:
                return False
            pstart = datetime.combine(self.cursor, periods[0].tstart)
            if pstart == dt:
                return True

        start = today + timedelta(hours=self.starthour)
        for end in row_ends:
            if periodIsStarting(start):
                period = periods.pop(0)
                pstart = datetime.combine(self.cursor, period.tstart)
                pend = pstart + period.duration
                yield (period.title, start, period.duration)
            else:
                duration =  end - start
                yield ('%d:%02d' % (start.hour, start.minute), start, duration)
            start = end

    def getHours(self):
        """Return an iterator over the rows of the table.

        Every row is a dict with the following keys:

            'time' -- row label (e.g. 8:00)
            'cols' -- sequence of cell values for this row

        A cell value can be one of the following:
            None  -- if there is no event in this cell
            event -- if an event starts in this cell
            ''    -- if an event started above this cell

        """
        nr_cols = self.getColumns()
        events = self.dayEvents(self.cursor)
        self._setRange(events)
        slots = Slots()
        for title, start, duration in self.calendarRows():
            end = start + duration
            hour = start.hour

            # Remove the events that have already ended
            for i in range(nr_cols):
                ev = slots.get(i, None)
                if ev is not None and ev.dtstart + ev.duration <= start:
                    del slots[i]

            # Add events that start during (or before) this hour
            while (events and events[0].dtstart < end):
                event = events.pop(0)
                slots.add(event)
            cols = []

            # Format the row
            for i in range(nr_cols):
                ev = slots.get(i, None)
                if (ev is not None
                    and ev.dtstart < start
                    and hour != self.starthour):
                    # The event started before this hour (except first row)
                    cols.append('')
                else:
                    # Either None, or new event
                    cols.append(ev)

            yield {'title': title, 'cols': tuple(cols),
                   'time': start.strftime("%H:%M"),
                   # We can trust no period will be longer than a day
                   'duration': duration.seconds // 60}

    def rowspan(self, event):
        """Calculate how many calendar rows the event will take today."""
        count  = 0
        for title, start, duration in self.calendarRows():
            if (start < event.dtstart + event.duration and
                event.dtstart < start + duration):
                count += 1
        return count

    def eventTop(self, event):
        """Calculate the position of the top of the event block in the display.

        Each hour is made up of 4 units ('em' currently). If an event starts at
        10:15, and the day starts at 8:00 we get a top value of:

          (2 * 4) + (15 / 15) = 9

        """

        top = ((event.dtstart.hour - self.starthour) * 4
                + event.dtstart.minute / 15)

        return top

    def eventHeight(self, event):
        """Calculate the height of the event block in the display.

        Each hour is made up of 4 units ('em' currently).  Need to round 1 -
        14 minute intervals up to 1 display unit.

        """

        minutes = event.duration.seconds / 60

        return max(1, (minutes + 14) / 15)

    def do_GET(self, request):

        # Create self.cursor
        self.update()

        # Initialize self.starthour and self.endhour
        events = self.dayEvents(self.cursor)
        self._setRange(events)

        # The number of hours displayed in the day view
        self.visiblehours = self.endhour - self.starthour
        return View.do_GET(self, request)


class Slots(dict):
    """A dict with automatic key selection.

    The add method automatically selects the lowest unused numeric key
    (starting from 0).

    Example:

      >>> s = Slots()
      >>> s.add("first")
      >>> s
      {0: 'first'}

      >>> s.add("second")
      >>> s
      {0: 'first', 1: 'second'}

    The keys can be reused:

      >>> del s[0]
      >>> s.add("third")
      >>> s
      {0: 'third', 1: 'second'}

    """

    def add(self, obj):
        i = 0
        while i in self:
            i += 1
        self[i] = obj


class WeeklyCalendarView(CalendarViewBase):
    """Weekly calendar view."""

    template = Template("www/cal_weekly.pt")

    def title(self):
        # XXX Not tested.
        month_name = unicode(self.month_names[self.cursor.month])
        args = {'month': month_name,
                'year': self.cursor.year,
                'week': self.cursor.isocalendar()[1]}
        return _('%(month)s, %(year)s (week %(week)s)') % args

    def prevWeek(self):
        """Return the day a week before."""
        return self.cursor - timedelta(7)

    def nextWeek(self):
        """Return the day a week after."""
        return self.cursor + timedelta(7)

    def getCurrentWeek(self):
        """Return the current week as a list of CalendarDay objects."""
        return self.getWeek(self.cursor)


class MonthlyCalendarView(CalendarViewBase):
    """Monthly calendar view."""

    template = Template("www/cal_monthly.pt")

    def title(self):
        month_name = unicode(self.month_names[self.cursor.month])
        return _('%(month)s, %(year)s') % {
                                'month': month_name,
                                'year': self.cursor.year,
                            }

    def dayOfWeek(self, date):
        return unicode(self.day_of_week_names[date.weekday()])

    def weekTitle(self, date):
        return _('Week %d') % date.isocalendar()[1]

    def getCurrentMonth(self):
        """Return the current month as a nested list of CalendarDays."""
        return self.getMonth(self.cursor)


class YearlyCalendarView(CalendarViewBase):
    """Yearly calendar view."""

    template = Template('www/cal_yearly.pt')

    def monthTitle(self, date):
        return unicode(self.month_names[date.month])

    def dayOfWeek(self, date):
        return unicode(self.short_day_of_week_names[date.weekday()])

    def prevYear(self):
        """Return the first day of the next year."""
        return date(self.cursor.year - 1, 1, 1)

    def nextYear(self):
        """Return the first day of the previous year."""
        return date(self.cursor.year + 1, 1, 1)

    __url = None

    def calURL(self, cal_type, cursor=None):
        if cursor is None:
            cursor = self.cursor
        if self.__url is None:
            self.__url = absolutePath(self.request, self.context)
        return  '%s/%s.html?date=%s' % (self.__url, cal_type, cursor)


class CalendarView(View):
    """The main calendar view.

    Switches daily, weekly, monthly, yearly calendar presentations.
    """

    __used_for__ = ICalendar

    authorization = ACLViewAccess

    def _traverse(self, name, request):
        if 'cal_periods' in request.args:
            expires = None
            if request.args['cal_periods'][0] == 'no':
                request.addCookie('cal_periods', 'no', path='/')
            else:
                request.addCookie('cal_periods', 'yes', path='/')
            uri = request.uri
            if '?' in uri:
                uri = uri[:uri.rindex('?')]
            if 'date' in request.args:
                uri = "%s?date=%s" % (uri, request.args['date'][0])
            self.redirect(uri, request)
        if name == 'daily.html':
            return DailyCalendarView(self.context)
        elif name == 'weekly.html':
            return WeeklyCalendarView(self.context)
        elif name == 'monthly.html':
            return MonthlyCalendarView(self.context)
        elif name == 'yearly.html':
            return YearlyCalendarView(self.context)
        elif name == 'add_event.html':
            return EventAddView(self.context)
        elif name == 'edit_event.html':
            return EventEditView(self.context)
        elif name == 'delete_event.html':
            return EventDeleteView(self.context)
        elif name == 'event-popup.html':
            return EventDisplayView(self.context)
        elif name == 'acl.html':
            return ACLView(self.context.acl)
        else:
            raise KeyError(name)

    def do_GET(self, request):
        """Redirect to the daily calendar view by default."""
        url = absoluteURL(request, self.context, 'daily.html')
        return self.redirect(url, request)


class EventViewHelpers:
    """Helpers for the event views."""

    def _findOrdinaryEvent(self, event_id):
        """Return the event with the given ID from the ordinary calendar.

        Returns None if there is no event with the given ID in the calendar.
        """
        try:
            return self.context.find(event_id)
        except KeyError:
            return None

    def _findInheritedEvent(self, event_id, day):
        """Return the event with the given ID from the ordinary calendar.

        day is a date on which the event is happening.

        Returns None if there is no event with the given ID in the calendar.
        """
        try:
            obj = self.context.__parent__
            return obj.makeCompositeCalendar(day, day).find(event_id)
        except KeyError:
            return None

    def _findTimetableEvent(self, event_id):
        """Return the event with the given ID from the timetable calendar.

        Returns None if there is no event with the given ID in the calendar.
        """
        appobject = self.context.__parent__
        try:
            return appobject.makeTimetableCalendar().find(event_id)
        except KeyError:
            return None

    def _addTimetableException(self, event, replacement):
        """Add or change a timetable exception for a timetable event.

        If event is already an exceptional event, the corresponding
        exception is adjusted.  Otherwise a new one is created.
        """
        if IExceptionalTTCalendarEvent.providedBy(event):
            exception = event.exception
        else:
            exception = TimetableException(event.dtstart.date(),
                                           event.period_id,
                                           event.activity)
            tt = event.activity.timetable
            tt.exceptions.append(exception)

        if replacement is not None:
            replacement = ExceptionalTTCalendarEvent(
                    replacement.dtstart,
                    replacement.duration,
                    replacement.title,
                    replacement.owner,
                    context=replacement.context,
                    location=replacement.location,
                    unique_id=replacement.unique_id,
                    exception=exception)
        exception.replacement = replacement

    def _redirectToDailyView(self, date=None):
        """Redirect to the daily calendar view for a given date (or today)."""
        url = absoluteURL(self.request, self.context, 'daily.html')
        if date is not None:
            url += '?date=%s' % date.strftime('%Y-%m-%d')
        return self.redirect(url, self.request)


def datesFormatter(dates):
    r"""Format a sequence of dates

    >>> datesFormatter((date(2004, 5, 17),
    ...                 date(2004, 1, 29)))
    '2004-05-17\n2004-01-29'

    """
    return "\n".join([str(d) for d in dates])


def datesParser(raw_dates):
    r"""Parse dates on separate lines into a tuple of date objects.

    Incorrect lines are ignored.

    >>> datesParser('2004-05-17\n\n\n2004-01-29')
    (datetime.date(2004, 5, 17), datetime.date(2004, 1, 29))

    >>> datesParser('2004-05-17\n123\n\nNone\n2004-01-29')
    Traceback (most recent call last):
    ...
    ValueError: Invalid date.  Please specify YYYY-MM-DD, one per line.

    """
    results = []
    for dstr in raw_dates.splitlines():
        try:
            d = dateParser(dstr)
        except ValueError:
            # XXX: translate
            raise ValueError('Invalid date.  Please specify YYYY-MM-DD,'
                             ' one per line.')
        if isinstance(d, date):
            results.append(d)
    return tuple(results)


def positiveIntValidator(value):
    """
    >>> positiveIntValidator(None)
    >>> positiveIntValidator(1)

    >>> positiveIntValidator(0)
    Traceback (most recent call last):
    ...
    ValueError: Invalid value (must be not less than 1).

    >>> positiveIntValidator(-1)
    Traceback (most recent call last):
    ...
    ValueError: Invalid value (must be not less than 1).

    """
    if value is None:
        return
    if value < 1:
        # XXX translate
        raise ValueError("Invalid value (must be not less than 1).")


def intsParser(raw):
    """
    >>> intsParser(None)
    >>> intsParser("")
    >>> intsParser("1")
    (1,)
    >>> intsParser(["1", "3"])
    (1, 3)
    """
    result = []
    try:
        if isinstance(raw, list):
            for s in raw:
                result.append(intParser(s))
        else:
            # XXX this is overkill, raw will never be a single string
            if intParser(raw) is None:
                return None
            result.append(intParser(raw))
    except ValueError:
        # XXX translate and make understandable
        raise ValueError('weekdays must be a tuple of ints between 0 and 6.')
    return tuple(result)


def weekdaysValidator(value):
    """
    >>> weekdaysValidator(None)
    >>> weekdaysValidator((0, 1, 2, 3, 4, 5, 6))
    >>> weekdaysValidator(1)
    Traceback (most recent call last):
    ...
    ValueError: weekdays must be a tuple of ints between 0 and 6.
    >>> weekdaysValidator("hello")
    Traceback (most recent call last):
    ...
    ValueError: weekdays must be ints between 0 and 6.
    >>> weekdaysValidator((1, 7))
    Traceback (most recent call last):
    ...
    ValueError: weekdays must be ints between 0 and 6.

    """
    if value is None:
        return
    try:
        for i in value:
            if i < 0 or i > 6:
                # XXX: translate
                raise ValueError('weekdays must be ints between 0 and 6.')
    except TypeError:
        # XXX: translate
        raise ValueError('weekdays must be a tuple of ints between 0 and 6.')


class EventViewBase(View, CalendarBreadcrumbsMixin, EventViewHelpers):
    """A base class for event adding and editing views.

    Used by EventAddView and EventEditView.
    """
    # XXX This class and its subclasses are a bit "heavy".

    __used_for__ = ICalendar

    authorization = ACLModifyAccess

    template = Template('www/event.pt')

    page_title = None # overridden by subclasses
    tt_event = False
    date = None
    error = None

    def setUpWidgets(self):
        """Set up widgets used in this form."""
        self.title_widget = TextWidget('title', _('Title'))
        self.date_widget = TextWidget('start_date', _('Date'),
                                      parser=dateParser)
        self.time_widget = TextWidget('start_time', _('Time'),
                                      parser=timeParser,
                                      formatter=timeFormatter)
        self.duration_widget = TextWidget('duration', _('Duration'),
                                          unit=_('min.'),
                                          parser=intParser,
                                          validator=durationValidator,
                                          value=30)

        self.locations = self.getLocations()
        choices = [(l, l) for l in self.locations] + [('', _('Other'))]
        self.location_widget = SelectionWidget('location', _('Location'),
                                               choices, value='')
        self.other_location_widget = TextWidget('location_other',
                                                _('Specify other location'))

        default_privacy = getOptions(self.context).new_event_privacy
        self.privacy_widget = SelectionWidget('privacy',
                                              _('Visibility to other users'),
                                              (('public', _('Public')),
                                               ('private',  _('Busy block')),
                                               ('hidden', _('Hidden'))),
                                              value=default_privacy)

        self._setUpRecurrenceWidgets()

    def _setUpRecurrenceWidgets(self):
        """Set up widgets for editing recurrence attributes."""
        self.recurrence_widget = CheckboxWidget('recurrence', _('Recurring'))

        self.recurrence_type_widget = SelectionWidget(
            'recurrence_type', _('Recurs'),
            (('daily', _('Day')), ('weekly', _('Week')),
             ('monthly', _('Month')), ('yearly', _('Year'))))


        self.interval_widget = TextWidget('interval', _('Repeat every'),
                                          parser=intParser,
                                          validator=positiveIntValidator,
                                          value=1)

        self.range_widget = SelectionWidget('range', _('Range'),
                                            (('count', _('Count')),
                                             ('until', _('Until')),
                                             ('forever', _('forever'))),
                                            value='forever')

        self.count_widget = TextWidget('count', _('Number of events'),
                                       validator=positiveIntValidator,
                                       parser=intParser)
        self.until_widget = TextWidget('until', _('Repeat until'),
                                       parser=dateParser)

        # The display is done manually, so no formatter is needed.
        self.weekdays_widget = SequenceWidget('weekdays', _('Weekdays'),
                                              parser=intsParser,
                                              validator=weekdaysValidator)

        self.monthly_widget = SelectionWidget('monthly', _('Monthly'),
                                              (('monthday', 'md'),
                                               ('weekday', 'wd'),
                                               ('lastweekday', 'lwd')),
                                              value='monthday')

        self.exceptions_widget = TextAreaWidget('exceptions',
                                                _('Exception dates'),
                                                parser=datesParser,
                                                formatter=datesFormatter)

    def update(self):
        """Parse arguments in request and put them into view attributes."""
        for widget_name in ['title', 'date', 'time', 'duration',
                            'location', 'other_location', 'privacy',
                            'recurrence', 'recurrence_type', 'interval',
                            'range', 'count', 'until', 'exceptions',
                            'weekdays', 'monthly']:
            widget = getattr(self, widget_name + '_widget')
            widget.update(self.request)

    def do_GET(self, request):
        self.setUpWidgets()
        self.update()
        return View.do_GET(self, request)

    def do_POST(self, request):
        self.setUpWidgets()
        self.update()
        if self.title_widget.value == "":
            # Force a "field is required" error if value is ""
            self.title_widget.setRawValue(None)
        self.title_widget.require()
        self.date_widget.require()
        self.time_widget.require()
        self.duration_widget.require()

        if self.range_widget.value == 'count':
            self.count_widget.require()
        if self.range_widget.value == 'until':
            self.until_widget.require()
            start = self.date_widget.value
            until = self.until_widget.value
            if start and until and start > until:
                self.until_widget.error = _("End date is earlier"
                                            " than start date")

        errors = (self.title_widget.error or self.date_widget.error or
                  self.time_widget.error or self.duration_widget.error or
                  self.location_widget.error or
                  self.other_location_widget.error or
                  self.interval_widget.error or
                  self.count_widget.error or self.until_widget.error)

        if errors or 'SUBMIT' not in request.args:
            return View.do_GET(self, request)

        start = datetime.combine(self.date_widget.value,
                                 self.time_widget.value)
        duration = timedelta(minutes=self.duration_widget.value)

        location = (self.location_widget.value or
                    self.other_location_widget.value or None)

        self.process(start, duration, self.title_widget.value, location,
                     self.privacy_widget.value)

        if self.date is not None and self.tt_event:
            dt = self.date
        else:
            dt = start.date()
        return self._redirectToDailyView(date=dt)

    def process(self, dtstart, duration, title, location, privacy):
        raise NotImplementedError("Override this method in subclasses.")

    def getRecurrenceRule(self):
        """Return a recurrence rule according to the widgets in request.

        Must be called after update().
        """
        if self.tt_event or not self.recurrence_widget.value:
            return None

        interval = self.interval_widget.value
        until = self.until_widget.value
        count = self.count_widget.value
        range = self.range_widget.value
        exceptions = self.exceptions_widget.value

        if interval is None:
            interval = 1

        if range != 'until':
            until = None
        if range != 'count':
            count = None

        if exceptions is None:
            exceptions = ()

        kwargs = {'interval': interval, 'count': count,
                  'until': until, 'exceptions': exceptions}

        recurrence_type = self.recurrence_type_widget.value
        if recurrence_type == 'daily':
            return DailyRecurrenceRule(**kwargs)
        elif self.recurrence_type_widget.value == 'weekly':
            weekdays = self.weekdays_widget.value or ()
            return WeeklyRecurrenceRule(weekdays=tuple(weekdays), **kwargs)
        elif self.recurrence_type_widget.value == 'monthly':
            monthly = self.monthly_widget.value
            return MonthlyRecurrenceRule(monthly=monthly, **kwargs)
        elif self.recurrence_type_widget.value == 'yearly':
            return YearlyRecurrenceRule(**kwargs)
        else:
            return None # Shouldn't happen

    def getLocations(self):
        """Get a list of titles for possible locations."""
        location_group = traverse(self.context, '/groups/locations')
        locations = []
        for location in getRelatedObjects(location_group, URIMember):
            locations.append(location.title)
        locations.sort()
        return locations

    def weekdays(self):
        return ({'nr': 0, 'name': _("Mon")}, {'nr': 1, 'name': _("Tue")},
                {'nr': 2, 'name': _("Wed")}, {'nr': 3, 'name': _("Thu")},
                {'nr': 4, 'name': _("Fri")}, {'nr': 5, 'name': _("Sat")},
                {'nr': 6, 'name': _("Sun")})

    def getMonthDay(self):
        """Return the day number in a month."""
        evdate = self.date_widget.value
        if evdate is None:
            return '??'
        else:
            return str(evdate.day)

    def getWeekDay(self):
        """Return a description like '4th Tuesday'."""
        evdate = self.date_widget.value
        if evdate is None:
            return "same weekday"
        weekday = evdate.weekday()
        index = (evdate.day - 1) / 7 + 1

        indexes = {1: _('1st'), 2: _('2nd'), 3: _('3rd'),
                   4: _('4th'), 5: _('5th')}
        day_of_week = unicode(CalendarViewBase.day_of_week_names[weekday])

        return "%s %s" % (indexes[index], day_of_week)

    def weekdayChecked(self, weekday):
        """Return True if the given weekday should be checked."""
        day = self.date_widget.value
        return bool(day and day.weekday() == weekday['nr']
                    or (self.weekdays_widget.value and
                        weekday['nr'] in self.weekdays_widget.value))

    def weekdayDisabled(self, weekday):
        """Return True if the given weekday should be disabled."""
        day = self.date_widget.value
        return bool(day and day.weekday() == weekday['nr'])

    def getLastWeekDay(self):
        """Return a description like 'Last Friday' or None."""
        evdate = self.date_widget.value
        if evdate is None:
            return "last weekday"
        lastday = calendar.monthrange(evdate.year, evdate.month)[1]
        if lastday - evdate.day >= 7:
            return None
        else:
            weekday = evdate.weekday()
            day_of_week = unicode(CalendarViewBase.day_of_week_names[weekday])
            return _("Last %(weekday)s") % {'weekday': day_of_week}

    def bookingEvent(self):
        return False


class EventAddView(EventViewBase):
    """A view for adding events."""

    page_title = property(lambda self: _("Add event"))

    authorization = ACLAddAccess

    def process(self, dtstart, duration, title, location, privacy):
        ev = CalendarEvent(dtstart, duration, title,
                           self.context.__parent__, self.context.__parent__,
                           location=location,
                           recurrence=self.getRecurrenceRule(),
                           privacy=privacy)
        self.context.addEvent(ev)


class EventEditView(EventViewBase):
    """A view for editing events."""

    page_title = property(lambda self: _("Edit event"))

    composite_event = None
    calendar = None

    def update(self):
        self.event_id = to_unicode(self.request.args['event_id'][0])
        date = to_unicode(self.request.args['date'][0])
        self.date = parse_date(date)

        self.calendar = self.context
        event = self._findOrdinaryEvent(self.event_id)
        if event is None:
            event = self._findInheritedEvent(self.event_id, self.date)
            if event is not None:
                self.composite_event = True
                self.calendar = event.calendar
                event = self.calendar.find(event.unique_id)
        if event is None:
            event = self._findTimetableEvent(self.event_id)
            self.tt_event = (event is not None)
        if event is None:
            # Pehaps it would be better to create a traversal view for events
            # and refactor the event edit view to take the event as context,
            # then we would be able to simply display a standard 404 page.
            self.error = _("This event does not exist.")
            return
        if (self.tt_event or self.composite_event) and not self.isManager():
            # Only managers may add timetable exceptions
            raise Unauthorized

        self.title_widget.setValue(event.title)
        self.date_widget.setValue(event.dtstart.date())
        self.time_widget.setValue(event.dtstart.time())
        self.duration_widget.setValue(event.duration.seconds // 60)
        if event.location in self.locations:
            self.location_widget.setValue(event.location)
            self.other_location_widget.setValue('')
        else:
            self.location_widget.setValue('')
            self.other_location_widget.setValue(event.location)

        self.privacy_widget.setValue(event.privacy)

        if event.recurrence is not None:
            self.recurrence_widget.setValue(True)

            if IDailyRecurrenceRule.providedBy(event.recurrence):
                self.recurrence_type_widget.setValue('daily')
            elif IWeeklyRecurrenceRule.providedBy(event.recurrence):
                self.recurrence_type_widget.setValue('weekly')
                self.weekdays_widget.setValue(event.recurrence.weekdays)
            elif IMonthlyRecurrenceRule.providedBy(event.recurrence):
                self.recurrence_type_widget.setValue('monthly')
                self.monthly_widget.setValue(event.recurrence.monthly)
            elif IYearlyRecurrenceRule.providedBy(event.recurrence):
                self.recurrence_type_widget.setValue('yearly')

            self.interval_widget.setValue(event.recurrence.interval)

            if event.recurrence.count:
                self.range_widget.setValue('count')
                self.count_widget.setValue(event.recurrence.count)
            elif event.recurrence.until:
                self.range_widget.setValue('until')
                self.until_widget.setValue(event.recurrence.until)
            else:
                self.range_widget.setValue('forever')

            if event.recurrence.exceptions:
                self.exceptions_widget.setValue(event.recurrence.exceptions)

        else:
            self.recurrence_widget.setValue(False)

        self.event = event
        EventViewBase.update(self)

    def process(self, dtstart, duration, title, location, privacy):
        ev = self.event.replace(dtstart=dtstart, duration=duration,
                                title=title, location=location,
                                unique_id=self.event.unique_id,
                                recurrence=self.getRecurrenceRule(),
                                privacy=privacy)
        if (self.tt_event or self.composite_event) and not self.isManager():
            # Only managers may add timetable exceptions
            raise Unauthorized
        if self.tt_event:
            self._addTimetableException(self.event, replacement=ev)
        else:
            self.calendar.removeEvent(self.event)
            self.calendar.addEvent(ev)

    def bookingEvent(self):
        return self.event.owner != self.event.context


class EventDeleteView(View, EventViewHelpers):
    """A view for deleting events.

    The view receives two arguments in the request:

        `event_id` -- the ID of the event.

        `date` -- the date where that event was displayed (this is important
        for recurring events, because all ocurrences have the same event_id and
        you can only tell them apart by looking at the date).

    CalendarEventView.deleteLink generates a link for calling this view.

    There are five usage scenarios:

        1. You are trying to delete an ordinary, nonrepeating calendar event.
           The event is removed from the calendar.

        2. You are trying to delete an event that comes from a group
           through the composite calendar.  The event is removed from the
           group's calendar.

        3. You are trying to delete an instance of a repeating calendar event.
           A form is shown where you can choose whether you want to remove
           all repetitions, just this one repetition, or this and future
           repetitions.  Depending on your choice the event can either be
           removed from the calendar, or an exception can be added to the
           recurrence rule, or the end date of the repetition may be changed
           in the recurrence rule.

        4. You are trying to delete an event that comes from a timetable: a
           confirmation form is shown, and if you accept it, a timetable
           exception is added.  Only managers are allowed to add timetable
           exceptions.

        5. You are trying to delete an event that comes from a timetable
           exception: a confirmation form is shown, and if you accept it, a
           timetable exception is modified to remove the event rather than
           replace it.  Only managers are allowed to change timetable
           exceptions.

        6. The event_id does not point to an existing calendar event.  This can
           happen when someone removes a calendar event, and you click on a
           delete link in an outdated web page.  The request to delete a
           nonexisting event is silently ignored.

    After you're done, you're redirected to the daily calendar view for the
    specified date.
    """

    __used_for__ = ICalendar

    # Access to ordinary events is protected by the calendar's ACL.
    # Access to timetable exceptions is additionally restricted to managers.
    authorization = ACLModifyAccess

    # Page template shown when you are trying to remove a recurring event.
    recurrence_template = Template('www/recevent_delete.pt')

    # Page template shown when you are trying to remove a timetable event.
    # Extra namespace bindings: `event`
    tt_confirm_template = Template('www/ttevent_delete.pt')

    def do_GET(self, request):
        # It would be nice to show a meaningful error message if the arguments
        # are not supplied or invalid, but it is not necessary.
        event_id = to_unicode(request.args['event_id'][0])
        date = parse_date(to_unicode(request.args['date'][0]))

        # If it is an ordinary calendar event, remove it
        event = self._findOrdinaryEvent(event_id)
        if event is not None:
            if event.recurrence is None:
                return self._deleteOrdinaryEvent(self.context, event, date)
            else:
                return self._deleteRepeatingEvent(self.context, event, date)

        # If it is a composite calendar event, remove it from the
        # corresponding calendar
        event = self._findInheritedEvent(event_id, date)
        if event is not None:
            if not self.isManager():
                # XXX embedding security policy decisions in the middle of view
                # code is not nice.
                raise Unauthorized # Only managers can delete composite events
            calendar = event.calendar
            real_event = event.calendar.find(event.unique_id)
            if event.recurrence is None:
                return self._deleteOrdinaryEvent(calendar, real_event, date)
            else:
                return self._deleteRepeatingEvent(calendar, real_event, date)

        # If it is a timetable event, show a confirmation form,
        # and then add a timetable exception (unless canceled).
        event = self._findTimetableEvent(event_id)
        if event is not None:
            if not self.isManager():
                raise Unauthorized # Only managers can delete timetable events
            return self._deleteTimetableEvent(event, date)

        # Dangling event ID
        return self._redirectToDailyView(date)

    def _deleteOrdinaryEvent(self, calendar, event, date):
        """Delete an ordinary event."""
        calendar.removeEvent(event)
        return self._redirectToDailyView(date)

    def _deleteRepeatingEvent(self, calendar, event, date):
        """Delete a repeating event."""
        if 'CANCEL' in self.request.args:
            return self._redirectToDailyView(date)
        elif 'ALL' in self.request.args:
            calendar.removeEvent(event)
            return self._redirectToDailyView(date)
        elif 'FUTURE' in self.request.args:
            calendar.removeEvent(event)
            replacement = self._deleteFutureOccurrences(event, date)
            if replacement.hasOccurrences():
                calendar.addEvent(replacement)
            return self._redirectToDailyView(date)
        elif 'CURRENT' in self.request.args:
            calendar.removeEvent(event)
            replacement = self._deleteOneOccurrence(event, date)
            if replacement.hasOccurrences():
                calendar.addEvent(replacement)
            return self._redirectToDailyView(date)
        return self._showOccurrenceForm(event)

    def _deleteFutureOccurrences(self, event, date):
        """Return event without repetitions past a given date."""
        until = date - timedelta(days=1)
        if (event.recurrence.until is not None
            and event.recurrence.until <= until):
            return event
        new_recurrence = event.recurrence.replace(count=None, until=until)
        return event.replace(recurrence=new_recurrence)

    def _deleteOneOccurrence(self, event, date):
        """Return event without a repetition on a given date."""
        if date in event.recurrence.exceptions:
            return event
        exceptions = event.recurrence.exceptions + (date, )
        new_recurrence = event.recurrence.replace(exceptions=exceptions)
        return event.replace(recurrence=new_recurrence)

    def _deleteTimetableEvent(self, event, date):
        """Delete a timetable event."""
        if 'CONFIRM' in self.request.args:
            self._addTimetableException(event, replacement=None)
        elif 'CANCEL' not in self.request.args:
            return self._showConfirmationForm(event)
        return self._redirectToDailyView(date)

    def _showOccurrenceForm(self, event):
        """Render the form where the user selects occurrences to be deleted.

        The form offers a choice to delete just this one occurrence of the
        repeating event (CURRENT), this and future occurrences (FUTURE),
        all occurrences (ALL), or to cancel the deletion (CANCEL).  Uppercase
        words in parentheses are the names of submit elements corresponding
        to each choice.
        """
        return self.recurrence_template(self.request, view=self,
                                        context=self.context, event=event)

    def _showConfirmationForm(self, event):
        """Render the notification/confirmation form for a timetable event.

        The form tells the user that a timetable exception will be added
        and allows to confirm it (CONFIRM) or to cancel the deletion (CANCEL).
        Uppercase words in parentheses are the names of submit elements
        corresponding to each choice.
        """
        return self.tt_confirm_template(self.request, view=self,
                                        context=self.context, event=event)


class EventDisplayView(EventEditView):
    """Read only display of an event."""

    template = Template("www/event-popup.pt")


class CalendarEventView(View):
    """Renders the inside of the event box in various calendar views."""

    __used_for__ = ICalendarEvent

    authorization = PublicAccess

    template = Template("www/cal_event.pt", charset=None)

    def __init__(self, event, calendar):
        """Create a view for event.

        Since ordinary calendar events do not know which calendar they come
        from, we have to explicitly provide the access control list (acl)
        that governs access to this calendar.
        """
        View.__init__(self, event)
        self.acl = getACL(calendar)
        self.calendar = calendar
        self.date = None

    def canEdit(self):
        """Can the current user edit this calendar event?

        Users can edit normal calendar events only if the ACL allows it.

        Only managers can edit special events: timetable events, exceptional
        events and inherited events.
        """
        if self.isManager():
            return True

        for iface in [IInheritedCalendarEvent,
                      IExceptionalTTCalendarEvent,
                      ITimetableCalendarEvent]:
            if iface.providedBy(self.context):
                return False

        user = self.request.authenticated_user
        return self.acl.allows(user, ModifyPermission)

    def canView(self):
        """Can the current user view this calendar event?"""
        user = self.request.authenticated_user
        if self.context.privacy == 'public':
            return True
        else:
            return self.isManager() or user is self.calendar.__parent__

    def isHidden(self):
        """Should the event be hidden from the current user?"""
        user = self.request.authenticated_user
        if not self.context.privacy == 'hidden':
            return False
        else:
            return not (self.isManager() or user is self.calendar.__parent__)

    def cssClass(self):
        """Choose a CSS class for the event."""
        if IInheritedCalendarEvent.providedBy(self.context):
            return 'comp_event'
        if IExceptionalTTCalendarEvent.providedBy(self.context):
            return 'exc_event'
        elif ITimetableCalendarEvent.providedBy(self.context):
            return 'tt_event'
        else:
            return 'event'

    def getPeriod(self):
        """Returns the title of the timetable period this event coincides with.

        Returns None if there is no such period.
        """
        if self.request.getCookie('cal_periods'):
            periods = getPeriodsForDay(self.context.dtstart.date(),
                                       self.calendar)
            for period in periods:
                if (period.tstart == self.context.dtstart.time() and
                    period.duration == self.context.duration):
                    return period.title
        return None

    def duration(self):
        """Format the time span of the event."""
        dtstart = self.context.dtstart
        dtend = dtstart + self.context.duration
        if dtstart.date() == dtend.date():
            span =  "%s&ndash;%s" % (dtstart.strftime('%H:%M'),
                                     dtend.strftime('%H:%M'))
        else:
            span = "%s&ndash;%s" % (dtstart.strftime('%Y-%m-%d %H:%M'),
                                    dtend.strftime('%Y-%m-%d %H:%M'))

        period = self.getPeriod()
        if period:
            return "Period %s (%s)" % (period, span)
        else:
            return span

    def full(self, request, date):
        """Full representation of the event for daily/weekly views."""
        try:
            self.request = request
            self.date = date
            return self.do_GET(request)
        finally:
            self.request = None
            self.date = None

    def short(self, request):
        """Short representation of the event for the monthly view."""
        self.request = request
        ev = self.context
        end = ev.dtstart + ev.duration
        if self.canView():
            title = ev.title
        else:
            title = _("Busy")
        if ev.dtstart.date() == end.date():
            period = self.getPeriod()
            if period:
                duration = _("Period %s") % period
            else:
                duration =  "%s&ndash;%s" % (ev.dtstart.strftime('%H:%M'),
                                             end.strftime('%H:%M'))
        else:
            duration =  "%s&ndash;%s" % (ev.dtstart.strftime('%b&nbsp;%d'),
                                         end.strftime('%b&nbsp;%d'))
        return "%s (%s)" % (title, duration)

    def editLink(self):
        """Return the link for editing this event."""
        return 'edit_event.html?' + self._params()

    def deleteLink(self):
        """Return the link for deleting this event."""
        return 'delete_event.html?' + self._params()

    def _params(self):
        """Prepare query arguments for editLink and deleteLink."""
        event_id = self.context.unique_id
        date = self.date.strftime('%Y-%m-%d')
        return 'date=%s&event_id=%s' % (date, urllib.quote(event_id))

    def privacy(self):
        if self.context.privacy == "public":
            return _("Public")
        elif self.context.privacy == "private":
            return _("Busy block")
        elif self.context.privacy == "hidden":
            return _("Hidden")


def durationValidator(value):
    """Check if duration is acceptable.

        >>> durationValidator(None)
        >>> durationValidator(42)
        >>> durationValidator(0)
        >>> durationValidator(-1)
        Traceback (most recent call last):
            ...
        ValueError: Duration cannot be negative.

    """
    if value is None:
        return
    if value < 0:
        raise ValueError(_("Duration cannot be negative."))


#
# Calendaring functions
# (Perhaps move them to schooltool.common?)
#

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

    Assuming that weeks start on Mondays:

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

    Assuming that weeks start on Sundays:

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
