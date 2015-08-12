'''
Dec base::

    Copyright (C) 2011 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe
     * Ashley Felton

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

def remove_(attrs=list()):
    cleanattrs = list()
    for attr in attrs:
        if attr[0] != "_":
            cleanattrs.append(attr)
    return cleanattrs

def defaults(exclude=list(), includeauth=True):
    import sys
    frame = sys._getframe(1)
    global_scope = frame.f_globals
    import settings
    attrs = list()
    attrs = set(remove_(dir(settings))) - set(exclude)
    for attr in attrs:
        global_scope[attr] = settings.__getattribute__(attr)
    if includeauth:
        import authentication
        attrs = set(remove_(dir(authentication))) - set(exclude)
        for attr in attrs:
            global_scope[attr] = authentication.__getattribute__(attr)

