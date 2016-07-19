# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
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

import xivo_dao

from twisted.internet import reactor
from twisted.application import service, internet

from xivo_confgen.confgen import ConfgendFactory
from xivo_confgen.config import load as load_config


def main():
    config = load_config()
    xivo_dao.init_db(config['db_uri'])
    f = ConfgendFactory(config['cache'], config)

    reactor.listenTCP(config['listen_port'], f, interface=config['listen_address'])
    reactor.run()


def twisted_application():
    config = load_config()
    xivo_dao.init_db(config['db_uri'])
    f = ConfgendFactory(config['cache'], config)

    application = service.Application('confgend')
    service.IProcess(application).processName = "confgend"

    svc = internet.TCPServer(config['listen_port'], f, interface=config['listen_address'])
    svc.setServiceParent(application)

    return application
