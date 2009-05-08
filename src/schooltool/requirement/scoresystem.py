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
"""ScoreSystem Interfaces

$Id$
"""
__docformat__ = 'restructuredtext'

from decimal import Decimal

from persistent import Persistent

from zope.app.component.vocabulary import UtilityVocabulary
from zope.component import adapts, queryMultiAdapter
from zope.interface import implements
import zope.interface
import zope.schema
import zope.security.checker
from zope.security.proxy import removeSecurityProxy

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.requirement import interfaces
from schooltool.requirement.interfaces import IDiscreteValuesScoreSystem
from schooltool.requirement.interfaces import IScoreSystemsProxy


def ScoreSystemsVocabulary(context):
    return UtilityVocabulary(context,
                             interface=interfaces.IScoreSystem)


class UNSCORED(object):
    """This object behaves like a string.

    We want this to behave as a global, meaning it's pickled by name, rather
    than value. We need to arrange that it has a suitable __reduce__.
    """

    def __reduce__(self):
        return 'UNSCORED'

    def __repr__(self):
        return 'UNSCORED'


zope.security.checker.BasicTypes[UNSCORED] = zope.security.checker.NoProxy
UNSCORED = UNSCORED()


class AbstractScoreSystem(object):
    zope.interface.implements(interfaces.IScoreSystem)

    def __init__(self, title, description=None):
        self.title = title
        self.description = description

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.title)

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError


class CommentScoreSystem(AbstractScoreSystem):

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return True
        return isinstance(score, (str, unicode))

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        if not rawScore:
            return UNSCORED
        return rawScore

    def __reduce__(self):
        return 'CommentScoreSystem'


# Singelton
CommentScoreSystem = CommentScoreSystem(
    u'Comments', u'Scores are commentary text.')


class AbstractValuesScoreSystem(AbstractScoreSystem):
    zope.interface.implements(interfaces.IValuesScoreSystem)

    def __init__(self, title, description=None):
        self.title = title
        self.description = description

    def isPassingScore(self, score):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError

    def getBestScore(self):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError

    def getNumericalValue(self, score):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError

    def getFractionValue(self, score):
        """See interfaces.IScoreSystem"""
        raise NotImplementedError


