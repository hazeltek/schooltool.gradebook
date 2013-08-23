#
# SchoolTool - common information systems platform for school administration
# Copyright (c) 2011 Shuttleworth Foundation
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
Helper function for tests.
"""

from schooltool.app.testing import format_table
from schooltool.testing.analyze import queryHTML


def worksheet_tabs(contents):
    result = []
    cells =  [cell.strip()
              for cell in queryHTML('//table[@class="schooltool_gradebook"][1]/tr[1]/td',
                                    contents)]
    for cell in cells:
        row = []
        row.extend(['*%s*' % text.strip() for text in queryHTML('//td/span/text()', cell) if text.strip()])
        row.extend(['%s' % text.strip() for text in queryHTML('//td/a/text()', cell) if text.strip()])
        result.extend(row)
    return result


def gradebook_header(contents):
    result = []
    for div in [cell.strip() for cell in queryHTML('//th/div[1]', contents) if cell.strip()]:
        links = [cell.strip() for cell in queryHTML('//a/text()', div) if cell.strip()]
        if links:
            # <th><div><a>...</a></div></th>
            result.extend(links)
        else:
            spans = [cell.strip() for cell in queryHTML('//span/text()', div) if cell.strip()]
            if spans:
                # <th><div><span>...</span></div></th> (e.g. linked column activities)
                result.extend(spans)
            else:
                labels = [cell.strip() for cell in queryHTML('//div/text()', div) if cell.strip()]
                if labels:
                    # <th><div>...</div></th> (e.g. Name, Total, Ave.)
                    result.extend(labels)
    return result


def printGradebook(contents):
    contents = contents.replace('<br />', ' ')

    tabs_table_rows = []
    tabs_table_rows.append(worksheet_tabs(contents))

    grades_table_rows = []
    gradebook_rows = queryHTML('//table[@class="schooltool_gradebook"][2]//tr', contents)
    for row_number, row in enumerate(gradebook_rows):
        # we don't care about these rows
        # first (0): activity description
        # third (2): 'Apply a grade for all students'
        if row_number == 1:
            grades_table_rows.append(gradebook_header(row))
        if row_number > 2:
            columns = []
            cells = [cell for cell in queryHTML('//tr/td', row)]
            for cell in cells:
                # Student's name
                text = queryHTML('//td/a[1]/text()', cell)
                if not text:
                    # Activity inputs
                    text_input_value = queryHTML('//td//input[@type="text"]/@value', cell)
                    if text_input_value:
                        text = ["[%s]" % str(text_input_value[0]).ljust(5, '_')]
                if not text:
                    # Total and Ave.
                    text = queryHTML('//td/b/text()', cell)
                    if text:
                        text = [text[0].strip()]
                if not text:
                    # Linked column activities
                    text = queryHTML('//td/span/text()', cell)
                    if text:
                        text = [text[0].strip()]
                if not text:
                    text = ['']
                columns.append(text[0].strip().encode('utf-8'))
            grades_table_rows.append(columns)

    print format_table(tabs_table_rows)
    print format_table(grades_table_rows, header_rows=1)
