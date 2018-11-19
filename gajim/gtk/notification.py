# Copyright (C) 2005 Sebastian Estienne
# Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
#                    Stephan Erb <steve-e AT h3c.de>
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

import sys
import logging

from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

from gajim import gtkgui_helpers
from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.i18n import _

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_monitor_scale_factor
from gajim.gtk.util import get_total_screen_geometry
from gajim.gtk.util import load_icon

log = logging.getLogger('gajim.gtk.notification')


class Notification:
    """
    Handle notifications
    """
    def __init__(self):
        self._daemon_capabilities = ['actions']
        self._win32_active_popup = None

        # Detect if actions are supported by the notification daemon
        if sys.platform not in ('win32', 'darwin'):
            def on_proxy_ready(_source, res, _data=None):
                try:
                    proxy = Gio.DBusProxy.new_finish(res)
                    self._daemon_capabilities = proxy.GetCapabilities()
                except GLib.Error as error:
                    if error.domain == 'g-dbus-error-quark':
                        log.info('Notifications D-Bus connection failed: %s',
                                 error.message)
                    else:
                        raise
                else:
                    log.debug('Notifications D-Bus connected')

            log.debug('Connecting to Notifications D-Bus')
            Gio.DBusProxy.new_for_bus(Gio.BusType.SESSION,
                                      Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                                      None,
                                      'org.freedesktop.Notifications',
                                      '/org/freedesktop/Notifications',
                                      'org.freedesktop.Notifications',
                                      None,
                                      on_proxy_ready)

        app.ged.register_event_handler(
            'notification', ged.GUI2, self._nec_notification)
        app.ged.register_event_handler(
            'our-show', ged.GUI2, self._nec_our_status)
        app.events.event_removed_subscribe(self._on_event_removed)

    def _nec_notification(self, obj):
        if obj.do_popup:
            icon_name = self._get_icon_name(obj)
            self.popup(obj.popup_event_type, obj.jid, obj.conn.name,
                       obj.popup_msg_type, icon_name=icon_name,
                       title=obj.popup_title, text=obj.popup_text,
                       timeout=obj.popup_timeout)

        if obj.do_sound:
            if obj.sound_file:
                helpers.play_sound_file(obj.sound_file)
            elif obj.sound_event:
                helpers.play_sound(obj.sound_event)

        if obj.do_command:
            try:
                helpers.exec_command(obj.command, use_shell=True)
            except Exception:
                pass

    def _on_event_removed(self, event_list):
        for event in event_list:
            if event.type_ == 'gc-invitation':
                self._withdraw('gc-invitation', event.account, event.room_jid)
            if event.type_ in ('normal', 'printed_chat', 'chat',
                               'printed_pm', 'pm'):
                self._withdraw('new-message', event.account, event.jid)

    def _nec_our_status(self, obj):
        if app.account_is_connected(obj.conn.name):
            self._withdraw('connection-failed', obj.conn.name)

    @staticmethod
    def _get_icon_name(obj):
        if obj.notif_type == 'msg':
            if obj.base_event.mtype == 'pm':
                return 'gajim-priv_msg_recv'
            if obj.base_event.mtype == 'normal':
                return 'gajim-single_msg_recv'

        elif obj.notif_type == 'pres':
            if obj.transport_name is not None:
                return '%s-%s' % (obj.transport_name, obj.show)
            return get_icon_name(obj.show)

    def popup(self, event_type, jid, account, type_='', icon_name=None,
              title=None, text=None, timeout=-1, room_jid=None):
        """
        Notify a user of an event using GNotification and GApplication under
        Linux, Use PopupNotificationWindow under Windows
        """

        if icon_name is None:
            icon_name = 'gajim-chat_msg_recv'

        if timeout < 0:
            timeout = app.config.get('notification_timeout')

        if sys.platform == 'win32':
            self._withdraw()
            self._win32_active_popup = PopupNotification(
                event_type, jid, account, type_,
                icon_name, title, text, timeout)
            self._win32_active_popup.connect('destroy', self._on_popup_destroy)
            return

        scale = get_monitor_scale_factor()
        icon_pixbuf = load_icon(icon_name, size=48, pixbuf=True, scale=scale)

        notification = Gio.Notification()
        if title is not None:
            notification.set_title(title)
        if text is not None:
            notification.set_body(text)
        notif_id = None
        if event_type in (
                _('Contact Signed In'), _('Contact Signed Out'),
                _('New Message'), _('New Single Message'), _('New Private Message'),
                _('Contact Changed Status'), _('File Transfer Request'),
                _('File Transfer Error'), _('File Transfer Completed'),
                _('File Transfer Stopped'), _('Groupchat Invitation'),
                _('Connection Failed'), _('Subscription request'),
                _('Unsubscribed')):
            if 'actions' in self._daemon_capabilities:
                # Create Variant Dict
                dict_ = {'account': GLib.Variant('s', account),
                         'jid': GLib.Variant('s', jid),
                         'type_': GLib.Variant('s', type_)}
                variant_dict = GLib.Variant('a{sv}', dict_)
                action = 'app.{}-open-event'.format(account)
                #Button in notification
                notification.add_button_with_target(_('Open'), action,
                                                    variant_dict)
                notification.set_default_action_and_target(action,
                                                           variant_dict)

            # Only one notification per JID
            if event_type in (_('Contact Signed In'),
                              _('Contact Signed Out'),
                              _('Contact Changed Status')):
                notif_id = self._make_id('contact-status-changed', account, jid)
            elif event_type == _('Groupchat Invitation'):
                notif_id = self._make_id('gc-invitation', account, room_jid)
            elif event_type == _('Connection Failed'):
                notif_id = self._make_id('connection-failed', account)
            elif event_type in (_('New Message'),
                                _('New Single Message'),
                                _('New Private Message')):
                avatar = app.contacts.get_avatar(account, jid)
                if avatar:
                    icon_pixbuf = avatar
                notif_id = self._make_id('new-message', account, jid)

        notification.set_icon(icon_pixbuf)
        notification.set_priority(Gio.NotificationPriority.NORMAL)

        app.app.send_notification(notif_id, notification)

    def _on_popup_destroy(self, *args):
        self._win32_active_popup = None

    def _withdraw(self, *args):
        if sys.platform == 'win32':
            if self._win32_active_popup is not None:
                self._win32_active_popup.destroy()
        else:
            app.app.withdraw_notification(self._make_id(*args))

    @staticmethod
    def _make_id(*args):
        return ','.join(args)


