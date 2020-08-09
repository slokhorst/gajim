# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0313: Message Archive Management

import time
from datetime import datetime
from datetime import timedelta

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.util import generate_id
from nbxmpp.util import is_error_result
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.const import ArchiveState
from gajim.common.const import KindConstant
from gajim.common.const import SyncThreshold
from gajim.common.helpers import get_sync_threshold
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.base import BaseModule


class MAM(BaseModule):

    _nbxmpp_extends = 'MAM'
    _nbxmpp_methods = [
        'request_preferences',
        'set_preferences',
        'make_query',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._set_message_archive_info,
                          priority=41),
            StanzaHandler(name='message',
                          callback=self._mam_message_received,
                          priority=51),
        ]

        self.available = False
        self._mam_query_ids = {}

        # Holds archive jids where catch up was successful
        self._catch_up_finished = []

    def pass_disco(self, info):
        if Namespace.MAM_2 not in info.features:
            return

        self.available = True
        self._log.info('Discovered MAM: %s', info.jid)

        app.nec.push_incoming_event(
            NetworkEvent('feature-discovered',
                         account=self._account,
                         feature=Namespace.MAM_2))

    def reset_state(self):
        self._mam_query_ids.clear()
        self._catch_up_finished.clear()

    def _remove_query_id(self, jid):
        self._mam_query_ids.pop(jid, None)

    def is_catch_up_finished(self, jid):
        return jid in self._catch_up_finished

    def _from_valid_archive(self, _stanza, properties):
        if properties.type.is_groupchat:
            expected_archive = properties.jid
        else:
            expected_archive = self._con.get_own_jid()

        return properties.mam.archive.bareMatch(expected_archive)

    def _get_unique_id(self, properties):
        if properties.type.is_groupchat:
            return properties.mam.id, None

        if properties.is_self_message:
            return None, properties.id

        if properties.is_muc_pm:
            return properties.mam.id, properties.id

        if self._con.get_own_jid().bareMatch(properties.from_):
            # message we sent
            return properties.mam.id, properties.id

        # A message we received
        return properties.mam.id, None

    def _set_message_archive_info(self, _con, _stanza, properties):
        if (properties.is_mam_message or
                properties.is_pubsub or
                properties.is_muc_subject):
            return

        if properties.type.is_groupchat:
            archive_jid = properties.jid.getBare()
            timestamp = properties.timestamp

            disco_info = app.logger.get_last_disco_info(archive_jid)
            if disco_info is None:
                # This is the case on MUC creation
                # After MUC configuration we receive a configuration change
                # message before we had the chance to disco the new MUC
                return

            if disco_info.mam_namespace != Namespace.MAM_2:
                return

        else:
            if not self.available:
                return

            archive_jid = self._con.get_own_jid().getBare()
            timestamp = None

        if properties.stanza_id is None:
            return

        if not archive_jid == properties.stanza_id.by:
            return

        if not self.is_catch_up_finished(archive_jid):
            return

        app.logger.set_archive_infos(archive_jid,
                                     last_mam_id=properties.stanza_id.id,
                                     last_muc_timestamp=timestamp)

    def _mam_message_received(self, _con, stanza, properties):
        if not properties.is_mam_message:
            return

        app.nec.push_incoming_event(
            NetworkIncomingEvent('mam-message-received',
                                 account=self._account,
                                 stanza=stanza,
                                 properties=properties))

        if not self._from_valid_archive(stanza, properties):
            self._log.warning('Message from invalid archive %s',
                              properties.mam.archive)
            raise nbxmpp.NodeProcessed

        self._log.info('Received message from archive: %s',
                       properties.mam.archive)
        if not self._is_valid_request(properties):
            self._log.warning('Invalid MAM Message: unknown query id %s',
                              properties.mam.query_id)
            self._log.debug(stanza)
            raise nbxmpp.NodeProcessed

        is_groupchat = properties.type.is_groupchat
        if is_groupchat:
            kind = KindConstant.GC_MSG
        else:
            if properties.from_.bareMatch(self._con.get_own_jid()):
                kind = KindConstant.CHAT_MSG_SENT
            else:
                kind = KindConstant.CHAT_MSG_RECV

        stanza_id, message_id = self._get_unique_id(properties)

        # Search for duplicates
        if app.logger.find_stanza_id(self._account,
                                     str(properties.mam.archive),
                                     stanza_id,
                                     message_id,
                                     groupchat=is_groupchat):
            self._log.info('Found duplicate with stanza-id: %s, '
                           'message-id: %s', stanza_id, message_id)
            raise nbxmpp.NodeProcessed

        additional_data = AdditionalDataDict()
        if properties.has_user_delay:
            # Record it as a user timestamp
            additional_data.set_value(
                'gajim', 'user_timestamp', properties.user_timestamp)

        parse_oob(properties, additional_data)

        msgtxt = properties.body

        if properties.is_encrypted:
            additional_data['encrypted'] = properties.encrypted.additional_data
        else:
            if properties.eme is not None:
                msgtxt = get_eme_message(properties.eme)

        if not msgtxt:
            # For example Chatstates, Receipts, Chatmarkers
            self._log.debug(stanza.getProperties())
            return

        with_ = properties.jid.getStripped()
        if properties.is_muc_pm:
            # we store the message with the full JID
            with_ = str(with_)

        if properties.is_self_message:
            # Self messages can only be deduped with origin-id
            if message_id is None:
                self._log.warning('Self message without origin-id found')
                return
            stanza_id = message_id

        app.logger.insert_into_logs(self._account,
                                    with_,
                                    properties.mam.timestamp,
                                    kind,
                                    unread=False,
                                    message=msgtxt,
                                    contact_name=properties.muc_nickname,
                                    additional_data=additional_data,
                                    stanza_id=stanza_id,
                                    message_id=properties.id)

        app.nec.push_incoming_event(
            NetworkEvent('mam-decrypted-message-received',
                         account=self._account,
                         additional_data=additional_data,
                         correct_id=parse_correction(properties),
                         archive_jid=properties.mam.archive,
                         msgtxt=properties.body,
                         properties=properties,
                         kind=kind,
                         )
        )

    def _is_valid_request(self, properties):
        valid_id = self._mam_query_ids.get(properties.mam.archive, None)
        return valid_id == properties.mam.query_id

    def _get_query_id(self, jid):
        query_id = generate_id()
        self._mam_query_ids[jid] = query_id
        return query_id

    def request_archive_on_signin(self):
        own_jid = self._con.get_own_jid().getBare()

        if own_jid in self._mam_query_ids:
            self._log.warning('Request already running: %s', own_jid)
            return

        archive = app.logger.get_archive_infos(own_jid)

        # Migration of last_mam_id from config to DB
        if archive is not None:
            mam_id = archive.last_mam_id
        else:
            mam_id = app.config.get_per(
                'accounts', self._account, 'last_mam_id')
            if mam_id:
                app.config.del_per('accounts', self._account, 'last_mam_id')

        start_date = None
        queryid = self._get_query_id(own_jid)
        if mam_id:
            self._log.info('Request archive: %s, after mam-id %s',
                           own_jid, mam_id)

        else:
            # First Start, we request the last week
            start_date = datetime.utcnow() - timedelta(days=7)
            self._log.info('Request archive: %s, after date %s',
                           own_jid, start_date)

        self._nbxmpp('MAM').make_query(own_jid,
                                       queryid,
                                       after=mam_id,
                                       start=start_date,
                                       callback=self._result_finished,
                                       user_data={'queryid': queryid,
                                                  'start': start_date,
                                                  'groupchat': False})

        if own_jid in self._catch_up_finished:
            self._catch_up_finished.remove(own_jid)

    def request_archive_on_muc_join(self, jid):
        archive = app.logger.get_archive_infos(jid)
        threshold = get_sync_threshold(jid, archive)
        self._log.info('Threshold for %s: %s', jid, threshold)

        mam_id = None
        start_date = None
        if archive is None or archive.last_mam_id is None:
            # First join
            start_date = datetime.utcnow() - timedelta(days=1)
            self._log.info('Request archive: %s, after date %s',
                           jid, start_date)

        elif threshold == SyncThreshold.NO_THRESHOLD:
            # Not our first join and no threshold set

            mam_id = archive.last_mam_id
            self._log.info('Request archive: %s, after mam-id %s',
                           jid, archive.last_mam_id)

        else:
            # Not our first join, check how much time elapsed since our
            # last join and check against threshold
            last_timestamp = archive.last_muc_timestamp
            if last_timestamp is None:
                self._log.info('No last muc timestamp found: %s', jid)
                last_timestamp = 0

            last = datetime.utcfromtimestamp(float(last_timestamp))
            if datetime.utcnow() - last > timedelta(days=threshold):
                # To much time has elapsed since last join, apply threshold
                start_date = datetime.utcnow() - timedelta(days=threshold)
                self._log.info('Too much time elapsed since last join, '
                               'request archive: %s, after date %s, '
                               'threshold: %s', jid, start_date, threshold)

            else:
                # Request from last mam-id
                mam_id = archive.last_mam_id
                self._log.info('Request archive: %s, after mam-id %s:',
                               jid, archive.last_mam_id)

        if jid in self._catch_up_finished:
            self._catch_up_finished.remove(jid)

        queryid = self._get_query_id(jid)
        self._nbxmpp('MAM').make_query(jid,
                                       queryid,
                                       after=mam_id,
                                       start=start_date,
                                       callback=self._result_finished,
                                       user_data={'queryid': queryid,
                                                  'start': start_date,
                                                  'groupchat': True})

    def _result_finished(self, result, user_data):
        queryid, start_date, groupchat = user_data.values()
        self._remove_query_id(result.jid)

        if is_error_result(result):
            if result.condition == 'item-not-found':
                app.logger.reset_archive_infos(result.jid)
                if groupchat:
                    self.request_archive_on_muc_join(result.jid)
                else:
                    self.request_archive_on_signin()
            return

        if result.complete:
            self._catch_up_finished.append(result.jid)
            self._log.info('Request finished: %s, last mam id: %s',
                           result.jid, result.rsm.last)

            if result.rsm.last is not None:
                # <last> is not provided if the requested page was empty
                # so this means we did not get anything hence we only need
                # to update the archive info if <last> is present
                app.logger.set_archive_infos(result.jid,
                                             last_mam_id=result.rsm.last,
                                             last_muc_timestamp=time.time())

            if start_date is not None and not groupchat:
                # Record the earliest timestamp we request from
                # the account archive. For the account archive we only
                # set start_date at the very first request.
                app.logger.set_archive_infos(
                    result.jid,
                    oldest_mam_timestamp=start_date.timestamp())

        else:
            app.logger.set_archive_infos(result.jid,
                                         last_mam_id=result.rsm.last)
            queryid = self._get_query_id(result.jid)

            self._nbxmpp('MAM').make_query(result.jid,
                                           queryid,
                                           after=result.rsm.last,
                                           start=start_date,
                                           callback=self._result_finished,
                                           user_data={'queryid': queryid,
                                                      'start': start_date,
                                                      'groupchat': groupchat})

    def request_archive_interval(self,
                                 start_date,
                                 end_date,
                                 after=None,
                                 queryid=None):

        jid = self._con.get_own_jid().getBare()

        if after is None:
            self._log.info('Request interval: %s, from %s to %s',
                           jid, start_date, end_date)
        else:
            self._log.info('Request page: %s, after %s', jid, after)

        if queryid is None:
            queryid = self._get_query_id(jid)
        self._mam_query_ids[jid] = queryid

        self._nbxmpp('MAM').make_query(jid,
                                       queryid,
                                       after=after,
                                       start=start_date,
                                       end=end_date,
                                       callback=self._on_interval_result,
                                       user_data={'queryid': queryid,
                                                  'start_date': start_date,
                                                  'end_date': end_date})
        return queryid

    def _on_interval_result(self, result, user_data):
        queryid, start_date, end_date = user_data.values()
        self._remove_query_id(result.jid)

        if is_error_result(result):
            return

        if start_date:
            timestamp = start_date.timestamp()
        else:
            timestamp = ArchiveState.ALL

        if result.complete:
            self._log.info('Request finished: %s, last mam id: %s',
                           result.jid, result.rsm.last)
            app.logger.set_archive_infos(result.jid,
                                         oldest_mam_timestamp=timestamp)
            app.nec.push_incoming_event(NetworkEvent(
                'archiving-interval-finished',
                account=self._account,
                query_id=queryid))

        else:
            self.request_archive_interval(start_date,
                                          end_date,
                                          result.rsm.last,
                                          queryid)


def get_instance(*args, **kwargs):
    return MAM(*args, **kwargs), 'MAM'
