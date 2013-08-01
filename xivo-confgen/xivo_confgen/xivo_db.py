# -*- coding: utf-8 -*-

# Copyright (C) 2010-2013 Avencall
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

from sqlalchemy import exc
from sqlalchemy.ext.sqlsoup import SqlSoup
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, cast, literal, desc
from sqlalchemy.types import VARCHAR
import inspect
import warnings
warnings.simplefilter('ignore')


def mapped_set(self, key, value):
    self.__dict__[key] = value


def mapped_iterkeys(self):
    keys = sorted(filter(lambda x: x[0] != '_', self.__dict__))

    for k in keys:
        yield k

    return


def mapped_iteritems(self):
    keys = sorted(filter(lambda x: x[0] != '_', self.__dict__))

    for k in keys:
        yield (k, self.__dict__[k])

    return


def iterable(mode):
    def _iterable(f):
        def single_wrapper(*args, **kwargs):
            try:
                ret = f(*args, **kwargs)
            except exc.OperationalError:
                # reconnect & retry
                args[0].db.flush()
                ret = f(*args, **kwargs)

            if ret is not None:
                ret.__class__.__getitem__ = lambda self, key: self.__dict__[key]
                ret.__class__.iteritems = mapped_iteritems

            return ret

        def list_wrapper(*args, **kwargs):
            try:
                ret = f(*args, **kwargs)
            except exc.OperationalError:
                # reconnect & retry
                args[0].db.flush()
                ret = f(*args, **kwargs)

            if isinstance(ret, list) and len(ret) > 0:
                ret[0].__class__.__getitem__ = lambda self, key: self.__dict__[key]
                ret[0].__class__.__setitem__ = mapped_set
                ret[0].__class__.__contains__ = lambda self, key: self.__dict__.__contains__(key)
                ret[0].__class__.iteritems = mapped_iteritems
                ret[0].__class__.iterkeys = mapped_iterkeys
                ret[0].__class__.get = lambda self, key, dft: self.__dict__[key] if key in self.__dict__ else dft

            return ret

        def join_wrapper(*args, **kwargs):
            ret = f(*args, **kwargs)
            if isinstance(ret, list) and len(ret) > 0:
                def find(d, k):
                    # print d.keys, k, k in d, unicode(k) in d
                    return None
                ret[0].__class__.__getitem__ = lambda self, key: find(self.__dict__, key)

            return ret

        return locals()[mode + '_wrapper']
    return _iterable


class SpecializedHandler(object):
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def execute(self, q):
        try:
            ret = self.db.engine.connect().execute(q)
        except exc.OperationalError:
            # reconnect & retry
            self.db.flush()
            ret = self.db.engine.connect().execute(q)

        return ret


class AgentQueueskillsHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        (_a, _f, _s) = [getattr(self.db, options)._table for options in ('agentqueueskill', 'agentfeatures', 'queueskill')]
        q = select(
            [_f.c.id, _s.c.name, _a.c.weight],
            and_(_a.c.agentid == _f.c.id, _a.c.skillid == _s.c.id)
        )
        q = q.order_by(_f.c.id)

        return self.execute(q).fetchall()


class SccpGeneralSettingsHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        extensions = self.db.extensions._table
        sccpgeneralsettings = self.db.sccpgeneralsettings._table

        query1 = select(
            [literal('vmexten').label('option_name'), extensions.c.exten.label('option_value')],
            and_(extensions.c.type == 'extenfeatures',
                 extensions.c.typeval == 'vmusermsg')
        )

        query2 = select(
            [sccpgeneralsettings.c.option_name, sccpgeneralsettings.c.option_value])

        return self.execute(query1.union(query2)).fetchall()


class SccpLineHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        sccpline = self.db.sccpline._table
        linefeatures = self.db.linefeatures._table
        userfeatures = self.db.userfeatures._table
        user_line = self.db.user_line._table

        query = select(
            [sccpline.c.name,
             sccpline.c.cid_name,
             sccpline.c.cid_num,
             userfeatures.c.language,
             user_line.c.user_id,
             linefeatures.c.context,
             linefeatures.c.number],
            and_(user_line.c.user_id == userfeatures.c.id,
                 user_line.c.line_id == linefeatures.c.id,
                 user_line.c.main_user == True,
                 user_line.c.main_line == True,
                 linefeatures.c.protocol == 'sccp',
                 linefeatures.c.protocolid == sccpline.c.id)
        )

        return self.execute(query).fetchall()


