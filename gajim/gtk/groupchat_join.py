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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.const import MUC_DISCO_ERRORS

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.util import ensure_not_destroyed



class GroupchatJoin(Gtk.ApplicationWindow):
    def __init__(self, account, jid):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('GroupchatJoin')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Join Group Chat'))

        self._destroyed = False
        self.account = account
        self.jid = jid

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=18)
        self._main_box.set_valign(Gtk.Align.FILL)

        self._muc_info_box = GroupChatInfoScrolled(account)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._muc_info_box, 'info')
        self._stack.add_named(ProgressPage(), 'progress')
        self._stack.add_named(ErrorPage(), 'error')

        self._stack.set_visible_child_name('progress')
        self._stack.get_visible_child().start()

        self._stack.connect('notify::visible-child-name', self._on_page_changed)

        self._main_box.add(self._stack)

        self._join_button = Gtk.Button.new_with_mnemonic(_('_Join'))
        self._join_button.set_halign(Gtk.Align.END)
        self._join_button.set_sensitive(False)
        self._join_button.get_style_context().add_class('suggested-action')
        self._join_button.connect('clicked', self._on_join)

        self._main_box.add(self._join_button)

        self.connect('key-press-event', self._on_key_press_event)
        self.connect('destroy', self._on_destroy)

        self.add(self._main_box)
        self.show_all()

        self._disco_muc(jid)

    def _on_page_changed(self, stack, _param):
        name = stack.get_visible_child_name()
        self._join_button.set_sensitive(name == 'info')

    def _disco_muc(self, jid):
        con = app.connections[self.account]
        con.get_module('Discovery').disco_info(
            jid, callback=self._disco_info_received)

    @ensure_not_destroyed
    def _disco_info_received(self, result):
        if is_error_result(result):
            self._set_error(result)

        elif result.is_muc:
            self._muc_info_box.set_from_disco_info(result)
            self._stack.set_visible_child_name('info')

        else:
            self._set_error_from_code('not-muc-service')

    def _show_error_page(self, text):
        self._stack.get_child_by_name('error').set_text(text)
        self._stack.set_visible_child_name('error')

    def _set_error(self, error):
        text = MUC_DISCO_ERRORS.get(error.type, str(error))
        self._show_error_page(text)

    def _set_error_from_code(self, error_code):
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _on_join(self, _button):
        app.interface.join_gc_room(self.account, self.jid, None, None)
        self.destroy()

    def _on_destroy(self, *args):
        self._destroyed = True

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()


class ErrorPage(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_vexpand(True)
        self.set_homogeneous(True)
        error_icon = Gtk.Image.new_from_icon_name(
            'dialog-error', Gtk.IconSize.DIALOG)
        error_icon.set_valign(Gtk.Align.END)

        self._error_label = Gtk.Label()
        self._error_label.set_valign(Gtk.Align.START)
        self._error_label.get_style_context().add_class('bold16')
        self._error_label.set_line_wrap(True)
        self._error_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._error_label.set_size_request(150, -1)

        self.add(error_icon)
        self.add(self._error_label)
        self.show_all()

    def set_text(self, text):
        self._error_label.set_text(text)


class ProgressPage(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_vexpand(True)
        self.set_homogeneous(True)
        self._spinner = Gtk.Spinner()

        self.add(self._spinner)
        self.show_all()

    def start(self):
        self._spinner.start()

    def stop(self):
        self._spinner.stop()