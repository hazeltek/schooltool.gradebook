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
"""Score System Browser Code

$Id$
"""
__docformat__ = 'reStructuredText'

from decimal import Decimal

import zope.formlib
import zope.schema
from zope.app.form import utility
from zope.browserpage import ViewPageTemplateFile
from zope.container.interfaces import INameChooser
from zope.publisher.browser import BrowserView
from zope.security.proxy import removeSecurityProxy
from zope.traversing.browser.absoluteurl import absoluteURL
from zope.interface import implements, directlyProvides

from schooltool.app.interfaces import ISchoolToolApplication
from schooltool.gradebook import GradebookMessage as _
from schooltool.requirement import interfaces, scoresystem


MISSING_TITLE = _('The Title field must not be empty.')
VALUE_NOT_NUMERIC = _('Value field must contain a valid number.')
PERCENT_NOT_NUMERIC = _('Percent field must contain a valid number.')
NO_NEGATIVE_VALUES = _('All values must be non-negative.')
NO_NEGATIVE_PERCENTS = _('All percentages must be non-negative.')
NO_PERCENTS_OVER_100 = _('Percentages cannot be greater than 100.')
MUST_HAVE_AT_LEAST_2_SCORES = _('A score system must have at least two scores.')
VALUES_MUST_DESCEND = _('Score values must go in descending order.')
PERCENTS_MUST_DESCEND = _('Score percentages must go in descending order.')
LAST_PERCENT_NOT_ZERO = _('The last percentage must be zero.')
DUPLICATE_DISPLAYED = _('Duplicate scores are not allowed.')
DUPLICATE_ABBREVIATION = _('Duplicate abbreviations are not allowed.')


class ScoreSystemContainerView(BrowserView):
    """A view for maintaining custom score systems"""

    def update(self):
        if 'form-submitted' in self.request:
            for name, ss in self.context.items():
                ss = removeSecurityProxy(ss)
                if 'hide_' + name in self.request:
                    ss.hidden = True

    def scoresystems(self):
        app = ISchoolToolApplication(None)
        url = absoluteURL(app, self.request) + '/scoresystems'
        results = []
        for name, ss in self.context.items():
            ss = removeSecurityProxy(ss)
            if not ss.hidden:
                result = {
                    'title': ss.title,
                    'url': '%s/%s' % (url, name),
                    'hide_name': 'hide_' + name,
                    }
                results.append(result)
        return results


