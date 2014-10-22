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
from StringIO import StringIO

from xivo import OrderedConf, xivo_helpers
from xivo_dao import asterisk_conf_dao


DEFAULT_EXTENFEATURES = {
    'paging': 'GoSub(paging,s,1(${EXTEN:3}))',
    'autoprov': 'GoSub(autoprov,s,1())',
    'incallfilter': 'GoSub(incallfilter,s,1())',
    'phoneprogfunckey': 'GoSub(phoneprogfunckey,s,1(${EXTEN:0:4},${EXTEN:4}))',
    'phonestatus': 'GoSub(phonestatus,s,1())',
    'pickup': 'Pickup(${EXTEN:2}%${CONTEXT}@PICKUPMARK)',
    'recsnd': 'GoSub(recsnd,s,1(wav))',
    'vmboxmsgslt': 'GoSub(vmboxmsg,s,1(${EXTEN:3}))',
    'vmboxpurgeslt': 'GoSub(vmboxpurge,s,1(${EXTEN:3}))',
    'vmboxslt': 'GoSub(vmbox,s,1(${EXTEN:3}))',
    'vmusermsg': 'GoSub(vmusermsg,s,1())',
    'vmuserpurge': 'GoSub(vmuserpurge,s,1())',
    'vmuserpurgeslt': 'GoSub(vmuserpurge,s,1(${EXTEN:3}))',
    'vmuserslt': 'GoSub(vmuser,s,1(${EXTEN:3}))',
    'agentstaticlogin': 'GoSub(agentstaticlogin,s,1(${EXTEN:3}))',
    'agentstaticlogoff': 'GoSub(agentstaticlogoff,s,1(${EXTEN:3}))',
    'agentstaticlogtoggle': 'GoSub(agentstaticlogtoggle,s,1(${EXTEN:3}))',
    'bsfilter': 'GoSub(bsfilter,s,1(${EXTEN:3}))',
    'cctoggle': 'GoSub(cctoggle,s,1())',
    'callgroup': 'GoSub(group,s,1(${EXTEN:4}) )',
    'calllistening': 'GoSub(calllistening,s,1())',
    'callmeetme': 'GoSub(meetme,s,1(${EXTEN:4}))',
    'callqueue': 'GoSub(queue,s,1(${EXTEN:4}))',
    'callrecord': 'GoSub(callrecord,s,1() )',
    'calluser': 'GoSub(user,s,1(${EXTEN:4}))',
    'directoryaccess': 'Directory(${CONTEXT})',
    'enablednd': 'GoSub(enablednd,s,1())',
    'enablevm': 'GoSub(enablevm,s,1())',
    'enablevmslt': 'GoSub(enablevm,s,1(${EXTEN:3}))',
    'fwdundoall': 'GoSub(fwdundoall,s,1())',
    'fwdbusy': 'GoSub(feature_forward,s,1(busy,${EXTEN:3}))',
    'fwdrna': 'GoSub(feature_forward,s,1(rna,${EXTEN:3}))',
    'fwdunc': 'GoSub(feature_forward,s,1(unc,${EXTEN:3}))',
}


