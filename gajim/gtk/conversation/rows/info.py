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

import time
from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common.const import AvatarSize

from .widgets import SimpleLabel
from .base import BaseRow


class InfoMessage(BaseRow):
    def __init__(self, account: str, text: str) -> None:
        BaseRow.__init__(self, account)

        self.type = 'info'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        text = GLib.markup_escape_text(text)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        icon = Gtk.Image.new_from_icon_name('feather-info-symbolic',
                                            Gtk.IconSize.MENU)
        icon.get_style_context().add_class('gajim-status-message')
        self.grid.attach(icon, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.get_style_context().add_class('gajim-status-message')
        self._label.set_text(text)
        self.grid.attach(self._label, 2, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()
