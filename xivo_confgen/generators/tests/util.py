# -*- coding: utf-8 -*-

# Copyright (C) 2011-2014 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import re


class InvalidAstConfigException(Exception):
    pass


_SECTION_REGEX = re.compile(u'^\[([-\w]+)\]$')
_OPTION_REGEX = re.compile(u'^[-\w]+ =>? .*$')


def parse_ast_config(fobj):
    ast_config = {}
    cur_section = None
    for raw_line in fobj:
        line = raw_line.rstrip()
        if not line or line.startswith(u';'):
            continue

        m = _OPTION_REGEX.match(line)
        if m:
            if cur_section is None:
                raise InvalidAstConfigException('option %r not defined in a section' % line)
            cur_section.append(line)
        else:
            m = _SECTION_REGEX.match(line)
            if m:
                name, = m.groups()
                if name in ast_config:
                    raise InvalidAstConfigException('redefinition of section %r' % name)
                cur_section = ast_config.setdefault(name, [])
            else:
                raise InvalidAstConfigException('invalid line %r' % line)
    return ast_config


def build_expected(output):
    return '\n'.join(line.lstrip() for line in output.split('\n'))