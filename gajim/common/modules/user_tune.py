# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0118: User Tune

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import ged
from gajim.common.events import TuneReceived
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import store_publish
from gajim.common.dbus.music_track import MusicTrackListener
from gajim.common.helpers import event_filter


class UserTune(BaseModule):

    _nbxmpp_extends = 'Tune'
    _nbxmpp_methods = [
        'set_tune',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._tune_received)
        self._tune_data = None
        self._tunes = {}

        self.register_events([
            ('music-track-changed', ged.CORE, self._on_music_track_changed),
            ('signed-in', ged.CORE, self._on_signed_in),
        ])

    def get_current_tune(self):
        return self._tune_data

    @event_node(Namespace.TUNE)
    def _tune_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        if properties.is_self_message:
            self._tune_data = data
        else:
            self._tunes[properties.jid] = data

        app.ged.raise_event(TuneReceived(
            account=self._account,
            jid=properties.jid.bare,
            tune=data,
            is_self_message=properties.is_self_message))

    @store_publish
    def set_tune(self, tune):
        if not self._con.get_module('PEP').supported:
            return

        if not app.settings.get_account_setting(self._account, 'publish_tune'):
            return

        if tune == self._tune_data:
            return

        self._tune_data = tune

        self._log.info('Send %s', tune)
        self._nbxmpp('Tune').set_tune(tune)

    def set_enabled(self, enable):
        if enable:
            app.settings.set_account_setting(self._account,
                                             'publish_tune',
                                             True)
            self._publish_current_tune()

        else:
            self.set_tune(None)
            app.settings.set_account_setting(self._account,
                                             'publish_tune',
                                             False)

    def _publish_current_tune(self):
        self.set_tune(MusicTrackListener.get().current_tune)

    @event_filter(['account'])
    def _on_signed_in(self, _event):
        self._publish_current_tune()

    def _on_music_track_changed(self, event):
        if self._tune_data == event.info:
            return

        self.set_tune(event.info)
