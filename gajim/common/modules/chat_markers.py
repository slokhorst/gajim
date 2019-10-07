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

# Chat Markers (XEP-0333)

import nbxmpp
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class ChatMarkers(BaseModule):

    _nbxmpp_extends = 'ChatMarkers'

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_read_state_sync,
                          ns=nbxmpp.NS_CHATMARKERS,
                          priority=47),
            StanzaHandler(name='message',
                          callback=self._process_chat_marker,
                          ns=nbxmpp.NS_CHATMARKERS,
                          priority=48),
        ]

    def _process_read_state_sync(self, _con, _stanza, properties):
        if not properties.is_marker:
            return

        if not properties.marker.is_displayed:
            return

        if properties.type.is_error:
            return

        if properties.is_mam_message:
            return

        if properties.type.is_groupchat:
            manager = self._con.get_module('MUC').get_manager()
            muc_data = manager.get(properties.muc_jid)
            if muc_data is None:
                return

            if properties.muc_nickname != muc_data.nick:
                return

        elif not properties.is_carbon_message or not properties.carbon.is_sent:
            return

        self._log.info('Read state sync: %s %s',
                       properties.jid,
                       properties.marker.id)

        app.nec.push_outgoing_event(
            NetworkEvent('read-state-sync',
                         account=self._account,
                         jid=properties.jid,
                         properties=properties,
                         type=properties.type,
                         is_muc_pm=properties.is_muc_pm,
                         marker_id=properties.marker.id))

        raise nbxmpp.NodeProcessed

    def _process_chat_marker(self, _con, _stanza, properties):
        if not properties.is_marker:
            return
        # TODO: Implement showing displayed state in ConversationsTextview
        raise nbxmpp.NodeProcessed

    def _send_marker(self, contact, marker, id_, type_):
        jid = contact.jid
        if contact.is_pm_contact:
            jid = app.get_jid_without_resource(contact.jid)

        config = 'rooms' if type_ in ('gc', 'pm') else 'contacts'
        if not app.config.get_per(config, jid, 'send_marker', False):
            return

        typ = 'groupchat' if type_ == 'gc' else 'chat'
        message = nbxmpp.Message(to=contact.jid, typ=typ)
        message.setMarker(marker, id_)
        self._log.info('Send %s: %s', marker, contact.jid)
        self._nbxmpp().send(message)

    def send_displayed_marker(self, contact, id_, type_):
        self._send_marker(contact, 'displayed', id_, type_)


def get_instance(*args, **kwargs):
    return ChatMarkers(*args, **kwargs), 'ChatMarkers'