class DiscreteValuesScoreSystem(AbstractValuesScoreSystem):
    """Abstract Discrete Values Score System"""

    zope.interface.implements(interfaces.IDiscreteValuesScoreSystem)

    # See interfaces.IDiscreteValuesScoreSystem
    scores = None
    _minPassingScore = None
    _bestScore = None
    hidden = False

    def __init__(self, title=None, description=None,
                 scores=None, bestScore=None, minPassingScore=None):
        self.title = title
        self.description = description
        self.scores = scores or []
        self._bestScore = bestScore
        self._minPassingScore = minPassingScore

    def isPassingScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return None
        if self._minPassingScore is None:
            return None
        scores = self.scoresDict()
        return scores[score] >= scores[self._minPassingScore]

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        scores = self.scoresDict().keys()
        return score in scores + [UNSCORED]

    def getBestScore(self):
        """See interfaces.IScoreSystem"""
        return self._bestScore

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        if rawScore == '':
            return UNSCORED

        if not self.isValidScore(rawScore):
            raise zope.schema.ValidationError(
                "'%s' is not a valid score." %rawScore)
        return rawScore

    def getNumericalValue(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return None
        scores = self.scoresDict()
        return scores[score]

    def getFractionalValue(self, score):
        """See interfaces.IScoreSystem"""
        # get maximum and minimum score to determine the range
        maximum = self.scores[0][1]
        minimum = self.scores[-1][1]
        # normalized numerical score
        value = self.getNumericalValue(score) - minimum
        return value / (maximum - minimum)

    def scoresDict(self):
        scores = [(score, value) for score, value, percent in self.scores]
        return dict(scores)

class GlobalDiscreteValuesScoreSystem(DiscreteValuesScoreSystem):

    def __init__(self, name, *args, **kwargs):
        self.__name__ = name
        super(GlobalDiscreteValuesScoreSystem, self).__init__(*args, **kwargs)

    def __reduce__(self):
        return self.__name__


PassFail = GlobalDiscreteValuesScoreSystem(
    'PassFail',
    u'Pass/Fail', u'Pass or Fail score system.',
    [(u'Pass', Decimal(1), Decimal(60)), 
     (u'Fail', Decimal(0), Decimal(0))], 
     u'Pass', u'Pass')

AmericanLetterScoreSystem = GlobalDiscreteValuesScoreSystem(
    'AmericanLetterScoreSystem',
    u'Letter Grade', u'American Letter Grade',
    [('A', Decimal(4), Decimal(90)), 
     ('B', Decimal(3), Decimal(80)), 
     ('C', Decimal(2), Decimal(70)),
     ('D', Decimal(1), Decimal(60)), 
     ('F', Decimal(0), Decimal(0))], 
     'A', 'D')

ExtendedAmericanLetterScoreSystem = GlobalDiscreteValuesScoreSystem(
    'ExtendedAmericanLetterScoreSystem',
    u'Extended Letter Grade', u'American Extended Letter Grade',
    [('A+', Decimal('4.0'), Decimal(98)), 
     ('A', Decimal('4.0'), Decimal(93)), 
     ('A-', Decimal('3.7'), Decimal(90)),
     ('B+', Decimal('3.3'), Decimal(88)), 
     ('B', Decimal('3.0'), Decimal(83)), 
     ('B-', Decimal('2.7'), Decimal(80)),
     ('C+', Decimal('2.3'), Decimal(78)), 
     ('C', Decimal('2.0'), Decimal(73)), 
     ('C-', Decimal('1.7'), Decimal(70)),
     ('D+', Decimal('1.3'), Decimal(68)), 
     ('D', Decimal('1.0'), Decimal(63)), 
     ('D-', Decimal('0.7'), Decimal(60)),
     ('F',  Decimal('0.0'), Decimal(0))], 
     'A+', 'D-')


class RangedValuesScoreSystem(AbstractValuesScoreSystem):
    """Abstract Ranged Values Score System"""

    zope.interface.implements(interfaces.IRangedValuesScoreSystem)

    # See interfaces.IRangedValuesScoreSystem
    min = None
    max = None
    _minPassingScore = None

    def __init__(self, title=None, description=None,
                 min=Decimal(0), max=Decimal(100), minPassingScore=None):
        self.title = title
        self.description = description
        self.min, self.max = Decimal(min), Decimal(max)
        if minPassingScore is not None:
            minPassingScore = Decimal(minPassingScore)
        self._minPassingScore = minPassingScore

    def isPassingScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED or self._minPassingScore is None:
            return None
        return score >= self._minPassingScore

    def isValidScore(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return True
        return score >= self.min

    def getBestScore(self):
        """See interfaces.IScoreSystem"""
        return self.max

    def fromUnicode(self, rawScore):
        """See interfaces.IScoreSystem"""
        if rawScore == '':
            return UNSCORED

        try:
            score = Decimal(rawScore)
        except:
            raise ValueError

        if not self.isValidScore(score):
            raise zope.schema.ValidationError(
                "%r is not a valid score." %score)
        return score

    def getNumericalValue(self, score):
        """See interfaces.IScoreSystem"""
        if score is UNSCORED:
            return None
        return Decimal(score)

    def getFractionalValue(self, score):
        """See interfaces.IScoreSystem"""
        # normalized numerical score
        value = self.getNumericalValue(score) - self.min
        return value / (self.max - self.min)


class GlobalRangedValuesScoreSystem(RangedValuesScoreSystem):

    def __init__(self, name, *args, **kwargs):
        self.__name__ = name
        super(GlobalRangedValuesScoreSystem, self).__init__(*args, **kwargs)

    def __reduce__(self):
        return self.__name__


PercentScoreSystem = GlobalRangedValuesScoreSystem(
    'PercentScoreSystem',
    u'Percent', u'Percent Score System', Decimal(0), Decimal(100), Decimal(60))

HundredPointsScoreSystem = GlobalRangedValuesScoreSystem(
    'HundredPointsScoreSystem',
    u'100 Points', u'100 Points Score System',
    Decimal(0), Decimal(100), Decimal(60))


class ICustomScoreSystem(zope.interface.Interface):
    """Marker interface for score systems created in the widget."""


class IScoreSystemField(zope.schema.interfaces.IField):
    """A field that represents score system."""


class ScoreSystemField(zope.schema.Field):
    """Score System Field."""
    zope.interface.implements(IScoreSystemField)


class CustomScoreSystem(DiscreteValuesScoreSystem, Persistent):
    """ScoreSystem class for custom (user-created) score systems"""

    implements(interfaces.ICustomScoreSystem)


class ScoreSystemsProxy(object):
    """The Proxy class for adding/editing score systems"""

    implements(IScoreSystemsProxy)
    adapts(ISchoolToolApplication)

    def __init__(self, app):
        self.app = app
        self.siteManager = app.getSiteManager()
        self.__parent__ = app
        self.__name__ = 'scoresystems'

    def getScoreSystems(self):
        """Return list of tuples (name, scoresystem)"""
        results = []
        for name, util in sorted(self.siteManager.getUtilitiesFor(
                                 interfaces.ICustomScoreSystem)):
            util = removeSecurityProxy(util)
            if util.hidden:
                continue
            results.append((name, util))
        return results

    def addScoreSystem(self, scoresystem):
        """Add scoresystem to app utilitiles"""
        names = [name for name, util in self.getScoreSystems()]
        name = u''.join([c for c in scoresystem.title.lower()
                         if c.isalnum() or c == ' ']).replace(' ', '-')
        n = name
        i = 1
        while n in names:
            n = name + u'-' + unicode(i)
            i += 1
        self.siteManager.registerUtility(scoresystem, 
            interfaces.ICustomScoreSystem, name=n)

    def getScoreSystem(self, name):
        """Get scoresystem from app utilitiles by the given name"""
        for n, util in self.getScoreSystems():
            if n == name:
                return removeSecurityProxy(util)
        raise KeyError