class ExtensionsConf(object):

    def __init__(self, contextsconf, hint_generator):
        self.contextsconf = contextsconf
        self.hint_generator = hint_generator

    def generate(self, output):
        options = output

        if self.contextsconf is not None:
            # load context templates
            conf = OrderedConf.OrderedRawConf(filename=self.contextsconf)
            if conf.has_conflicting_section_names():
                raise ValueError("%s has conflicting section names" % self.contextsconf)
            if not conf.has_section('template'):
                raise ValueError("Template section doesn't exist in %s" % self.contextsconf)

        # hints & features (init)
        xfeatures = {
            'bsfilter': {},
            'callmeetme': {},
            'calluser': {},
            'fwdbusy': {},
            'fwdrna': {},
            'fwdunc': {},
            'phoneprogfunckey': {},
            'vmusermsg': {}
        }

        extensions = asterisk_conf_dao.find_extenfeatures_settings(features=xfeatures.keys())
        xfeatures.update(dict([x['typeval'], {'exten': x['exten'], 'commented': x['commented']}] for x in extensions))

        # foreach active context
        for ctx in asterisk_conf_dao.find_context_settings():
            # context name preceded with '!' is ignored
            if conf and conf.has_section('!%s' % ctx['name']):
                continue

            print >> options, "\n[%s]" % ctx['name']

            if conf.has_section(ctx['name']):
                section = ctx['name']
            elif conf.has_section('type:%s' % ctx['contexttype']):
                section = 'type:%s' % ctx['contexttype']
            else:
                section = 'template'

            tmpl = []
            for option in conf.iter_options(section):
                if option.get_name() == 'objtpl':
                    tmpl.append(option.get_value())
                    continue

                print >> options, "%s = %s" % (option.get_name(), option.get_value().replace('%%CONTEXT%%', ctx['name']))

            # context includes
            for row in asterisk_conf_dao.find_contextincludes_settings(ctx['name']):
                print >> options, "include = %s" % row['include']
            print >> options

            # objects extensions (user, group, ...)
            for exten in asterisk_conf_dao.find_exten_settings(ctx['name']):
                exten_type = exten['type']
                exten_typeval = exten['typeval']
                if exten_type == 'incall':
                    exten_type = 'did'

                exten['action'] = 'GoSub(%s,s,1(%s,))' % (exten_type, exten_typeval)

                self.gen_dialplan_from_template(tmpl, exten, options)

            # conference supervision
            conferences = asterisk_conf_dao.find_exten_conferences_settings(context_name=ctx['name'])
            if len(conferences) > 0:
                print >> options, "\n; conferences supervision"

            for conference in conferences:
                if conference['exten'] is not None:
                    exten = xivo_helpers.clean_extension(conference['exten'])
                else:
                    continue

            self._generate_hints(ctx['name'], options)

        print >> options, self._extensions_features(conf, xfeatures)
        return options.getvalue()

    def _extensions_features(self, conf, xfeatures):
        options = StringIO()
        # XiVO features
        context = 'xivo-features'
        cfeatures = []
        tmpl = []

        print >> options, "\n[%s]" % context
        for option in conf.iter_options(context):
            if option.get_name() == 'objtpl':
                tmpl.append(option.get_value())
                continue

            print >> options, "%s = %s" % (option.get_name(), option.get_value().replace('%%CONTEXT%%', context))
            print >> options

        for exten in asterisk_conf_dao.find_exten_xivofeatures_setting():
            name = exten['typeval']
            if name in DEFAULT_EXTENFEATURES:
                exten['action'] = DEFAULT_EXTENFEATURES[name]
                self.gen_dialplan_from_template(tmpl, exten, options)

        for x in ('busy', 'rna', 'unc'):
            fwdtype = "fwd%s" % x
            if not xfeatures[fwdtype].get('commented', 1):
                exten = xivo_helpers.clean_extension(xfeatures[fwdtype]['exten'])
                cfeatures.extend([
                    "%s,1,Set(XIVO_BASE_CONTEXT=${CONTEXT})" % exten,
                    "%s,n,Set(XIVO_BASE_EXTEN=${EXTEN})" % exten,
                    "%s,n,Gosub(feature_forward,s,1(%s))\n" % (exten, x),
                ])

        if cfeatures:
            print >> options, "exten = " + "\nexten = ".join(cfeatures)

        return options.getvalue()

    def gen_dialplan_from_template(self, template, exten, output):
        if 'priority' not in exten:
            exten['priority'] = 1

        for line in template:
            prefix = 'exten =' if line.startswith('%%EXTEN%%') else 'same  =    '

            def varset(matchObject):
                return str(exten.get(matchObject.group(1).lower(), ''))
            line = re.sub('%%([^%]+)%%', varset, line)
            print >> output, prefix, line
        print >> output

    @staticmethod
    def _build_sorted_bsfilter(query_result):
        numbers = []
        for bsfilter in query_result:
            if bsfilter['bsfilter'] == 'secretary':
                boss, secretary = bsfilter['exten'], bsfilter['number']
            elif bsfilter['bsfilter'] == 'boss':
                boss, secretary = bsfilter['number'], bsfilter['exten']
            else:
                pass
            numbers.append((boss, secretary))
        return set(numbers)

    def _generate_hints(self, context, output):
        for line in self.hint_generator.generate(context):
            print >> output, line