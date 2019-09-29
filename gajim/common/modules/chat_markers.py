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
#TODO: add <thread> support

import nbxmpp

from gajim.common.modules.base import BaseModule


class ChatMarkers(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

    def send_marker(self, jid, marker, id_, is_gc):
        if is_gc:
            message = nbxmpp.Message(to=jid, typ='groupchat')
        else:
            message = nbxmpp.Message(to=jid, typ='chat')
        message.setTag(marker, namespace=nbxmpp.NS_CHATMARKERS,
            attrs={'id': id_})
        self._nbxmpp().send(message)

    def send_displayed_marker(self, jid, id_, is_gc):
        self.send_marker(jid, 'displayed', id_, is_gc)

def get_instance(*args, **kwargs):
    return ChatMarkers(*args, **kwargs), 'ChatMarkers'