class SccpSpeedDialHandler(SpecializedHandler):
    def all(self):
        sccpdevice = self.db.sccpdevice._table
        linefeatures = self.db.linefeatures._table
        phonefunckey = self.db.phonefunckey._table
        user_line = self.db.user_line._table

        query = select(
            [phonefunckey.c.exten,
             phonefunckey.c.fknum,
             phonefunckey.c.label,
             phonefunckey.c.supervision,
             user_line.c.user_id,
             sccpdevice.c.device],
            and_(user_line.c.user_id == phonefunckey.c.iduserfeatures,
                 user_line.c.line_id == linefeatures.c.id,
                 user_line.c.main_user == True,
                 linefeatures.c.protocol == 'sccp',
                 linefeatures.c.number == sccpdevice.c.line)
        )

        return self.execute(query).fetchall()


class HintsHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        # get users with hint
        userfeatures = self.db.userfeatures._table
        linefeatures = self.db.linefeatures._table
        voicemail = self.db.voicemail._table
        user_line = self.db.user_line._table

        conds = [
             user_line.c.user_id == userfeatures.c.id,
             user_line.c.line_id == linefeatures.c.id,
             user_line.c.main_user == True,
             user_line.c.main_line == True,
             userfeatures.c.enablehint == 1
        ]
        if 'context' in kwargs:
            conds.append(linefeatures.c.context == kwargs['context'])

        q = select([
            userfeatures.c.id,
            userfeatures.c.enablevoicemail,
            linefeatures.c.number,
            linefeatures.c.name,
            linefeatures.c.protocol,
            voicemail.c.uniqueid
            ],
            and_(*conds),
            from_obj=[
                userfeatures.outerjoin(voicemail, userfeatures.c.voicemailid == voicemail.c.uniqueid)
            ],
        )

        return self.execute(q).fetchall()


class PhonefunckeysHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        # get all supervised user/group/queue/meetme
        extensions = self.db.extensions._table
        linefeatures = self.db.linefeatures._table
        phonefunckey = self.db.phonefunckey._table
        user_line = self.db.user_line._table

        conds = [
            user_line.c.user_id == phonefunckey.c.iduserfeatures,
            user_line.c.line_id == linefeatures.c.id,
            user_line.c.main_user == True,
            user_line.c.main_line == True,
            phonefunckey.c.typeextenumbers == None,
            phonefunckey.c.typevalextenumbers == None,
            phonefunckey.c.typeextenumbersright.in_(('group', 'queue', 'meetme')),
            phonefunckey.c.supervision == 1,
        ]
        if 'context' in kwargs:
            conds.append(linefeatures.c.context == kwargs['context'])

        q = select(
            [phonefunckey.c.typeextenumbersright, phonefunckey.c.typevalextenumbersright, extensions.c.exten],
            and_(*conds),
            from_obj=[
                phonefunckey.outerjoin(extensions, and_(
                    cast(phonefunckey.c.typeextenumbersright, VARCHAR(255)) == cast(extensions.c.type, VARCHAR(255)),
                    phonefunckey.c.typevalextenumbersright == extensions.c.typeval))],
        )

        return self.execute(q).fetchall()


