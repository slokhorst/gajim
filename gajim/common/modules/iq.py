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
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# Iq handler

import nbxmpp
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.events import FileRequestError
from gajim.common.events import FileSendError
from gajim.common.events import IqErrorReceived
from gajim.common.helpers import to_user_string
from gajim.common.file_props import FilesProp
from gajim.common.modules.base import BaseModule


class Iq(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._iq_error_received,
                          typ='error',
                          priority=51),
        ]

    def _iq_error_received(self, _con, _stanza, properties):
        self._log.info('Error: %s', properties.error)
        if properties.error.condition in ('jid-malformed',
                                          'forbidden',
                                          'not-acceptable'):
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                if properties.error.condition == 'jid-malformed':
                    file_props.error = -3
                else:
                    file_props.error = -4
                app.ged.raise_event(
                    FileRequestError(
                        conn=self._con,
                        jid=properties.jid.bare,
                        file_props=file_props,
                        error_msg=to_user_string(properties.error)))
                self._con.get_module('Bytestream').disconnect_transfer(
                    file_props)
                raise nbxmpp.NodeProcessed

        if properties.error.condition == 'item-not-found':
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                app.ged.raise_event(
                    FileSendError(account=self._account,
                                  jid=str(properties.jid),
                                  file_props=file_props,
                                  error_msg=''))
                self._con.get_module('Bytestream').disconnect_transfer(
                    file_props)
                raise nbxmpp.NodeProcessed

        app.ged.raise_event(
            IqErrorReceived(account=self._account,
                            properties=properties))
        raise nbxmpp.NodeProcessed

    @staticmethod
    def _get_sid(id_):
        sid = id_
        if len(id_) > 3 and id_[2] == '_':
            sid = id_[3:]
        return sid
