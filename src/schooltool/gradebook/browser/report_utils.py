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
Utilities used in report views.
"""
import cgi
import re


def _unescape_FCKEditor_HTML(text):
    text = text.replace(u'&amp;', u'&')
    text = text.replace(u'&lt;', u'<')
    text = text.replace(u'&gt;', u'>')
    text = text.replace(u'&quot;', u'"')
    text = text.replace(u'&#39;', u"'")
    text = text.replace(u'&rsquo;', u"'")
    text = text.replace(u'&nbsp;', u' ')
    return text


escaped_reportlab_tags_re = re.compile(
    r'&lt;(/?((strong)|(b)|(em)|(i)))&gt;')

html_p_tag_re = re.compile(r'</?p[^>]*>')
html_br_tag_re = re.compile(r'</?br[^>]*>')


def buildHTMLParagraphs(snippet):
    """Build a list of paragraphs from an HTML snippet."""
    if not snippet:
        return []
    paragraphs = []
    tokens = []
    for token in html_p_tag_re.split(snippet):
        if not token or token.isspace():
            continue
        tokens.extend(html_br_tag_re.split(token))
    for token in tokens:
        if not token or token.isspace():
            continue
        # Reportlab is very sensitive to unknown tags and escaped symbols.
        # In case of invalid HTML, ensure correct escaping.
        fixed_escaping = cgi.escape(_unescape_FCKEditor_HTML(unicode(token)))
        # Unescape some of the tags which are also valid in Reportlab
        valid_text = escaped_reportlab_tags_re.sub(u'<\g<1>>', fixed_escaping)
        paragraphs.append(valid_text)
    return paragraphs

