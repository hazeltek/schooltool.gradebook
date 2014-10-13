#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2012 Shuttleworth Foundation
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
Functional selenium tests for schooltool.gradebook
"""

import unittest
import os

from schooltool.testing.analyze import etree, to_string
from schooltool.testing.selenium import SeleniumLayer
from schooltool.testing.selenium import collect_ftests
from schooltool.testing.util import format_table


def queryXML(xpath, response):
    doc = etree.XML(response)
    return [to_string(node).strip() for node in doc.xpath(xpath)]


def print_rml_table(browser):
    story = browser.query.tag('story').getHTML()
    table = []
    for row in queryXML('//blocktable/tr', story):
        cells = queryXML('//td/text()', row)
        table.append(cells)
    print format_table(table, header_rows=1)


dir = os.path.abspath(os.path.dirname(__file__))
filename = os.path.join(dir, '../stesting.zcml')
journal_filename = os.path.join(dir, '../stesting_journal.zcml')

need_journal = (
    'itworks_journal.txt',
    'absences_by_day_report.txt',
    )

testdir = os.path.dirname(__file__)
ftests = [fn for fn in os.listdir(testdir)
          if (fn.endswith('.txt') and
              not fn.startswith('.') and
              not fn in need_journal)]

gradebook_selenium_layer = SeleniumLayer(filename,
                                         __name__,
                                         'gradebook_selenium_layer')

journal_selenium_layer = SeleniumLayer(journal_filename,
                                       __name__,
                                       'journal_functional_layer')

def test_suite():
    return unittest.TestSuite([
        collect_ftests(layer=gradebook_selenium_layer, filenames=ftests),
        collect_ftests(layer=journal_selenium_layer, filenames=need_journal,
                       extra_globs={'print_rml_table': print_rml_table})
        ])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