class CustomScoreSystemAddView(BrowserView):
    """A view for adding a custom score system"""

    def update(self):
        self.message = ''

        if 'form-submitted' in self.request:
            if 'CANCEL' in self.request:
                self.request.response.redirect(self.nextURL())

            if not self.validateForm():
                return
            if 'UPDATE_SUBMIT' in self.request:
                if not self.validateScores():
                    return
                target = scoresystem.CustomScoreSystem()
                self.updateScoreSystem(target)
                self.addScoreSystem(target)
                self.request.response.redirect(self.nextURL())

    def addScoreSystem(self, target):
        chooser = INameChooser(self.context)
        name = chooser.chooseName('', target)
        self.context[name] = target

    def nextURL(self):
        return absoluteURL(self.context, self.request)

    def scores(self):
        rownum = 1
        results = []
        for displayed, abbr, value, percent in self.getRequestScores():
            results.append(self.buildScoreRow(rownum, displayed, abbr, value, 
                percent))
            rownum += 1
        results.append(self.buildScoreRow(rownum, '', '', '', ''))
        return results

    def buildScoreRow(self, rownum, displayed, abbr, value, percent):
        return {
            'displayed_name': 'displayed' + unicode(rownum),
            'displayed_value': displayed,
            'abbr_name': 'abbr' + unicode(rownum),
            'abbr_value': abbr,
            'value_name': 'value' + unicode(rownum),
            'value_value': value,
            'percent_name': 'percent' + unicode(rownum),
            'percent_value': percent,
            }

    def getRequestScores(self):
        rownum = 0
        results = []
        while True:
            rownum += 1
            displayed_name = 'displayed' + unicode(rownum)
            abbr_name = 'abbr' + unicode(rownum)
            value_name = 'value' + unicode(rownum)
            percent_name = 'percent' + unicode(rownum)
            if displayed_name not in self.request:
                break
            if not len(self.request[displayed_name]):
                continue
            result = (self.request[displayed_name],
                      self.request[abbr_name],
                      self.request[value_name],
                      self.request[percent_name])
            results.append(result)
        return results

    def validateForm(self):
        title = self.request['title']
        if not len(title):
            return self.setMessage(MISSING_TITLE)

        scores = []
        for displayed, abbr, value, percent in self.getRequestScores():
            try:
                decimal_value = Decimal(value)
            except:
                return self.setMessage(VALUE_NOT_NUMERIC)
            if decimal_value < 0:
                return self.setMessage(NO_NEGATIVE_VALUES)
            try:
                decimal_percent = Decimal(percent)
            except:
                return self.setMessage(PERCENT_NOT_NUMERIC)
            if decimal_percent < 0:
                return self.setMessage(NO_NEGATIVE_PERCENTS)
            if decimal_percent > 100:
                return self.setMessage(NO_PERCENTS_OVER_100)
            scores.append([displayed, abbr, decimal_value, decimal_percent])

        self.validTitle = title
        self.validScores = scores
        return True

    def validateScores(self):
        if len(self.validScores) < 2:
            return self.setMessage(MUST_HAVE_AT_LEAST_2_SCORES)

        last_value, last_percent = None, None
        disp_list, abbr_list = [], []
        for displayed, abbr, value, percent in self.validScores:
            if last_value is not None:
                if value >= last_value:
                    return self.setMessage(VALUES_MUST_DESCEND)
            if last_percent is not None:
                if percent >= last_percent:
                    return self.setMessage(PERCENTS_MUST_DESCEND)
            for d in disp_list:
                if d.lower() == displayed.lower():
                    return self.setMessage(DUPLICATE_DISPLAYED)
            if abbr:
                for a in abbr_list:
                    if a.lower() == abbr.lower():
                        return self.setMessage(DUPLICATE_ABBREVIATION)
            last_value = value
            last_percent = percent
            disp_list.append(displayed)
            abbr_list.append(abbr)

        if last_percent <> 0:
            return self.setMessage(LAST_PERCENT_NOT_ZERO)

        return True

    def setMessage(self, message):
        self.message = message
        return False

    def updateScoreSystem(self, target):
        target.title = self.validTitle
        target.scores = self.validScores
        target._bestScore = target.scores[0][0]
        target._minPassingScore = self.request.get('minScore')
        target._isMaxPassingScore = self.request.get('minMax') == 'max'

    @property
    def title_value(self):
        if 'form-submitted' in self.request:
            return self.request['title']
        else:
            return ''

    def getMinMax(self):
        results = []
        for form_id, title in[('min', _('Minimum')), ('max', _('Maximum'))]:
            selected = (self.request.get('minMax') == form_id)
            result = {
                'title': title,
                'form_id': form_id,
                'selected': selected,
                }
            results.append(result)
        return results

    def getMinScores(self):
        results = []
        for displayed, abbr, value, percent in self.getRequestScores():
            selected = (self.request.get('minScore') == displayed)
            result = {
                'title': displayed,
                'form_id': displayed,
                'selected': selected,
                }
            results.append(result)
        return results


class CustomScoreSystemView(BrowserView):
    """A view for viewing a custom score system"""

    def scores(self):
        result = []
        for displayed, abbr, value, percent in self.context.scores:
            if self.context.isPassingScore(displayed):
                passing = _('Yes')
            else:
                passing = _('No')
            row = self.buildScoreRow(displayed, abbr, value, percent, passing)
            result.append(row)
        return result

    def buildScoreRow(self, displayed, abbr, value, percent, passing):
        return {
            'displayed_value': displayed,
            'abbr_value': abbr,
            'value_value': value,
            'percent_value': percent,
            'passing_value': passing,
            }

    @property
    def nextURL(self):
        app = ISchoolToolApplication(None)
        return absoluteURL(app, self.request) + '/scoresystems'


class IWidgetData(interfaces.IRangedValuesScoreSystem):
    """A schema used to generate the score system widget."""

    existing = zope.schema.Choice(
        title=_('Existing Score System'),
        vocabulary='schooltool.requirement.scoresystems',
        required=False)

    custom = zope.schema.Bool(
        title=_('Custom score system'),
        required=True)


class WidgetData(object):
    """A simple object used to simulate the widget data."""

    existing = None
    custom = False
    min = 0
    max = 100