class PopupNotification(Gtk.Window):
    def __init__(self, event_type, jid, account, msg_type='',
                 icon_name=None, title=None, text=None, timeout=-1):
        Gtk.Window.__init__(self)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.set_name('NotificationPopup')
        self.set_skip_taskbar_hint(True)
        self.set_decorated(False)
        self.set_size_request(312, 95)

        self._timeout_id = None
        self.account = account
        self.jid = jid
        self.msg_type = msg_type

        self._ui = get_builder('popup_notification_window.ui')
        self.add(self._ui.eventbox)

        if not text:
            text = app.get_name_from_jid(account, jid)  # default value of text
        if not title:
            title = ''

        self._ui.event_type_label.set_markup(
            '<span foreground="black" weight="bold">%s</span>' %
            GLib.markup_escape_text(title))

        css = '#NotificationPopup {background-color: black }'
        gtkgui_helpers.add_css_to_widget(self, css)

        if event_type == _('Contact Signed In'):
            bg_color = app.config.get('notif_signin_color')
        elif event_type == _('Contact Signed Out'):
            bg_color = app.config.get('notif_signout_color')
        elif event_type in (_('New Message'), _('New Single Message'),
                            _('New Private Message'), _('New E-mail')):
            bg_color = app.config.get('notif_message_color')
        elif event_type == _('File Transfer Request'):
            bg_color = app.config.get('notif_ftrequest_color')
        elif event_type == _('File Transfer Error'):
            bg_color = app.config.get('notif_fterror_color')
        elif event_type in (_('File Transfer Completed'),
                            _('File Transfer Stopped')):
            bg_color = app.config.get('notif_ftcomplete_color')
        elif event_type == _('Groupchat Invitation'):
            bg_color = app.config.get('notif_invite_color')
        elif event_type == _('Contact Changed Status'):
            bg_color = app.config.get('notif_status_color')
        else: # Unknown event! Shouldn't happen but deal with it
            bg_color = app.config.get('notif_other_color')

        background_class = '''
            .popup-style {
                border-image: none;
                background-image: none;
                background-color: %s }''' % bg_color

        gtkgui_helpers.add_css_to_widget(self._ui.eventbox, background_class)
        self._ui.eventbox.get_style_context().add_class('popup-style')

        gtkgui_helpers.add_css_to_widget(
            self._ui.close_button, background_class)
        self._ui.close_button.get_style_context().add_class('popup-style')

        escaped_text = GLib.markup_escape_text(text)
        self._ui.event_description_label.set_markup(
            '<span foreground="black">%s</span>' % escaped_text)

        # set the image
        self._ui.image.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)

        self.move(*self._get_window_pos())

        self._ui.connect_signals(self)
        self.connect('button-press-event', self._on_button_press)
        self.connect('destroy', self._on_destroy)
        self.show_all()
        if timeout > 0:
            self._timeout_id = GLib.timeout_add_seconds(timeout, self.destroy)

    def _get_window_pos(self):
        pos_x = app.config.get('notification_position_x')
        screen_w, screen_h = get_total_screen_geometry()
        if pos_x < 0:
            pos_x = screen_w - 312 + pos_x + 1
        pos_y = app.config.get('notification_position_y')
        if pos_y < 0:
            pos_y = screen_h - 95 - 80 + pos_y + 1
        return pos_x, pos_y

    def _on_close_button_clicked(self, _widget):
        self.destroy()

    def _on_button_press(self, _widget, event):
        if event.button == 1:
            app.interface.handle_event(self.account, self.jid, self.msg_type)
        self.destroy()

    def _on_destroy(self, *args):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
