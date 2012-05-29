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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Selenium functional tests setup for schooltool.gradebook
"""

from schooltool.app.testing import format_table


css_to_code = {
    'valid': 'v',
    'error': 'i',
    'extracredit': 'e',
    }


def tertiary_navigation(browser):
    result = []
    sel = 'ul.third-nav li'
    for tab in browser.query_all.css(sel):
        text = tab.text.strip()
        css_class = tab.get_attribute('class')
        if css_class is not None and 'active' in css_class:
            text = '*%s*' % text
        result.append(text)
    return result


def table_header(browser):
    result = []
    row1 = []
    sel = '.students thead a.popup_link'
    for header in browser.query_all.css(sel):
        row1.append(header.text.strip())
    sel = '.grades thead a.popup_link'
    for header in browser.query_all.css(sel):
        row1.append(header.text.strip())
    sel = '.totals thead a.popup_link'
    for header in browser.query_all.css(sel):
        row1.append(header.text.strip())
    result.append(row1)
    row2 = ['']
    sel = 'id("grades-part")//thead/tr[2]/th'
    for header in browser.query_all.xpath(sel):
        row2.append(header.text.strip())
    sel = 'id("totals-part")//thead//th'
    for header in browser.query_all.xpath(sel):
        row2.append('')
    result.append(row2)
    return result


def table_rows(browser, show_validation):
    rows = []
    sel = '.students tbody a.popup_link'
    for student in browser.query_all.css(sel):
        rows.append([student.text.strip()])
    sel = '.grades tbody tr'
    for index, row in enumerate(browser.query_all.css(sel)):
        student = rows[index]
        sel = 'td[not(contains(@class, "placeholder"))]'
        for td in row.query_all.xpath(sel):
            fields = td.query_all.tag('input')
            if fields:
                field = fields[0]
                value = browser.driver.execute_script(
                    'return arguments[0].value', field)
                value = '[%s]' % value.ljust(5, '_')
                if show_validation:
                    css_class = field.get_attribute('class')
                    value += css_to_code.get(css_class, '')
            else:
                value = td.text.strip()
            student.append(value)
    sel = '.totals tbody tr'
    for index, row in enumerate(browser.query_all.css(sel)):
        student = rows[index]
        for td in row.query_all.tag('td'):
            student.append(td.text.strip())
    return rows


def print_gradebook(browser, show_validation):
    print format_table([tertiary_navigation(browser)])
    rows = []
    rows.extend(table_header(browser))
    for row in table_rows(browser, show_validation):
        rows.append(row)
    print format_table(rows, header_rows=2)


def registerSeleniumSetup():
    try:
        import selenium
    except ImportError:
        return
    from schooltool.testing import registry
    import schooltool.testing.selenium

    def printGradebook(browser, show_validation=False):
        print_gradebook(browser, show_validation)

    registry.register('SeleniumHelpers',
        lambda: schooltool.testing.selenium.registerBrowserUI(
            'gradebook.worksheet.pprint', printGradebook))

    def score(browser, student, activity, grade):
        row_index = None
        column_index = None
        sel = '.students tbody a.popup_link'
        for index, link in enumerate(browser.query_all.css(sel)):
            if student == link.text:
                row_index = index
                break
        sel = '.grades thead a.popup_link'
        for index, link in enumerate(browser.query_all.css(sel)):
            if activity == link.text:
                column_index = index
                break
        sel = ('//div[contains(@class, "grades")]'
               '//tbody/tr[%s]/td[%s]' % (row_index+1, column_index+1))
        cell = browser.query.xpath(sel)
        cell.click()
        cell.query.tag('input').type(browser.keys.DELETE, grade)

    registry.register('SeleniumHelpers',
        lambda: schooltool.testing.selenium.registerBrowserUI(
            'gradebook.worksheet.score', score))

registerSeleniumSetup()
del registerSeleniumSetup