class ProgfunckeysHintsHandler(SpecializedHandler):
    def all(self, *args, **kwargs):
        extensions = self.db.extensions._table
        linefeatures = self.db.linefeatures._table
        phonefunckey = self.db.phonefunckey._table
        user_line = self.db.user_line._table

        conds = [
            user_line.c.user_id == phonefunckey.c.iduserfeatures,
            user_line.c.main_user == True,
            user_line.c.main_line == True,
            user_line.c.line_id == linefeatures.c.id,
            phonefunckey.c.typeextenumbers != None,
            phonefunckey.c.typevalextenumbers != None,
            phonefunckey.c.supervision == 1,
            phonefunckey.c.progfunckey == 1,
            cast(phonefunckey.c.typeextenumbers, VARCHAR(255)) == cast(extensions.c.type, VARCHAR(255)),
            phonefunckey.c.typevalextenumbers != 'user',
            phonefunckey.c.typevalextenumbers == extensions.c.typeval
        ]
        if 'context' in kwargs:
            conds.append(linefeatures.c.context == kwargs['context'])

        q = select(
            [phonefunckey.c.iduserfeatures, phonefunckey.c.exten, phonefunckey.c.typeextenumbers,
             phonefunckey.c.typevalextenumbers, phonefunckey.c.typeextenumbersright,
             phonefunckey.c.typevalextenumbersright, extensions.c.exten.label('leftexten')],
            and_(*conds)
        )
        return self.execute(q).fetchall()


class PickupsHandler(SpecializedHandler):
    """

        NOTE: all user lines can be intercepted/intercept calls
    """
    def all(self, usertype, *args, **kwargs):
        if usertype not in ('sip', 'iax'):
            raise TypeError

        (_p, _pm, _lf, _u, _g, _q, _qm, _ul) = [getattr(self.db, options)._table.c for options in
                ('pickup', 'pickupmember', 'linefeatures', 'user' + usertype, 'groupfeatures',
                'queuefeatures', 'queuemember', 'user_line')]

        # simple users
        q1 = select([_u.name, _pm.category, _p.id],
            and_(
                _p.commented == 0,
                _p.id == _pm.pickupid,
                _pm.membertype == 'user',
                _pm.memberid == _ul.user_id,
                _ul.id == _ul.line_id,
                _lf.protocol == usertype,
                _lf.protocolid == _u.id
            )
        )

        # groups
        q2 = select([_u.name, _pm.category, _p.id],
            and_(
                _p.commented == 0,
                _p.id == _pm.pickupid,
                _pm.membertype == 'group',
                _pm.memberid == _g.id,
                _g.name == _qm.queue_name,
                _qm.usertype == 'user',
                _qm.userid == _ul.user_id,
                _ul.id == _ul.line_id,
                _lf.protocol == usertype,
                _lf.protocolid == _u.id
            )
        )

        # queues
        q3 = select([_u.name, _pm.category, _p.id],
            and_(
                _p.commented == 0,
                _p.id == _pm.pickupid,
                _pm.membertype == 'queue',
                _pm.memberid == _q.id,
                _q.name == _qm.queue_name,
                _qm.usertype == 'user',
                _qm.userid == _ul.user_id,
                _lf.id == _ul.line_id,
                _lf.protocol == usertype,
                _lf.protocolid == _u.id
            )
        )

        return self.execute(q1.union(q2.union(q3))).fetchall()


class QueuePenaltiesHandler(SpecializedHandler):
    def all(self, **kwargs):
        (_p, _pc) = [getattr(self.db, options)._table.c for options in ('queuepenalty', 'queuepenaltychange')]

        q = select(
                [_p.name, _pc.seconds, _pc.maxp_sign, _pc.maxp_value, _pc.minp_sign, _pc.minp_value],
                and_(
                    _p.commented == 0,
                    _p.id == _pc.queuepenalty_id
                )
        ).order_by(_p.name)

        return self.execute(q).fetchall()


class TrunksHandler(SpecializedHandler):
    def all(self, **kwargs):
        (_t, _s, _i) = [getattr(self.db, options)._table.c for options in ('trunkfeatures', 'usersip', 'useriax')]

        q1 = select([_t.id, _t.protocol, _s.username, _s.secret, _s.host],
            and_(
                _t.protocol == 'sip',
                _t.protocolid == _s.id,
                _s.commented == 0,
            )
        )
        q2 = select([_t.id, _t.protocol, _i.username, _i.secret, _i.host],
            and_(
                _t.protocol == 'iax',
                _t.protocolid == _i.id,
                _i.commented == 0,
            )
        )

        return self.execute(q2.union(q1)).fetchall()
        # return self.execute(q1).fetchall()


