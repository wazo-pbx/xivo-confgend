# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import unicode_literals

from StringIO import StringIO

from xivo_dao.resources.asterisk_file import dao as asterisk_file_dao

from ..helpers.asterisk import AsteriskFileGenerator


class HEPConfGenerator(object):

    def __init__(self, dependencies):
        self.dependencies = dependencies

    def generate(self):
        asterisk_file_generator = AsteriskFileGenerator(asterisk_file_dao)
        output = StringIO()
        asterisk_file_generator.generate('hep.conf', output)
        return output.getvalue()