class ScoreSystemWidget(object):
    """Score System Widget"""
    implements(zope.formlib.interfaces.IBrowserWidget,
               zope.formlib.interfaces.IInputWidget)

    template = ViewPageTemplateFile('scoresystemwidget.pt')
    _prefix = 'field.'
    _error = ''

    # See zope.formlib.interfaces.IWidget
    name = None
    label = property(lambda self: self.context.title)
    hint = property(lambda self: self.context.description)
    visible = True
    # See zope.formlib.interfaces.IInputWidget
    required = property(lambda self: self.context.required)

    def __init__(self, field, request):
        self.context = field
        self.request = request
        data = WidgetData()
        if interfaces.IRequirement.providedBy(field.context):
            ss = field.context.scoresystem
            if scoresystem.ICustomScoreSystem.providedBy(ss):
                data.custom = True
                data.min = ss.min
                data.max = ss.max
            else:
                data.existing = ss
        self.name = self._prefix + field.__name__
        utility.setUpEditWidgets(self, IWidgetData, source=data,
                                 prefix=self.name+'.')


    def setRenderedValue(self, value):
        """See zope.formlib.interfaces.IWidget"""
        if scoresystem.ICustomScoreSystem.providedBy(value):
            self.custom_widget.setRenderedValue(True)
            self.min_widget.setRenderedValue(value.min)
            self.max_widget.setRenderedValue(value.max)
        else:
            self.existing_widget.setRenderedValue(value)


    def setPrefix(self, prefix):
        """See zope.formlib.interfaces.IWidget"""
        # Set the prefix locally
        if not prefix.endswith("."):
            prefix += '.'
        self._prefix = prefix
        self.name = prefix + self.context.__name__
        # Now distribute it to the sub-widgets
        for widget in [getattr(self, name+'_widget')
                       for name in zope.schema.getFieldNames(IWidgetData)]:
            widget.setPrefix(self.name+'.')


    def getInputValue(self):
        """See zope.formlib.interfaces.IInputWidget"""
        if self.custom_widget.getInputValue():
            min = self.min_widget.getInputValue()
            max = self.max_widget.getInputValue()
            custom = scoresystem.RangedValuesScoreSystem(
                u'generated', min=min, max=max)
            directlyProvides(custom, scoresystem.ICustomScoreSystem)
            return custom
        else:
            return self.existing_widget.getInputValue()


    def applyChanges(self, content):
        """See zope.formlib.interfaces.IInputWidget"""
        field = self.context
        new_value = self.getInputValue()
        old_value = field.query(content, self)
        # The selection of an existing scoresystem has not changed
        if new_value == old_value:
            return False
        # Both, the new and old score system are generated
        if (scoresystem.ICustomScoreSystem.providedBy(new_value) and
            scoresystem.ICustomScoreSystem.providedBy(old_value)):
            # If they both have the same min and max value, then there is no
            # change
            if (new_value.min == old_value.min and
                new_value.max == old_value.max):
                return False

        field.set(content, new_value)
        return True


    def hasInput(self):
        """See zope.formlib.interfaces.IInputWidget"""
        flag = ((self.existing_widget.hasInput() and
                 self.existing_widget.getInputValue()) or
                (self.custom_widget.hasValidInput() and
                 self.custom_widget.getInputValue()))
        if not flag:
            self._error = _('Required input is missing.')
        return bool(flag)


    def hasValidInput(self):
        """See zope.formlib.interfaces.IInputWidget"""
        if (self.custom_widget.hasValidInput() and
            self.custom_widget.getInputValue()):
            return (self.min_widget.hasValidInput() and
                    self.min_widget.hasValidInput())

        return self.existing_widget.hasValidInput()


    def hidden(self):
        """See zope.formlib.browser.interfaces.IBrowserWidget"""
        if (self.custom_widget.hasValidInput() and
            self.custom_widget.getInputValue()):
            output = []
            output.append(self.custom_widget.hidden())
            output.append(self.min_widget.hidden())
            output.append(self.max_widget.hidden())
            return '\n'.join(output)

        return self.existing_widget.hidden()


    def error(self):
        """See zope.formlib.browser.interfaces.IBrowserWidget"""
        if self._error:
            return self._error

        custom_error = self.custom_widget.error()
        if custom_error:
            return custom_error
        if (self.custom_widget.hasInput() and
            self.custom_widget.getInputValue()):
            min_error = self.min_widget.error()
            if min_error:
                return min_error
            max_error = self.max_widget.error()
            if max_error:
                return max_error

        return self.existing_widget.error()


    def __call__(self):
        """See zope.formlib.browser.interfaces.IBrowserWidget"""
        return self.template()
