# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

from gajim import message_control

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import AvatarSize

from gajim.chat_control import ChatControl
from gajim.command_system.implementation.hosts import PrivateChatCommands

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.util import get_icon_name


class PrivateChatControl(ChatControl):
    TYPE_ID = message_control.TYPE_PM

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, parent_win, gc_contact, contact, account, session):
        room_jid = gc_contact.room_jid
        self.room_ctrl = app.interface.msg_win_mgr.get_gc_control(
            room_jid, account)
        if room_jid in app.interface.minimized_controls[account]:
            self.room_ctrl = app.interface.minimized_controls[account][room_jid]
        if self.room_ctrl:
            self.room_name = self.room_ctrl.name
        else:
            self.room_name = room_jid
        self.gc_contact = gc_contact
        ChatControl.__init__(self, parent_win, contact, account, session)
        self.TYPE_ID = 'pm'

        self.__event_handlers = [
            ('update-gc-avatar', ged.GUI1, self._nec_update_avatar),
            ('caps-update', ged.GUI1, self._nec_caps_received_pm),
            ('muc-user-joined', ged.GUI1, self._on_user_joined),
            ('muc-user-left', ged.GUI1, self._on_user_left),
            ('muc-nickname-changed', ged.GUI1, self._on_nickname_changed),
            ('muc-self-presence', ged.GUI1, self._on_self_presence),
            ('muc-self-kicked', ged.GUI1, self._on_diconnected),
            ('muc-user-status-show-changed', ged.GUI1, self._on_status_show_changed),
            ('muc-destroyed', ged.GUI1, self._on_diconnected),
        ]

        for handler in self.__event_handlers:
            app.ged.register_event_handler(*handler)

    @property
    def contact(self):
        return self.gc_contact.as_contact()

    @contact.setter
    def contact(self, _value):
        # TODO: remove all code that sets the contact here
        return

    def get_our_nick(self):
        return self.room_ctrl.nick

    def shutdown(self):
        super(PrivateChatControl, self).shutdown()
        for handler in self.__event_handlers:
            app.ged.remove_event_handler(*handler)

    def _nec_caps_received_pm(self, obj):
        if obj.conn.name != self.account or \
        obj.fjid != self.gc_contact.get_full_jid():
            return
        self.update_contact()

    def _on_nickname_changed(self, event):
        if event.account != self.account:
            return
        if event.properties.new_jid != self.gc_contact.get_full_jid():
            return

        nick = event.properties.muc_nickname
        new_nick = event.properties.muc_user.nick
        if event.properties.is_muc_self_presence:
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)

        self.print_conversation(message, 'info')

        self.draw_banner()
        app.interface.msg_win_mgr.change_key(str(event.properties.jid),
                                             str(event.properties.new_jid),
                                             self.account)

        self.parent_win.redraw_tab(self)
        self.update_ui()

    def _on_status_show_changed(self, event):
        if event.account != self.account:
            return
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        nick = event.properties.muc_nickname
        status = event.properties.status
        status = '' if status is None else ' (%s)' % status
        show = helpers.get_uf_show(event.properties.show.value)

        status_default = app.config.get('print_status_muc_default')

        if event.properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)
            self.print_conversation(message, 'info')

        elif app.config.get_per('rooms', self.room_name,
                                'print_status', status_default):
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
            self.print_conversation(message, 'info')

        self.parent_win.redraw_tab(self)
        self.update_ui()

    def _on_diconnected(self, event):
        if event.account != self.account:
            return
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.got_disconnected()

    def _on_user_left(self, event):
        if event.account != self.account:
            return
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.got_disconnected()

    def _on_user_joined(self, event):
        if event.account != self.account:
            return
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.gc_contact = app.contacts.get_gc_contact(
            self.account, self.gc_contact.room_jid, self.gc_contact.name)
        self.parent_win.redraw_tab(self)
        self.got_connected()

    def _on_self_presence(self, event):
        if event.account != self.account:
            return
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.parent_win.redraw_tab(self)
        self.got_connected()

    def send_message(self, message, xhtml=None, process_commands=True,
                     attention=False):
        """
        Call this method to send the message
        """
        message = helpers.remove_invalid_xml_chars(message)
        if not message:
            return

        # We need to make sure that we can still send through the room and that
        # the recipient did not go away
        if self.gc_contact.presence.is_unavailable:
            ErrorDialog(
                _('Sending private message failed'),
                #in second %s code replaces with nickname
                _('You are no longer in group chat "%(room)s" or '
                  '"%(nick)s" has left.') % {
                      'room': self.room_name, 'nick': self.gc_contact.name},
                transient_for=self.parent_win.window)
            return

        ChatControl.send_message(self, message,
                                 xhtml=xhtml,
                                 process_commands=process_commands,
                                 attention=attention)

    def update_ui(self):
        if self.gc_contact.presence.is_unavailable:
            self.got_disconnected()
        else:
            self.got_connected()

    def _nec_update_avatar(self, obj):
        if obj.contact != self.gc_contact:
            return
        self.show_avatar()

    def show_avatar(self):
        if not app.config.get('show_avatar_in_chat'):
            return

        scale = self.parent_win.window.get_scale_factor()
        surface = app.interface.get_avatar(
            self.gc_contact.avatar_sha, AvatarSize.CHAT, scale)
        image = self.xml.get_object('avatar_image')
        if surface is None:
            image.set_from_icon_name('avatar-default', Gtk.IconSize.DIALOG)
        else:
            image.set_from_surface(surface)

    def _update_banner_state_image(self):
        # Set banner image
        if self.gc_contact.presence.is_unavailable:
            icon = get_icon_name('offline')
        else:
            icon = get_icon_name(self.gc_contact.show.value)
        banner_status_img = self.xml.get_object('banner_status_image')
        banner_status_img.set_from_icon_name(icon, Gtk.IconSize.DND)

    def get_tab_image(self, count_unread=True):
        jid = self.gc_contact.get_full_jid()
        if app.config.get('show_avatar_in_tabs'):
            scale = self.parent_win.window.get_scale_factor()
            surface = app.contacts.get_avatar(
                self.account, jid, AvatarSize.TAB, scale)
            if surface is not None:
                return surface

        if count_unread:
            num_unread = len(app.events.get_events(
                self.account, jid, ['printed_' + self.type_id, self.type_id]))
        else:
            num_unread = 0

        transport = None
        if app.jid_is_transport(jid):
            transport = app.get_transport_name_from_jid(jid)

        if self.gc_contact.presence.is_unavailable:
            show = 'offline'
        else:
            show = self.gc_contact.show.value

        if num_unread and app.config.get('show_unread_tab_icon'):
            icon_name = get_icon_name('event', transport=transport)
        else:
            icon_name = get_icon_name(show, transport=transport)

        return icon_name

    def update_contact(self):
        self.contact = self.gc_contact.as_contact()

    def got_disconnected(self):
        ChatControl.got_disconnected(self)
        self.parent_win.redraw_tab(self)
        ChatControl.update_ui(self)

    def got_connected(self):
        ChatControl.got_connected(self)
        ChatControl.update_ui(self)