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
"""Gradebook interfaces

$Id$
"""
__docformat__ = 'reStructuredText'

import datetime

from zope.interface import Interface, Attribute
import zope.schema
from zope.app.container.interfaces import IContainer, IContained
from zope.app.container.constraints import containers, contains
import zope.interface
from zope.app import container
from zope.schema.interfaces import IIterableSource
from schooltool.requirement import interfaces, scoresystem
from schooltool.common import SchoolToolMessage as _


class IGradebookRoot(Interface):
    """The root of gradebook data"""

    templates = Attribute("""Container of report sheet templates""")

    deployed = Attribute("""Container of deployed report sheet templates""")

    layouts = Attribute("""Container of report card layouts""")


class IGradebookTemplates(interfaces.IRequirement):
    """Container of Report Sheet Templates"""

    contains('.IReportWorksheet')


class IGradebookDeployed(interfaces.IRequirement):
    """Container of Deployed Report Sheet Templates (by term)"""

    contains('.IReportWorksheet')


class IGradebookLayouts(interfaces.IRequirement):
    """Container of Report Card Layouts (by schoolyear)"""

    contains('.IReportLayout')


class IActivities(interfaces.IRequirement):
    '''A list of worksheets containing activities that must be fulfilled in a
       course or section.'''

    def resetCurrentWorksheet():
        """Reset the currently active worksheet to first or None."""

    def getCurrentWorksheet():
        """Get the currently active worksheet."""

    def setCurrentWorksheet(worksheet):
        """Set the currently active worksheet."""

    def getCurrentActivities():
        """Get the activities for the currently active worksheet."""

    contains('.IWorksheet')


class IWorksheet(interfaces.IRequirement):
    '''A list of activities that must be fulfilled in a course or section.'''

    deployed = zope.schema.Bool(
        title=u"Deployed Worksheet",
        required=False
        )

    def getCategoryWeights():
        """Get the category weights for the worksheet.  This method will
           return a list of (category, weight) tuples, the weight being
           a Decimal object."""

    def setCategoryWeight(category, weight):
        """Set the weight for the given category.  Any numeric type is 
           acceptable"""

    containers(IActivities)
    contains('.IActivity')


class IReportWorksheet(interfaces.IRequirement):
    '''A list of report card activities that get copied into sections.'''

    containers(IGradebookTemplates, IGradebookDeployed)
    contains('.IReportActivity')


class IActivity(interfaces.IRequirement):
    '''An activity to be graded'''

    due_date = zope.schema.Date(
        title=_("Due Date"),
        description=_("The date the activity is due to be graded."),
        required=True,
        default = datetime.date.today())

    label = zope.schema.TextLine(
        title=_(u"Label"),
        description=_("The column label for the activity in the gradebook."),
        required=False)

    description = zope.schema.Text(
        title=_("Description"),
        description=_("A detailed description of the activity."),
        required=False)

    category = zope.schema.Choice(
        title=_("Category"),
        description=_("The activity category"),
        vocabulary="schooltool.gradebook.categories",
        required=True)

    scoresystem = scoresystem.ScoreSystemField(
        title=_("Scoresystem"),
        description=_("The activity scoresystem."),
        required=True)

    date = zope.schema.Date(
        title=_("Date"),
        description=_("The date the activity was created."),
        required=True)

    containers(IWorksheet)


class IReportActivity(IActivity):
    '''An activity to be deployed to section activities'''

    containers(IReportWorksheet)


class IReportLayout(Interface):
    '''The layout of the report card for the school year'''

    columns = zope.schema.List(
        title=_('Columns'),
        description=_('Columns to be printed in the report card.'))

    containers(IGradebookLayouts)


class IEditGradebook(Interface):

    def evaluate(student, activity, score, evaluator=None):
        """Evaluate a student for an activity"""

    def removeEvaluation(student, activity):
        """Remove evaluation."""
        
    def setFinalGradeAdjustment(person, student, adjustment, reason):
        """Set the final grade adjustment for the given student."""
    

