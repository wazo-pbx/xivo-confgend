# -*- coding: utf-8 -*-

# Copyright (C) 2015 Avencall
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

import yaml

from xivo_dao import cti_context_dao
from xivo_dao import cti_displays_dao
from xivo_dao import cti_main_dao
from xivo_dao import cti_reverse_dao
from xivo_dao import directory_dao


class _AssociationGenerator(object):

    def generate(self):
        raw = cti_displays_dao.get_profile_configuration()
        return {profile: config['display']
                for profile, config in raw.iteritems()}


class _PhoneAssociationGenerator(object):

    _DEFAULT_PHONE_DISPLAY = 'default'

    def generate(self):
        profiles = cti_context_dao.get_context_names()
        return {profile: self._DEFAULT_PHONE_DISPLAY for profile in profiles}


class _DisplayGenerator(object):

    _fields = ['title', 'type', 'default', 'field']

    def generate(self):
        raw = cti_displays_dao.get_config()
        return {name: self._format_columns(column)
                for name, column in raw.iteritems()}

    def _format_columns(self, column_configs):
        keys = sorted(column_configs.iterkeys())
        return [self._format_line(column_configs[key]) for key in keys]

    def _format_line(self, line_config):
        default_index = self._fields.index('default')
        line_config[default_index] = line_config[default_index] or None
        return dict(zip(self._fields, line_config))


class _LookupServiceGenerator(object):

    _default_sources = ['personal']
    _default_timeout = 2.9

    def __init__(self, profile_configuration):
        self._profile_config = profile_configuration

    def generate(self):
        return {profile: {'sources': conf['sources'] + self._default_sources,
                          'timeout': self._default_timeout}
                for profile, conf in self._profile_config.iteritems()}


class _SourceGenerator(object):

    confd_api_version = '1.1'
    confd_default_timeout = 4
    phonebook_default_timeout = 4
    supported_types = ['csv', 'csv_ws', 'ldap', 'phonebook', 'xivo']

    def __init__(self, raw_sources):
        self._raw_sources = raw_sources

    def generate(self):
        return dict(self._format_source(source)
                    for source in self._raw_sources
                    if source['type'] in self.supported_types)

    def _format_source(self, source):
        name = source['name']
        type_ = source['type']
        config = {'type': type_,
                  'name': name,
                  'searched_columns': source['searched_columns'],
                  'first_matched_columns': source['first_matched_columns'],
                  'format_columns': source['format_columns']}

        if type_ == 'xivo':
            config.update(self._format_xivo_source(source))
        elif type_ == 'phonebook':
            config.update(self._format_phonebook_source(source))
        elif type_ == 'csv':
            config.update(self._format_csv_source(source))
        elif type_ == 'csv_ws':
            config.update(self._format_csv_ws_source(source))
        elif type_ == 'ldap':
            config.update(self._format_ldap_source(source))

        return name, config

    def _format_csv_source(self, source):
        _, _, filename = source['uri'].partition('file://')
        return {'file': filename,
                'separator': source['delimiter']}

    def _format_csv_ws_source(self, source):
        return {'delimiter': source['delimiter'],
                'lookup_url': source['uri']}

    def _format_ldap_source(self, source):
        return {
            'ldap_uri': source['ldap_uri'],
            'ldap_username': source['ldap_username'],
            'ldap_password': source['ldap_password'],
            'ldap_base_dn': source['ldap_base_dn'],
            'ldap_custom_filter': source['ldap_custom_filter'],
        }

    def _format_phonebook_source(self, source):
        return {'phonebook_url': source['uri'],
                'phonebook_timeout': 4}

    def _format_xivo_source(self, source):
        return {'unique_column': 'id',
                'confd_config': self._format_confd_config(source)}

    def _format_confd_config(self, source):
        scheme, _, end = source['uri'].partition('://')
        host, _, port = end.partition(':')
        verify_certificate = self._format_confd_verify_certificate(source)

        config = {
            'https': scheme == 'https',
            'host': host,
            'timeout': self.confd_default_timeout,
            'version': self.confd_api_version,
            'verify_certificate': verify_certificate
        }
        if port:
            config['port'] = int(port)
        if source['xivo_username'] and source['xivo_password']:
            config['username'] = source['xivo_username']
            config['password'] = source['xivo_password']

        return config

    def _format_confd_verify_certificate(self, source):
        if source['xivo_verify_certificate']:
            if source['xivo_custom_ca_path']:
                return source['xivo_custom_ca_path']
            else:
                return True
        else:
            return False


class _FavoritesServiceGenerator(_LookupServiceGenerator):
    pass


class _ReverseServiceGenerator(object):

    _default_sources = ['personal']
    _default_profile = 'default'
    _default_timeout = 1

    def __init__(self, reverse_configuration):
        self._reverse_config = reverse_configuration

    def generate(self):
        return {self._default_profile: {'sources': self._reverse_config + self._default_sources,
                                        'timeout': self._default_timeout}}


class DirdFrontend(object):

    def __init__(self):
        self._no_context_separation_backend = _NoContextSeparationDirdFrontend()
        self._context_separated_backend = _ContextSeparatedDirdFrontend()

    def __getattr__(self, name):
        if bool(cti_main_dao.get_config()['main']['context_separation']):
            selected_implementation = self._context_separated_backend
        else:
            selected_implementation = self._no_context_separation_backend

        return getattr(selected_implementation, name)


class _BaseDirdFrontend(object):

    def services_yml(self):
        profile_config = cti_displays_dao.get_profile_configuration()
        lookups = _LookupServiceGenerator(profile_config).generate()
        favorites = _FavoritesServiceGenerator(profile_config).generate()

        reverse_config = cti_reverse_dao.get_config()
        reverses = _ReverseServiceGenerator(reverse_config).generate()

        return yaml.safe_dump({'services': {'lookup': lookups,
                                            'favorites': favorites,
                                            'reverse': reverses}})

    def sources_yml(self):
        raw_sources = directory_dao.get_all_sources()
        sources = _SourceGenerator(raw_sources).generate()
        return yaml.safe_dump({'sources': sources})

    def views_yml(self):
        displays = _DisplayGenerator().generate()
        associations = _AssociationGenerator().generate()
        phone_associations = _PhoneAssociationGenerator().generate()

        views_section = {'views': {'displays': displays,
                                   'profile_to_display': associations,
                                   'profile_to_display_phone': phone_associations}}

        return yaml.safe_dump(views_section)


class _ContextSeparatedDirdFrontend(_BaseDirdFrontend):

    pass


class _NoContextSeparationDirdFrontend(_BaseDirdFrontend):

    pass
