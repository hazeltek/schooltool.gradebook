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
Request PDF Views
"""

from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.publisher.browser import BrowserView
from zope.traversing.browser.absoluteurl import absoluteURL

from schooltool.common import SchoolToolMessage as _


class BaseView(BrowserView):
    """Base class for all request report views"""

    template=ViewPageTemplateFile('request_reports.pt')

    def __call__(self):
        return self.template()


class StudentReportsView(BaseView):

    def title(self):
        return _('Student Reports')

    def links(self):
        url = absoluteURL(self.context, self.request)
        results = [
            {
                'url': url +  '/report_card.pdf',
                'content': _('Download Report Card'),
            },
            {
                'url': url +  '/student_detail.pdf',
                'content': _('Download Student Detail Report'),
            },
        ]
        return results


class GroupReportsView(BaseView):

    def title(self):
        return _('Group Reports')

    def links(self):
        url = absoluteURL(self.context, self.request)
        results = [
            {
                'url': url +  '/report_card.pdf',
                'content': _('Download Report Card'),
            },
            {
                'url': url +  '/student_detail.pdf',
                'content': _('Download Student Detail Report'),
            },
         ]
        return results


class SchoolYearReportsView(BaseView):

    def title(self):
        return _('School Year Reports')

    def links(self):
        url = absoluteURL(self.context, self.request)
        results = [
            {
                'url': url +  '/failing_report.pdf',
                'content': _('Download Failing Report'),
            },
            {
                'url': url +  '/absences_by_day.pdf',
                'content': _('Download Absences By Day Report'),
            },
         ]
        return results


class SectionReportsView(BaseView):

    def title(self):
        return _('Section Reports')

    def links(self):
        url = absoluteURL(self.context, self.request)
        results = [
            {
                'url': url +  '/section_absences.pdf',
                'content': _('Download Section Absences Report'),
            },
         ]
        return results

