# -*- coding: UTF-8 -*-

__license__ = """
    Copyright (C) 2011  Avencall

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA..
"""

from xivo_confgen.generators.util import format_ast_section, \
    format_ast_option


class SccpConf(object):
    def __init__(self, sccpgeneralsettings, sccpline, sccpdevice, sccpspeeddial):
        self._sccpgeneralsettings = sccpgeneralsettings
        self._sccpline = sccpline
        self._sccpdevice = sccpdevice
        self._sccpspeeddial = sccpspeeddial

    def generate(self, output):
        sccp_general_conf = _SccpGeneralSettingsConf()
        sccp_general_conf.generate(self._sccpgeneralsettings, output)

        sccp_line_conf = _SccpLineConf()
        sccp_line_conf.generate(self._sccpline, output)

        sccp_device_conf = _SccpDeviceConf()
        sccp_device_conf.generate(self._sccpdevice, output)

        sccp_speeddial_conf = _SccpSpeedDialConf()
        sccp_speeddial_conf.generate(self._sccpspeeddial, output)

    @classmethod
    def new_from_backend(cls, backend):
        sccpgeneralsettings = backend.sccpgeneralsettings.all()
        sccpline = backend.sccpline.all()
        sccpdevice = backend.sccpdevice.all()
        sccpspeeddial = backend.sccpspeeddial.all()
        return cls(sccpgeneralsettings,
                   sccpline,
                   sccpdevice,
                   sccpspeeddial)


class _SccpGeneralSettingsConf(object):
    def generate(self, sccpgeneralsettings, output):
        print >> output, u'[general]'
        for item in sccpgeneralsettings:
            option_value = item['option_value']
            if item['option_name'] == 'directmedia':
                option_value = '0' if item['option_value'] == 'no' else '1'
            print >> output, format_ast_option(item['option_name'], option_value)
        print >> output


class _SccpLineConf(object):
    def generate(self, sccpline, output):
        print >> output, u'[lines]'
        for item in sccpline:
            print >> output, format_ast_section(item['name'])
            print >> output, format_ast_option('cid_name', item['cid_name'])
            print >> output, format_ast_option('cid_num', item['cid_num'])
            print >> output, format_ast_option('setvar', 'XIVO_USERID=%s' % item['user_id'])
            print >> output, format_ast_option('setvar', 'PICKUPMARK=%s%%%s' % (item['number'], item['context']))
            print >> output, format_ast_option('language', self._format_language(item['language']))
            print >> output, format_ast_option('context', item['context'])
            print >> output

    def _format_language(self, language):
        if not language:
            return u'en_US'
        else:
            return language


class _SccpDeviceConf(object):
    def generate(self, sccpdevice, output):
        print >> output, u'[devices]'
        for item in sccpdevice:
            print >> output, format_ast_section(item['name'])
            print >> output, format_ast_option('device', item['device'])
            print >> output, format_ast_option('line', item['line'])
            print >> output, format_ast_option('voicemail', item['voicemail'])
            print >> output


class _SccpSpeedDialConf(object):
    def generate(self, sccpspeeddial, output):
        print >> output, u'[speeddials]'
        for item in sccpspeeddial:
            print >> output, format_ast_section('%d-%d' % (item['iduserfeatures'], item['fknum']))
            print >> output, format_ast_option('extension', item['exten'])
            print >> output, format_ast_option('label', item['label'])
            print >> output, format_ast_option('blf', item['supervision'])
            print >> output