class SipUsersHandler(SpecializedHandler):

    def all(self):
        usersip = self.db.usersip._table
        linefeatures = self.db.linefeatures._table

        query = select(
            [usersip, linefeatures.c.number],
            and_(usersip.c.commented == '0',
                 usersip.c.category == 'user',
                 linefeatures.c.protocol == 'sip',
                 linefeatures.c.protocolid == usersip.c.id)
        )

        sip_users = self.execute(query).fetchall()
        return map(dict, sip_users)


class ExtenFeaturesHandler(SpecializedHandler):

    def all(self, features=[], *args, **kwargs):
        extensions = self.db.extensions._table
        q = select(
            [extensions.c.typeval,
             extensions.c.exten,
             extensions.c.commented],
            and_(extensions.c.context == 'xivo-features',
                 extensions.c.type == 'extenfeatures',
                 extensions.c.typeval.in_(features))
        ).order_by('exten')

        return self.execute(q).fetchall()


class QObject(object):
    _translation = {
        'sccpgeneralsettings': SccpGeneralSettingsHandler,
        'sccpline': SccpLineHandler,
        'sccpdevice': ('sccpdevice',),
        'sccpspeeddial': SccpSpeedDialHandler,
        'sip': ('staticsip',),
        'iax': ('staticiax',),
        'voicemail': ('staticvoicemail',),
        'queue': ('staticqueue',),
        'agentfeatures': ('agentfeatures',),
        'meetme': ('staticmeetme',),
        'musiconhold': ('musiconhold',),
        'features': ('features',),

        'sipauth': ('sipauthentication',),
        'iaxcalllimits': ('iaxcallnumberlimits',),

        'sipusers': SipUsersHandler,
        'iaxusers': ('useriax', {'category': 'user'}),

        'trunks': TrunksHandler,
        'siptrunks': ('usersip', {'category': 'trunk'}),
        'iaxtrunks': ('useriax', {'category': 'trunk'}),

        'voicemails': ('voicemail',),
        'queues': ('queue',),
        'queuemembers': ('queuemember',),
        'queuepenalty': ('queuepenalty',),

        'agentqueueskills': AgentQueueskillsHandler,
        'queueskillrules': ('queueskillrule',),
        'extensions': ('extensions',),
        'extenfeatures': ExtenFeaturesHandler,
        'contexts': ('context',),
        'contextincludes': ('contextinclude',),

        'voicemenus': ('voicemenu',),
        'hints': HintsHandler,
        'phonefunckeys': PhonefunckeysHandler,
        'progfunckeys': ProgfunckeysHintsHandler,

        'pickups': PickupsHandler,
        'queuepenalties': QueuePenaltiesHandler,
        'parkinglot': ('parkinglot',),
        'general': ('general',),
    }

    def __init__(self, db, name):
        self.db = db
        self.name = name

    @iterable('list')
    def all(self, commented=None, order=None, asc=True, **kwargs):
        _trans = self._translation.get(self.name, (self.name,))
        q = getattr(self.db, _trans[0])

        # # FILTERING
        conds = []
        if isinstance(commented, bool):
            conds.append(q.commented == int(commented))

        if len(_trans) > 1:
            for k, v in _trans[1].iteritems():
                conds.append(getattr(q, k) == v)

        for k, v in kwargs.iteritems():
            conds.append(getattr(q, k) == v)

        q = q.filter(and_(*conds))

        # # ORDERING
        if order is not None:
            if not asc:
                order = desc(order)
            q = q.order_by(order)

        return q.all()

    @iterable('single')
    def get(self, **kwargs):
        q = getattr(self.db, self._translation.get(self.name, (self.name,))[0])

        conds = []
        for k, v in kwargs.iteritems():
            conds.append(getattr(q, k) == v)
        return q.filter(and_(*conds)).first()


class XivoDBBackend(object):
    def __init__(self, uri):
        self.db = SqlSoup(uri,
                session=scoped_session(sessionmaker(autoflush=True, expire_on_commit=False, autocommit=True)))

    def __getattr__(self, name):
        if not name in QObject._translation:
            raise KeyError(name)

        if inspect.isclass(QObject._translation[name]) and\
             issubclass(QObject._translation[name], SpecializedHandler):
            return QObject._translation[name](self.db, name)

        return QObject(self.db, name)
