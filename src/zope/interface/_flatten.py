##############################################################################
#
# Copyright (c) 2002 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Adapter-style interface registry

See Adapter class.

$Id: _flatten.py,v 1.7 2003/11/21 17:11:43 jim Exp $
"""
__metaclass__ = type # All classes are new style when run with Python 2.2+

from zope.interface import Declaration

def _flatten(implements, include_None=0):

    try:
        r = implements.flattened()
    except AttributeError:
        if implements is None:
            r=()
        else:
            r = Declaration(implements).flattened()

    if not include_None:
        return r

    r = list(r)
    r.append(None)
    return r
