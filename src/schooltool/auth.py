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
SchoolTool authentication service.

$Id$
"""

import sha
import time
import random
import datetime

from persistent import Persistent
from BTrees.OOBTree import OOBTree

from schooltool.interfaces import AuthenticationError


__metaclass__ = type


class TicketService(Persistent):
    """Ticket service for authentication.

    The idea of using a ticket service for authentication is that once the
    credentials are verified in a login form, the user gets a ticket for this
    session.  The ticket is usually stored as a browser cookie.

      >>> service = TicketService()
      >>> ticket = service.newTicket(('rms', ''))

    The ticket can be used to extract the credentials from the ticket service:

      >>> service.verifyTicket(ticket)
      ('rms', '')

      >>> service.verifyTicket('fake ticket')
      Traceback (most recent call last):
        ...
      AuthenticationError

    The ticket itself is a random string, so it is not possible to extract the
    username and password from the ticket if it gets stolen.  Also, the ticket
    can expire after a certain duration.  We will demonstrate it by specifying
    a ridiculously low duration of zero seconds:

      >>> import datetime
      >>> ticket2 = service.newTicket(('user', 'password'),
      ...                             datetime.timedelta(0))
      >>> service.verifyTicket(ticket2)
      Traceback (most recent call last):
        ...
      AuthenticationError

    (If you see test failures here, make sure that your clock does not go
    backwards.  It has happened to some people!  Note that ZODB is known to be
    unhappy with nonmonotonic clocks.)

    Note that we did not specify a duration in the first example -- in that
    case the ticket will never expire automatically.

    It is always possible to forcefully expire a ticket before its expiration
    deadline is reached:

      >>> service.verifyTicket(ticket)
      ('rms', '')
      >>> service.expire(ticket)
      >>> service.verifyTicket(ticket)
      Traceback (most recent call last):
        ...
      AuthenticationError

    It is a very good idea to expire a user's ticket when the user logs out.
    """

    def __init__(self):
        self._tickets = OOBTree()

    def newTicket(self, credentials, duration=None):
        """Allocate a new ticket for given credentials.

        Returns the ticket -- a hard-to-guess random alphanumeric string.

        The ticket will automatically expire after a specified duration.  If
        duration is None, the ticket will not expire automatically.  A given
        ticket can expire earlier, if expire method is called.

        Credentials can be any object -- usually it will be a tuple containing
        the username and password.  Do not put persistent objects into the
        ticket service.
        """
        ticket = sha.new('%s-%s' % (random.random(), time.time())).hexdigest()
        if duration is None:
            expires = datetime.datetime.max
        else:
            expires = datetime.datetime.now() + duration
        self._tickets[ticket] = (credentials, expires)
        return ticket

    def verifyTicket(self, ticket):
        """Verify a ticket and return the credentials associated with it.

        Raises AuthenticationError if the ticket is not valid or has expired.
        """
        try:
            credentials, expires = self._tickets[ticket]
        except KeyError:
            raise AuthenticationError
        else:
            if datetime.datetime.now() >= expires:
                try:
                    del self._tickets[ticket]
                except KeyError:
                    # just in case two threads access the same expired ticket
                    # at the same time
                    pass
                raise AuthenticationError
            else:
                return credentials

    def expire(self, ticket):
        """Forcefully expire a ticket.

        Let's create a ticket first:

          >>> service = TicketService()
          >>> ticket = service.newTicket(('u', 'p'),
          ...                            datetime.timedelta(hours=2))
          >>> service.verifyTicket(ticket)
          ('u', 'p')

        Once you expire the ticket, it is no longer valid:

          >>> service.expire(ticket)
          >>> service.verifyTicket(ticket)
          Traceback (most recent call last):
            ...
          AuthenticationError

        You can call expire on tickets that are not valid or have expired
        already:

          >>> service.expire(ticket)

        """
        try:
            del self._tickets[ticket]
        except KeyError:
            pass
