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
"""
Gradebook Initialization
"""

from persistent import Persistent
import zope.event
from zope.container.contained import containedEvent, Contained
from zope.interface import implements
from zope.security.proxy import removeSecurityProxy

from schooltool.app.app import InitBase, StartUpBase

from schooltool.gradebook.interfaces import IGradebookRoot, IGradebookTemplates
from schooltool.gradebook.interfaces import IGradebookDeployed
from schooltool.gradebook.interfaces import IGradebookLayouts, IReportLayout
from schooltool.gradebook.interfaces import IReportColumn, IOutlineActivity
from schooltool.gradebook.category import CategoryContainer, CATEGORIES_KEY
from schooltool.requirement.requirement import Requirement

from schooltool.gradebook import GradebookMessage as _

GRADEBOOK_ROOT_KEY = 'schooltool.gradebook'


class GradebookRoot(object):
    """Root of gradebook data"""

    implements(IGradebookRoot)

    def __init__(self):
        self.templates, event = containedEvent(
            GradebookTemplates(_('Report Sheet Templates')),
            self, 'templates')
        self.deployed, event = containedEvent(
            GradebookDeployed(_('Deployed Report Sheets')),
            self, 'deployed')
        self.layouts, event = containedEvent(
            GradebookLayouts(_('Report Card Layouts')),
            self, 'layouts')


class GradebookTemplates(Requirement):
    """Container of Report Sheet Templates"""

    implements(IGradebookTemplates)


class GradebookDeployed(Requirement):
    """Container of Deployed Report Sheet Templates (by term)"""

    implements(IGradebookDeployed)


class GradebookLayouts(Requirement):
    """Container of Report Card Layouts (by schoolyear)"""

    implements(IGradebookLayouts)


class ReportLayout(Persistent, Contained):
    """The layout of the report card for the school year"""

    implements(IReportLayout)

    columns = []

    outline_activities = []


class ReportColumn(Persistent):
    """A column of the report card layout"""

    implements(IReportColumn)

    def __init__(self, source, heading):
        self.source = source
        self.heading = heading


class OutlineActivity(Persistent):
    """An outlne activity of the report card layout"""

    implements(IOutlineActivity)

    def __init__(self, source, heading):
        self.source = source
        self.heading = heading


def setUpGradebookRoot(app):
    """Create Gradebook Root Object if not already there"""

    if GRADEBOOK_ROOT_KEY not in app:
        app[GRADEBOOK_ROOT_KEY] = GradebookRoot()


def setUpDefaultCategories(categories):
    # XXX: We werestoring zope.i18nmessageid.message.Message in ZODB...
    #      I'm not changing the behaviour at this point, but I wonder
    #      if it will bite us or become a common thing in ST.
    categories[u'assignment'] = _('Assignment')
    categories[u'essay'] = _('Essay')
    categories[u'exam'] = _('Exam')
    categories[u'homework'] = _('Homework')
    categories[u'journal'] = _('Journal')
    categories[u'lab'] = _('Lab')
    categories[u'presentation'] = _('Presentation')
    categories[u'project'] = _('Project')
    categories.default_key = u'assignment'


class GradebookAppStartup(StartUpBase):
    def __call__(self):
        setUpGradebookRoot(self.app)

        if CATEGORIES_KEY not in self.app:
            categories = self.app[CATEGORIES_KEY] = CategoryContainer()
            setUpDefaultCategories(categories)


class GradebookInit(InitBase):
    def __call__(self):
        setUpGradebookRoot(self.app)
        categories = self.app[CATEGORIES_KEY] = CategoryContainer()
        setUpDefaultCategories(categories)


def getGradebookRoot(app):
    if GRADEBOOK_ROOT_KEY not in app:
        return None
    return app[GRADEBOOK_ROOT_KEY]


def getGradebookTemplates(root):
    root = removeSecurityProxy(root)
    templates = removeSecurityProxy(root.templates)
    return templates

