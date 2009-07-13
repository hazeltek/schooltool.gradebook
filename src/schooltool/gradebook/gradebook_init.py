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
Gradebook Initialization
"""

from persistent import Persistent
from zope.app.container import btree
from zope.app.container.contained import contained, Contained
from zope.component import adapts
from zope.interface import implements
from zope.security.proxy import removeSecurityProxy

from schooltool.app.app import InitBase, StartUpBase
from schooltool.app.interfaces import IApplicationStartUpEvent
from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.schoolyear.subscriber import ObjectEventAdapterSubscriber

from schooltool.gradebook.interfaces import IGradebookRoot, IGradebookTemplates
from schooltool.gradebook.interfaces import IGradebookDeployed
from schooltool.gradebook.interfaces import IGradebookLayouts, IReportLayout
from schooltool.gradebook.interfaces import IReportColumn
from schooltool.gradebook.category import getCategories
from schooltool.requirement.requirement import Requirement

from schooltool.common import SchoolToolMessage as _

GRADEBOOK_ROOT_KEY = 'schooltool.gradebook'


class GradebookRoot(object):
    """Root of gradebook data"""

    implements(IGradebookRoot)

    def __init__(self):
        self.templates = GradebookTemplates(_('Report Sheet Templates'))
        self.deployed = GradebookDeployed(_('Deployed Report Sheets'))
        self.layouts = GradebookLayouts(_('Report Card Layouts'))


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


class ReportColumn(Persistent):
    """A column of the report card layout"""

    implements(IReportColumn)

    def __init__(self, source, heading):
        self.source = source
        self.heading = heading


def setUpGradebookRoot(app):
    """Create Gradebook Root Object if not already there"""

    if GRADEBOOK_ROOT_KEY not in app:
        app[GRADEBOOK_ROOT_KEY] = GradebookRoot()


def setUpDefaultCategories(dict):
    dict.addValue('assignment', 'en', _('Assignment'))
    dict.addValue('essay', 'en', _('Essay'))
    dict.addValue('exam', 'en', _('Exam'))
    dict.addValue('homework', 'en', _('Homework'))
    dict.addValue('journal', 'en', _('Journal'))
    dict.addValue('lab', 'en', _('Lab'))
    dict.addValue('presentation', 'en', _('Presentation'))
    dict.addValue('project', 'en', _('Project'))
    dict.setDefaultLanguage('en')
    dict.setDefaultKey('assignment')


class GradebookAppStartup(StartUpBase):
    def __call__(self):
        setUpGradebookRoot(self.app)
        dict = getCategories(self.app)
        if not dict.getKeys():
            setUpDefaultCategories(dict)


class GradebookInit(InitBase):
    def __call__(self):
        setUpGradebookRoot(self.app)
        dict = getCategories(self.app)
        setUpDefaultCategories(dict)


def getGradebookRoot(app):
    return app[GRADEBOOK_ROOT_KEY]


def getGradebookTemplates(root):
    root = removeSecurityProxy(root)
    templates = removeSecurityProxy(root.templates)
    contained(templates, root, 'templates')
    return templates

