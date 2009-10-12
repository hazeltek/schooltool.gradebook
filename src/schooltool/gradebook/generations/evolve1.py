#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2008 Shuttleworth Foundation
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
Evolve database to generation 1.

Moves hard-coded score system utilities to the app site manager.
"""

from zope.app.zopeappgenerations import getRootFolder

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.course.interfaces import ISectionContainer
from schooltool.gradebook.interfaces import IActivities, IGradebookRoot
from schooltool.gradebook.gradebook_init import setUpGradebookRoot
from schooltool.person.interfaces import IPersonContainer
from schooltool.schoolyear.interfaces import ISchoolYearContainer
from schooltool.requirement.interfaces import IScoreSystemsProxy
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IEvaluations
from schooltool.requirement.scoresystem import CustomScoreSystem, PassFail
from schooltool.requirement.scoresystem import AmericanLetterScoreSystem
from schooltool.requirement.scoresystem import ExtendedAmericanLetterScoreSystem


def updateEvaluations(app, ss, custom_ss):
    """Update all evaluations using the hard-coded score system to use the 
       newly created custom score system"""

    for person in app['persons'].values():
        evaluations = IEvaluations(person)
        for evaluation in evaluations.values():
            if evaluation.scoreSystem == ss:
                evaluation.scoreSystem = custom_ss
                person._p_changed = True


def updateObjActivities(obj, activities, ss, custom_ss):
    """Update the obj activities using the hard-coded score system to use the 
       newly created custom score system"""

    for worksheet in activities.values():
        for activity in worksheet.values():
            if activity.scoresystem == ss:
                activity.scoresystem = custom_ss
                obj._p_changed = True


def updateAllActivities(app, ss, custom_ss):
    """Update all activities using the hard-coded score system to use the 
       newly created custom score system"""

    for sections in app['schooltool.course.section'].values():
        for section in sections.values():
            updateObjActivities(section, IActivities(section), ss, custom_ss)

    root = IGradebookRoot(app)
    if root is None:
        return
    updateObjActivities(root, root.templates, ss, custom_ss)
    updateObjActivities(root, root.deployed, ss, custom_ss)


def evolve(context):
    """Migrates hard-coded discrete values score systems found in
       schooltool.requirement.scoresystem to the app site manager"""

    app = getRootFolder(context)
    setUpGradebookRoot(app)
    ssProxy = IScoreSystemsProxy(app)
    for ss in [PassFail, AmericanLetterScoreSystem, 
               ExtendedAmericanLetterScoreSystem]:
        custom_ss = CustomScoreSystem(ss.title, ss.description, ss.scores,
            ss._bestScore, ss._minPassingScore)
        ssProxy.addScoreSystem(custom_ss)
        updateEvaluations(app, ss, custom_ss)
        updateAllActivities(app, ss, custom_ss)

