# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import unicode_literals

import yaml

from xivo_dao import init_db_from_config
from xivo_dao.helpers.db_utils import session_scope
from xivo_dao.alchemy.provisioning import Provisioning
from xivo_dao.alchemy.netiface import Netiface


class ProvdNetworkConfGenerator(object):

    def __init__(self, dependencies):
        init_db_from_config(dependencies['config'])

    def get_provd_net4_ip(self, session):
        result = session.query(Provisioning.net4_ip).first()
        if not result:
            return
        return result.net4_ip

    def get_netiface_net4_ip(self, session):
        result = session.query(Netiface.address).filter(Netiface.networktype == 'voip').first()
        if not result:
            return
        return result.address

    def get_provd_net4_ip_rest(self, session):
        result = session.query(Provisioning.net4_ip_rest).first()
        if not result:
            return
        return result.net4_ip_rest

    def get_provd_rest_port(self, session):
        result = session.query(Provisioning.rest_port).first()
        if not result:
            return
        return result.rest_port

    def get_provd_http_port(self, session):
        result = session.query(Provisioning.http_port).first()
        if not result:
            return
        return result.http_port

    def generate(self):
        config = {}
        with session_scope() as session:
            external_ip = self.get_provd_net4_ip(session) or self.get_netiface_net4_ip(session)
            external_port = self.get_provd_http_port(session)
            rest_ip = self.get_provd_net4_ip_rest(session)
            rest_port = self.get_provd_rest_port(session)

            sections = {
                'general': {
                    'external_ip': external_ip,
                    'http_port': external_port,
                },
                'rest_api': {
                    'ip': rest_ip,
                    'port': rest_port,
                }
            }

            for section_name, section_value in sections.iteritems():
                for option, value in section_value.iteritems():
                    if value:
                        if section_name not in config:
                            config.update({section_name: {}})
                        config[section_name][option] = value

        return yaml.safe_dump(config, default_flow_style=False)