class IReadGradebook(Interface):

    worksheets = zope.schema.List(
        title=_('Worksheets'),
        description=_('Worksheets in this gradebook.'))

    activities = zope.schema.List(
        title=_('Activities'),
        description=_('Activities in this gradebook.'))

    students = zope.schema.List(
        title=_('Students'),
        description=_('Students in this gradebook.'))

    def hasEvaluation(student, activity):
        """Check whether an evaluation exists for a student-activity pair."""

    def getEvaluation(student, activity, default=None):
        """Get the evaluation of a student for a given activity."""

    def getCurrentEvaluationsForStudent(student):
        """Get the evaluations of the curretn worksheet for this student.

        Return iterable of 2-tuples of the form (activity, evaluation).
        """
    def getEvaluationsForStudent(student):
        """Get the evaluations of the section for this student.

        Return iterable of 2-tuples of the form (activity, evaluation).
        """

    def getEvaluationsForActivity(activity):
        """Get the evaluations of a particular activity in the section.

        Return iterable of 2-tuples of the form (student, evaluation).
        """

    def getWorksheetActivities(worksheet):
        """Get the activities for the given worksheet."""

    def getWorksheetAverage(worksheet, student):
        """Calculate the average for the worksheet, student pair."""

    def getCurrentWorksheet(person):
        """Get the user's currently active worksheet."""

    def setCurrentWorksheet(person, worksheet):
        """Set the user's currently active worksheet."""

    def getDueDateFilter(person):
        """Get the user's current due date filter setting."""

    def setDueDateFilter(person, flag, weeks):
        """Set the user's current due date filter setting."""

    def getCurrentActivities(person):
        """Get the activities for the user's currently active worksheet."""

    def getSortKey(person):
        """Get the sortkey for the gradebook table."""

    def setSortKey(person, value):
        """Set the sortkey for the gradebook table.

        The value is a 2-tuple. The entry in the tuple is either "student" to
        sort by student title or the hash of the activity. The second entry
        specifies whether the sorting is reversed.
        """

    def getFinalGradeAdjustment(person, student):
        """Get the final grade adjustment for the given student."""

    def getFinalGrade(student):
        """Get the final grade for the given student."""

    def getAdjustedFinalGrade(person, student):
        """Get the adjusted final grade for the given student."""


class IGradebook(IReadGradebook, IEditGradebook):
    """The gradebook of a section.

    The gradebook provides an API that allows the user to treat it like a
    gradebook spreadsheet/table.
    """


class IMyGrades(Interface):
    """The students gradebook for a section.

    This interface provides an API that allows the studentto see their
    grades for a section.
    """
    worksheets = zope.schema.List(
        title=_('Worksheets'),
        description=_('Worksheets in this gradebook.'))

    def getEvaluation(student, activity, default=None):
        """Get the evaluation of a student for a given activity."""

    def getCurrentWorksheet():
        """Get the currently active worksheet."""

    def getCurrentActivities():
        """Get the activities for the currently active worksheet."""

    def setCurrentWorksheet(worksheet):
        """Set the currently active worksheet."""


class ILinkedActivity(IActivity):
    """An activity that can be linked to an external activity"""

    source = zope.schema.TextLine(
        title=_(u"External Activity Source"),
        description=_(u"The registration name of the source"),
        required=True)
        
    external_activity_id = zope.schema.TextLine(
        title=_(u"External Activity ID"),
        description=_(u"A unique identifier for the external activity"),
        required=True)
    
    points = zope.schema.Int(
        title=_(u"Points"),
        description=_(u"Points value to calculate the activity grade"),
        min=0,
        required=True)

    def getExternalActivity():
        """Returns the external activity to which this activity is linked.

        Return None if it cannot find an appropiate external activity"""


class IExternalActivitiesSource(IIterableSource):
    """Source with all external activities"""


# These should be provided by plugin programmers

class IExternalActivities(zope.interface.Interface):
    """External activities of a section"""
 
    source = zope.schema.TextLine(
        title=_(u"External Activity Source"),
        description=_(u"The name under which the adapter is registered"),
        required=True)

    title = zope.schema.TextLine(
        title=_(u"Title"),
        description=_(u"A brief title of the external activities source"),
        required=True)

    def getExternalActivities():
        """Return a list of IExternalActivity objects for its context
        section"""

    def getExternalActivity(external_activity_id):
        """Return an IExternalActivity object matching the provided id.

        Return None if it cannot find an appropiate external activity"""


class IExternalActivity(zope.interface.Interface):
    """An external activity"""

    source = zope.schema.TextLine(
        title=_(u"External Activity Source"),
        description=_(u"The registration name of the source"),
        required=True)
        
    external_activity_id = zope.schema.TextLine(
        title=_(u"External Activity ID"),
        description=_(u"A unique identifier for the external activity"),
        required=True)
    
    title = zope.schema.TextLine(
        title=_(u"Title"),
        description=_(u"A brief title of the external activity."),
        required=True)

    description = zope.schema.Text(
        title=_("Description"),
        description=_("A detailed description of the external activity."),
        required=False)

    def getGrade(student):
        """Get the grade for an external activity.

        Return a Decimal percentage representing the grade for the
        given student. If there is no grade for that student for that
        external activity, None should be returned"""

    def __eq__(another):
        """Compare equality with other external activities"""
