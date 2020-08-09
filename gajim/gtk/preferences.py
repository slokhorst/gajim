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

import logging
import os
import sys

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

try:
    from gi.repository import Gst
except Exception:
    pass

from gajim.common import app
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common import idle
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.i18n import ngettext
from gajim.common.helpers import open_file
from gajim.common.multimedia_helpers import AudioInputManager
from gajim.common.multimedia_helpers import AudioOutputManager
from gajim.common.multimedia_helpers import VideoInputManager

from gajim.chat_control_base import ChatControlBase

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_available_iconsets
from gajim.gtk.util import open_window
from gajim.gtk.sounds import ManageSounds
from gajim.gtk.const import ControlType
from gajim.gtk import gstreamer

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

log = logging.getLogger('gajim.gtk.preferences')


class Preferences(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Preferences'))

        self._ui = get_builder('preferences_window.ui')
        self.add(self._ui.preferences_window)

        ### General tab ###
        ## Behavior of Windows and Tabs
        # Set default for single window type
        self._ui.one_window_type_combobox.set_active_id(
            app.config.get('one_message_window'))

        # Show roster on startup
        self._ui.show_roster_on_startup.set_active_id(
            app.config.get('show_roster_on_startup'))

        # Quit on roster x
        st = app.config.get('quit_on_roster_x_button')
        self._ui.quit_on_roster_x_checkbutton.set_active(st)

        # Tab placement
        st = app.config.get('tabs_position')
        if st == 'top':
            self._ui.tabs_placement.set_active(0)
        elif st == 'bottom':
            self._ui.tabs_placement.set_active(1)
        elif st == 'left':
            self._ui.tabs_placement.set_active(2)
        else: # right
            self._ui.tabs_placement.set_active(3)

        ## Contact List Appearance
        # Merge accounts
        st = app.config.get('mergeaccounts')
        self._ui.merge_accounts_checkbutton.set_active(st)

        # Display avatars in roster
        st = app.config.get('show_avatars_in_roster')
        self._ui.show_avatars_in_roster_checkbutton.set_active(st)

        # Display status msg under contact name in roster
        st = app.config.get('show_status_msgs_in_roster')
        self._ui.show_status_msgs_in_roster_checkbutton.set_active(st)

        # Display PEP in roster
        st1 = app.config.get('show_mood_in_roster')
        st2 = app.config.get('show_activity_in_roster')
        st3 = app.config.get('show_tunes_in_roster')
        st4 = app.config.get('show_location_in_roster')
        if st1 == st2 == st3 == st4:
            self._ui.show_pep_in_roster_checkbutton.set_active(st1)
        else:
            self._ui.show_pep_in_roster_checkbutton.set_inconsistent(True)

        # Sort contacts by show
        st = app.config.get('sort_by_show_in_roster')
        self._ui.sort_by_show_in_roster_checkbutton.set_active(st)
        st = app.config.get('sort_by_show_in_muc')
        self._ui.sort_by_show_in_muc_checkbutton.set_active(st)

        ### Chat tab ###
        ## General Settings

        # Enable auto copy
        st = app.config.get('auto_copy')
        self._ui.auto_copy.set_active(st)

        ## Chat Settings
        # Use speller
        if app.is_installed('GSPELL'):
            st = app.config.get('use_speller')
            self._ui.speller_checkbutton.set_active(st)
        else:
            self._ui.speller_checkbutton.set_sensitive(False)

        # XEP-0184 positive ack
        st = app.config.get('positive_184_ack')
        self._ui.positive_184_ack_checkbutton.set_active(st)

        # Ignore XHTML
        st = app.config.get('show_xhtml')
        self._ui.xhtml_checkbutton.set_active(st)

        # Print status messages in single chats
        st = app.config.get('print_status_in_chats')
        self._ui.print_status_in_chats_checkbutton.set_active(st)

        # Show subject on join
        st = app.config.get('show_subject_on_join')
        self._ui.subject_on_join_checkbutton.set_active(st)

        # Group chat settings
        threshold_model = self._ui.sync_threshold_combobox.get_model()
        options = app.config.get('threshold_options').split(',')
        days = [int(option.strip()) for option in options]
        for day in days:
            if day == 0:
                label = _('No threshold')
            else:
                label = ngettext('%i day', '%i days', day, day, day)
            threshold_model.append([str(day), label])
        public_threshold = app.config.get('public_room_sync_threshold')
        self._ui.sync_threshold_combobox.set_id_column(0)
        self._ui.sync_threshold_combobox.set_active_id(str(public_threshold))

        st = app.config.get('print_join_left_default')
        self._ui.join_leave_checkbutton.set_active(st)

        st = app.config.get('print_status_muc_default')
        self._ui.status_change_checkbutton.set_active(st)

        # Displayed chat state notifications
        st = app.config.get('show_chatstate_in_tabs')
        self._ui.show_chatstate_in_tabs.set_active(st)

        st = app.config.get('show_chatstate_in_roster')
        self._ui.show_chatstate_in_roster.set_active(st)

        st = app.config.get('show_chatstate_in_banner')
        self._ui.show_chatstate_in_banner.set_active(st)

        ### Notifications tab ###
        ## Visual Notifications
        # Systray icon
        if app.config.get('trayicon') == 'never':
            self._ui.systray_combobox.set_active(0)
        elif app.config.get('trayicon') == 'on_event':
            self._ui.systray_combobox.set_active(1)
        else: # always
            self._ui.systray_combobox.set_active(2)

        # Notify on new event
        if app.config.get('autopopup'):
            self._ui.on_event_received_combobox.set_active(0)
        elif app.config.get('notify_on_new_message'):
            self._ui.on_event_received_combobox.set_active(1)
        else: # only show in roster
            self._ui.on_event_received_combobox.set_active(2)

        # Notify on online statuses
        st = app.config.get('notify_on_signin')
        self._ui.notify_on_signin_checkbutton.set_active(st)

        # Notify on offline statuses
        st = app.config.get('notify_on_signout')
        self._ui.notify_on_signout_checkbutton.set_active(st)

        # Auto popup when away
        st = app.config.get('autopopupaway')
        self._ui.auto_popup_away_checkbutton.set_active(st)

        # Auto popup when chat already open
        st = app.config.get('autopopup_chat_opened')
        self._ui.auto_popup_chat_opened_checkbutton.set_active(st)

        ## Sounds
        # Sounds
        if app.config.get('sounds_on'):
            self._ui.play_sounds_checkbutton.set_active(True)
        else:
            self._ui.manage_sounds_button.set_sensitive(False)

        # Allow sounds when dnd
        st = app.config.get('sounddnd')
        self._ui.sound_dnd_checkbutton.set_active(st)

        #### Status tab ###
        # Auto away
        st = app.config.get('autoaway')
        self._ui.auto_away_checkbutton.set_active(st)

        # Auto away time
        st = app.config.get('autoawaytime')
        self._ui.auto_away_time_spinbutton.set_value(st)
        self._ui.auto_away_time_spinbutton.set_sensitive(app.config.get('autoaway'))

        # Auto away message
        st = app.config.get('autoaway_message')
        self._ui.auto_away_message_entry.set_text(st)
        self._ui.auto_away_message_entry.set_sensitive(app.config.get('autoaway'))

        # Auto xa
        st = app.config.get('autoxa')
        self._ui.auto_xa_checkbutton.set_active(st)

        # Auto xa time
        st = app.config.get('autoxatime')
        self._ui.auto_xa_time_spinbutton.set_value(st)
        self._ui.auto_xa_time_spinbutton.set_sensitive(app.config.get('autoxa'))

        # Auto xa message
        st = app.config.get('autoxa_message')
        self._ui.auto_xa_message_entry.set_text(st)
        self._ui.auto_xa_message_entry.set_sensitive(app.config.get('autoxa'))

        if not idle.Monitor.is_available():
            self._ui.autoaway_table.set_sensitive(False)

        # Restore last status
        st = self.get_per_account_option('restore_last_status')
        if st == 'mixed':
            self._ui.restore_last_status_checkbutton.set_inconsistent(True)
        else:
            self._ui.restore_last_status_checkbutton.set_active(st)

        # Ask for status when online/offline
        st = app.config.get('ask_online_status')
        self._ui.prompt_online_status_message_checkbutton.set_active(st)
        st = app.config.get('ask_offline_status')
        self._ui.prompt_offline_status_message_checkbutton.set_active(st)

        # Status messages
        renderer = Gtk.CellRendererText()
        renderer.connect('edited', self.on_msg_cell_edited)
        renderer.set_property('editable', True)
        col = Gtk.TreeViewColumn('name', renderer, text=0)
        self._ui.msg_treeview.append_column(col)
        self.fill_msg_treeview()

        buf = self._ui.msg_textview.get_buffer()
        buf.connect('end-user-action', self.on_msg_textview_changed)

        ### Style tab ###
        # Themes
        self.changed_id = self._ui.theme_combobox.connect(
            'changed', self.on_theme_combobox_changed)
        self.update_theme_list()

        # Dark theme
        self._ui.dark_theme_combobox.set_active_id(str(app.config.get('dark_theme')))

        # Emoticons
        emoticon_themes = helpers.get_available_emoticon_themes()

        for theme in emoticon_themes:
            self._ui.emoticons_combobox.append_text(theme)

        config_theme = app.config.get('emoticons_theme')
        if config_theme not in emoticon_themes:
            config_theme = 'font'
        self._ui.emoticons_combobox.set_id_column(0)
        self._ui.emoticons_combobox.set_active_id(config_theme)

        self._ui.ascii_emoticons.set_active(app.config.get('ascii_emoticons'))

        # Iconset
        model = Gtk.ListStore(str, str)
        renderer_image = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property('xpad', 5)
        self._ui.iconset_combobox.pack_start(renderer_image, False)
        self._ui.iconset_combobox.pack_start(renderer_text, True)
        self._ui.iconset_combobox.add_attribute(renderer_text, 'text', 1)
        self._ui.iconset_combobox.add_attribute(renderer_image, 'icon_name', 0)
        self._ui.iconset_combobox.set_model(model)

        for index, iconset_name in enumerate(get_available_iconsets()):
            icon_name = get_icon_name('online', iconset=iconset_name)
            model.append([icon_name, iconset_name])
            if app.config.get('iconset') == iconset_name:
                self._ui.iconset_combobox.set_active(index)

        # Use transports iconsets
        st = app.config.get('use_transports_iconsets')
        self._ui.transports_iconsets_checkbutton.set_active(st)

        ### Audio/Video tab ###
        def create_av_combobox(opt_name, device_dict, config_name=None,
                               # This key is there to give the first index to autovideosrc and co.
                               key=lambda x: '' if x[1].startswith('auto') else x[0].lower()):
            combobox = self._ui.get_object(opt_name + '_combobox')
            cell = Gtk.CellRendererText()
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)
            cell.set_property('ellipsize-set', True)
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)
            model = Gtk.ListStore(str, str)
            combobox.set_model(model)
            if config_name:
                config = app.config.get(config_name)
            else:
                config = app.config.get(opt_name + '_device')

            for index, (name, value) in enumerate(sorted(device_dict.items(),
                                                         key=key)):
                model.append((name, value))
                if config == value:
                    combobox.set_active(index)

        if os.name == 'nt':
            self._ui.av_dependencies_label.set_text(
                _('Feature not available under Windows'))
        else:
            self._ui.av_dependencies_label.set_text(
                _('Missing dependencies for Audio/Video'))

        if app.is_installed('AV'):
            self._ui.av_dependencies_infobar.set_no_show_all(True)
            self._ui.av_dependencies_infobar.hide()

            create_av_combobox(
                'audio_input', AudioInputManager().get_devices())
            create_av_combobox(
                'audio_output', AudioOutputManager().get_devices())
            create_av_combobox(
                'video_input', VideoInputManager().get_devices())

            create_av_combobox(
                'video_framerate',
                {_('Default'): '',
                 '15fps': '15/1',
                 '10fps': '10/1',
                 '5fps': '5/1',
                 '2.5fps': '5/2'},
                'video_framerate',
                key=lambda x: -1 if not x[1] else float(x[0][:-3]))
            create_av_combobox(
                'video_size',
                {_('Default'): '',
                 '800x600': '800x600',
                 '640x480': '640x480',
                 '320x240': '320x240'},
                'video_size',
                key=lambda x: -1 if not x[1] else int(x[0][:3]))
            st = app.config.get('video_see_self')
            self._ui.video_see_self_checkbutton.set_active(st)

            self.av_pipeline = None
            self.av_src = None
            self.av_sink = None
            self.av_widget = None
        else:
            for opt_name in ('audio_input', 'audio_output', 'video_input',
                             'video_framerate', 'video_size'):
                combobox = self._ui.get_object(opt_name + '_combobox')
                combobox.set_sensitive(False)
            self._ui.live_preview_checkbutton.set_sensitive(False)

        # STUN
        st = app.config.get('use_stun_server')
        self._ui.stun_checkbutton.set_active(st)
        self._ui.stun_server_entry.set_sensitive(st)
        self._ui.stun_server_entry.set_text(app.config.get('stun_server'))

        ### Advanced tab ###

        ## Miscellaneous
        # Proxy
        self.update_proxy_list()

        # Log status changes of contacts
        st = app.config.get('log_contact_status_changes')
        self._ui.log_show_changes_checkbutton.set_active(st)

        st = app.config.get('use_keyring')
        self._ui.use_keyring_checkbutton.set_active(st)

        self._ui.enable_logging.set_active(app.get_debug_mode())
        self._ui.enable_logging.show()

        if sys.platform in ('win32', 'darwin'):
            st = app.config.get('check_for_update')
            self._ui.update_check.set_active(st)
            self._ui.update_check.show()

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)

        self._ui.msg_treeview.get_model().connect('row-changed',
                                self.on_msg_treemodel_row_changed)
        self._ui.msg_treeview.get_model().connect('row-deleted',
                                self.on_msg_treemodel_row_deleted)

        self.sounds_preferences = None
        self.theme_preferences = None

        self.show_all()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_per_account_option(self, opt):
        """
        Return the value of the option opt if it's the same in all accounts else
        returns "mixed"
        """
        if not app.connections:
            # A non existent key return default value
            return app.config.get_per('accounts', '__default__', opt)
        val = None
        for account in app.connections:
            v = app.config.get_per('accounts', account, opt)
            if val is None:
                val = v
            elif val != v:
                return 'mixed'
        return val

    def on_checkbutton_toggled(self, widget, config_name,
                               change_sensitivity_widgets=None):
        app.config.set(config_name, widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def on_per_account_checkbutton_toggled(self, widget, config_name,
                                           change_sensitivity_widgets=None):
        for account in app.connections:
            app.config.set_per('accounts', account, config_name,
                    widget.get_active())
        if change_sensitivity_widgets:
            for w in change_sensitivity_widgets:
                w.set_sensitive(widget.get_active())

    def _get_all_controls(self):
        for ctrl in app.interface.msg_win_mgr.get_controls():
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    def _get_all_muc_controls(self):
        for ctrl in app.interface.msg_win_mgr.get_controls(
                ControlType.GROUPCHAT):
            yield ctrl
        for account in app.connections:
            for ctrl in app.interface.minimized_controls[account].values():
                yield ctrl

    ### General tab ###
    def on_one_window_type_combo_changed(self, combobox):
        app.config.set('one_message_window', combobox.get_active_id())
        app.interface.msg_win_mgr.reconfig()

    def on_show_roster_on_startup_changed(self, combobox):
        app.config.set('show_roster_on_startup', combobox.get_active_id())

    def on_quit_on_roster_x_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'quit_on_roster_x_button')

    def on_tab_placement_changed(self, widget):
        active = widget.get_active()
        if active == 0: # top
            app.config.set('tabs_position', 'top')
        elif active == 1: # bottom
            app.config.set('tabs_position', 'bottom')
        elif active == 2: # left
            app.config.set('tabs_position', 'left')
        else: # right
            app.config.set('tabs_position', 'right')

    def on_merge_accounts_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'mergeaccounts')
        app.app.activate_action('merge')

    def on_show_avatars_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_avatars_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_show_status_msgs_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_status_msgs_in_roster')
        app.interface.roster.setup_and_draw_roster()
        for ctrl in self._get_all_muc_controls():
            ctrl.roster.draw_contacts()

    def on_show_pep_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_mood_in_roster')
        self.on_checkbutton_toggled(widget, 'show_activity_in_roster')
        self.on_checkbutton_toggled(widget, 'show_tunes_in_roster')
        self.on_checkbutton_toggled(widget, 'show_location_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_sort_by_show_in_roster_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_roster')
        app.interface.roster.setup_and_draw_roster()

    def on_sort_by_show_in_muc_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sort_by_show_in_muc')
        # Redraw groupchats
        for ctrl in self._get_all_muc_controls():
            ctrl.roster.invalidate_sort()

    ### Chat tab ###
    def on_auto_copy_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'auto_copy')

    def on_speller_checkbutton_toggled(self, widget):
        active = widget.get_active()
        app.config.set('use_speller', active)
        if not active:
            return
        lang = app.config.get('speller_language')
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        app.config.set('speller_language', gspell_lang.get_code())
        self.apply_speller()

    def apply_speller(self):
        for ctrl in self._get_all_controls():
            if isinstance(ctrl, ChatControlBase):
                ctrl.set_speller()

    def on_positive_184_ack_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'positive_184_ack')

    def on_xhtml_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_xhtml')

    def on_print_status_in_chats_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'print_status_in_chats')

    def on_subject_on_join_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_subject_on_join')

    def _on_sync_threshold_changed(self, widget):
        active = widget.get_active_id()
        app.config.set('public_room_sync_threshold', int(active))

    def _on_join_leave_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'print_join_left_default')
        for control in self._get_all_muc_controls():
            control.update_actions()

    def _on_status_change_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'print_status_muc_default')
        for control in self._get_all_muc_controls():
            control.update_actions()

    def on_show_chatstate_in_tabs_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_tabs')

    def on_show_chatstate_in_roster_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_roster')

    def on_show_chatstate_in_banner_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'show_chatstate_in_banner')

    ### Notifications tab ###
    def on_systray_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.config.set('trayicon', 'never')
            app.interface.hide_systray()
        elif active == 1:
            app.config.set('trayicon', 'on_event')
            app.interface.show_systray()
        else:
            app.config.set('trayicon', 'always')
            app.interface.show_systray()

    def on_event_received_combobox_changed(self, widget):
        active = widget.get_active()
        if active == 0:
            app.config.set('autopopup', True)
            app.config.set('notify_on_new_message', False)
        elif active == 1:
            app.config.set('autopopup', False)
            app.config.set('notify_on_new_message', True)
        else:
            app.config.set('autopopup', False)
            app.config.set('notify_on_new_message', False)

    def on_notify_on_signin_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signin')

    def on_notify_on_signout_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'notify_on_signout')

    def on_auto_popup_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autopopupaway')

    def on_auto_popup_chat_opened_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autopopup_chat_opened')

    def on_play_sounds_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounds_on',
                [self._ui.manage_sounds_button])

    def on_manage_sounds_button_clicked(self, widget):
        if self.sounds_preferences is None:
            self.sounds_preferences = ManageSounds()
        else:
            self.sounds_preferences.window.present()

    def on_sound_dnd_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'sounddnd')

    ### Status tab ###
    def on_auto_away_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoaway',
                                [self._ui.auto_away_time_spinbutton,
                                 self._ui.auto_away_message_entry])

    def on_auto_away_time_spinbutton_value_changed(self, widget):
        aat = widget.get_value_as_int()
        app.config.set('autoawaytime', aat)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_away_message_entry_changed(self, widget):
        app.config.set('autoaway_message', widget.get_text())

    def on_auto_xa_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'autoxa',
                                [self._ui.auto_xa_time_spinbutton,
                                 self._ui.auto_xa_message_entry])

    def on_auto_xa_time_spinbutton_value_changed(self, widget):
        axt = widget.get_value_as_int()
        app.config.set('autoxatime', axt)
        idle.Monitor.set_interval(app.config.get('autoawaytime') * 60,
                                  app.config.get('autoxatime') * 60)

    def on_auto_xa_message_entry_changed(self, widget):
        app.config.set('autoxa_message', widget.get_text())

    def on_restore_last_status_checkbutton_toggled(self, widget):
        widget.set_inconsistent(False)
        self.on_per_account_checkbutton_toggled(widget, 'restore_last_status')

    def on_prompt_online_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_online_status')

    def on_prompt_offline_status_message_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'ask_offline_status')

    def save_status_messages(self, model):
        for msg in app.config.get_per('statusmsg'):
            app.config.del_per('statusmsg', msg)
        iter_ = model.get_iter_first()
        while iter_:
            val = model[iter_][0]
            if model[iter_][1]: # We have a preset message
                if not val: # No title, use message text for title
                    val = model[iter_][1]
                app.config.add_per('statusmsg', val)
                msg = helpers.to_one_line(model[iter_][1])
                app.config.set_per('statusmsg', val, 'message', msg)
                i = 2
                # Store mood / activity
                for subname in ('activity', 'subactivity', 'activity_text',
                'mood', 'mood_text'):
                    val2 = model[iter_][i]
                    if not val2:
                        val2 = ''
                    app.config.set_per('statusmsg', val, subname, val2)
                    i += 1
            iter_ = model.iter_next(iter_)

    def on_msg_treemodel_row_changed(self, model, path, iter_):
        self.save_status_messages(model)

    def on_msg_treemodel_row_deleted(self, model, path):
        self.save_status_messages(model)

    def fill_msg_treeview(self):
        self._ui.delete_msg_button.set_sensitive(False)
        model = self._ui.msg_treeview.get_model()
        model.clear()
        preset_status = []
        for msg_name in app.config.get_per('statusmsg'):
            if msg_name.startswith('_last_'):
                continue
            preset_status.append(msg_name)
        preset_status.sort()
        for msg_name in preset_status:
            msg_text = app.config.get_per('statusmsg', msg_name, 'message')
            msg_text = helpers.from_one_line(msg_text)
            activity = app.config.get_per('statusmsg', msg_name, 'activity')
            subactivity = app.config.get_per('statusmsg', msg_name,
                'subactivity')
            activity_text = app.config.get_per('statusmsg', msg_name,
                'activity_text')
            mood = app.config.get_per('statusmsg', msg_name, 'mood')
            mood_text = app.config.get_per('statusmsg', msg_name, 'mood_text')
            iter_ = model.append()
            model.set(iter_, 0, msg_name, 1, msg_text, 2, activity, 3,
                subactivity, 4, activity_text, 5, mood, 6, mood_text)

    def on_msg_cell_edited(self, cell, row, new_text):
        model = self._ui.msg_treeview.get_model()
        iter_ = model.get_iter_from_string(row)
        model.set_value(iter_, 0, new_text)

    def on_msg_treeview_cursor_changed(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        self._ui.delete_msg_button.set_sensitive(True)
        buf = self._ui.msg_textview.get_buffer()
        msg = model[iter_][1]
        buf.set_text(msg)

    def on_new_msg_button_clicked(self, widget, data=None):
        model = self._ui.msg_treeview.get_model()
        iter_ = model.append()
        model.set(
            iter_, 0, _('status message title'), 1,
            _('status message text'))
        self._ui.msg_treeview.set_cursor(model.get_path(iter_))

    def on_delete_msg_button_clicked(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self._ui.msg_textview.get_buffer()
        model.remove(iter_)
        buf.set_text('')
        self._ui.delete_msg_button.set_sensitive(False)

    def on_msg_textview_changed(self, widget, data=None):
        sel = self._ui.msg_treeview.get_selection()
        if not sel:
            return
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        buf = self._ui.msg_textview.get_buffer()
        first_iter, end_iter = buf.get_bounds()
        model.set_value(iter_, 1, buf.get_text(first_iter, end_iter, True))

    def on_msg_treeview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.on_delete_msg_button_clicked(widget)

    ### Style ###
    @staticmethod
    def on_theme_combobox_changed(combobox):
        theme = combobox.get_active_id()
        app.config.set('roster_theme', theme)
        app.css_config.change_theme(theme)
        app.nec.push_incoming_event(NetworkEvent('theme-update'))

        # Begin repainting themed widgets throughout
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)

    def update_theme_list(self):
        with self._ui.theme_combobox.handler_block(self.changed_id):
            self._ui.theme_combobox.remove_all()
            self._ui.theme_combobox.append('default', 'default')
            for config_theme in app.css_config.themes:
                self._ui.theme_combobox.append(config_theme, config_theme)

        self._ui.theme_combobox.set_active_id(app.config.get('roster_theme'))

    def on_manage_theme_button_clicked(self, widget):
        open_window('Themes', transient=self)

    def on_dark_theme_changed(self, widget):
        app.css_config.set_dark_theme(int(widget.get_active_id()))

    def on_emoticons_combobox_changed(self, widget):
        active = widget.get_active()
        model = widget.get_model()
        emot_theme = model[active][0]
        app.config.set('emoticons_theme', emot_theme)
        from gajim.gtk.emoji_chooser import emoji_chooser
        emoji_chooser.load()
        self.toggle_emoticons()

    def on_convert_ascii_toggle(self, widget):
        app.config.set('ascii_emoticons', widget.get_active())
        app.interface.make_regexps()

    def toggle_emoticons(self):
        """
        Update emoticons state in Opened Chat Windows
        """
        for ctrl in self._get_all_controls():
            ctrl.toggle_emoticons()

    def on_iconset_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        icon_string = model[active][1]
        app.config.set('iconset', icon_string)
        app.interface.roster.update_icons()

    def on_transports_iconsets_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_transports_iconsets')

    ### Audio/Video tab ###
    def _on_features_button_clicked(self, _button):
        open_window('Features')

    def on_av_combobox_changed(self, combobox, config_name):
        model = combobox.get_model()
        active = combobox.get_active()
        device = model[active][1]
        app.config.set(config_name, device)
        return device

    def on_audio_input_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_input_device')

    def on_audio_output_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'audio_output_device')

    def on_video_input_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        device = model[active][1]

        try:
            src = Gst.parse_bin_from_description(device, True)
        except GLib.Error:
            # TODO: disable the entry instead of just selecting the default.
            log.error('Failed to parse "%s" as Gstreamer element,'
                      ' falling back to autovideosrc', device)
            widget.set_active(0)
            return

        if self._ui.live_preview_checkbutton.get_active():
            self.av_pipeline.set_state(Gst.State.NULL)
            if self.av_src is not None:
                self.av_pipeline.remove(self.av_src)
            self.av_pipeline.add(src)
            src.link(self.av_sink)
            self.av_src = src
            self.av_pipeline.set_state(Gst.State.PLAYING)
        app.config.set('video_input_device', device)

    def _on_live_preview_toggled(self, widget):
        if widget.get_active():
            sink, widget, name = gstreamer.create_gtk_widget()
            if sink is None:
                log.error('Failed to obtain a working Gstreamer GTK+ sink, '
                          'video support will be disabled')
                self._ui.video_input_combobox.set_sensitive(False)
                self._ui.selected_video_output.set_markup(
                    _('<span color="red" font-weight="bold">'
                      'Unavailable</span>, video support will be disabled'))
                return

            text = ''
            if name == 'gtkglsink':
                text = _('<span color="green" font-weight="bold">'
                         'OpenGL</span> accelerated')
            elif name == 'gtksink':
                text = _('<span color="yellow" font-weight="bold">'
                         'Unaccelerated</span>')
            self._ui.selected_video_output.set_markup(text)
            if self.av_pipeline is None:
                self.av_pipeline = Gst.Pipeline.new('preferences-pipeline')
            else:
                self.av_pipeline.set_state(Gst.State.NULL)
            self.av_pipeline.add(sink)
            self.av_sink = sink

            if self.av_widget is not None:
                self._ui.av_preview_box.remove(self.av_widget)
            self._ui.av_preview_placeholder.set_visible(False)
            self._ui.av_preview_box.add(widget)
            self.av_widget = widget

            src_name = app.config.get('video_input_device')
            try:
                self.av_src = Gst.parse_bin_from_description(src_name, True)
            except GLib.Error:
                log.error('Failed to parse "%s" as Gstreamer element, '
                          'falling back to autovideosrc', src_name)
                self.av_src = None
            if self.av_src is not None:
                self.av_pipeline.add(self.av_src)
                self.av_src.link(self.av_sink)
                self.av_pipeline.set_state(Gst.State.PLAYING)
            else:
                # Parsing the pipeline stored in video_input_device failed,
                # let’s try the default one.
                self.av_src = Gst.ElementFactory.make('autovideosrc', None)
                if self.av_src is None:
                    log.error('Failed to obtain a working Gstreamer source, '
                              'video will be disabled.')
                    self._ui.video_input_combobox.set_sensitive(False)
                    return
                # Great, this succeeded, let’s store it back into the
                # config and use it. We’ve made autovideosrc the first
                # element in the combobox so we can pick index 0 without
                # worry.
                self._ui.video_input_combobox.set_active(0)
        else:
            if self.av_pipeline is not None:
                self.av_pipeline.set_state(Gst.State.NULL)
            if self.av_src is not None:
                self.av_pipeline.remove(self.av_src)
                self.av_src = None
            if self.av_sink is not None:
                self.av_pipeline.remove(self.av_sink)
                self.av_sink = None
            if self.av_widget is not None:
                self._ui.av_preview_box.remove(self.av_widget)
                self._ui.av_preview_placeholder.set_visible(True)
                self.av_widget = None
            self.av_pipeline = None

    def on_video_framerate_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_framerate')

    def on_video_size_combobox_changed(self, widget):
        self.on_av_combobox_changed(widget, 'video_size')

    def on_video_see_self_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'video_see_self')

    def on_stun_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_stun_server', [
            self._ui.stun_server_entry])

    def stun_server_entry_changed(self, widget):
        app.config.set('stun_server', widget.get_text())

    ### Advanced tab ###
    # Proxies
    def on_proxies_combobox_changed(self, widget):
        active = widget.get_active()
        if active == -1:
            return
        proxy = widget.get_model()[active][0]
        if proxy == _('No Proxy'):
            proxy = ''
        app.config.set('global_proxy', proxy)

    def on_manage_proxies_button_clicked(self, _widget):
        app.app.activate_action('manage-proxies')

    def update_proxy_list(self):
        our_proxy = app.config.get('global_proxy')
        if not our_proxy:
            our_proxy = _('No Proxy')
        model = self._ui.proxies_combobox.get_model()
        model.clear()
        proxies = app.config.get_per('proxies')
        proxies.insert(0, _('No Proxy'))
        for index, proxy in enumerate(proxies):
            model.append([proxy])
            if our_proxy == proxy:
                self._ui.proxies_combobox.set_active(index)
        if not our_proxy in proxies:
            self._ui.proxies_combobox.set_active(0)

    # Log status changes of contacts
    def on_log_show_changes_checkbutton_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'log_contact_status_changes')

    # Use system’s keyring
    def _on_use_keyring_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'use_keyring')

    # Enable debug logging
    def on_enable_logging_toggled(self, widget):
        app.set_debug_mode(widget.get_active())

    def _on_debug_folder_clicked(self, _widget):
        open_file(configpaths.get('DEBUG'))

    def _on_update_check_toggled(self, widget):
        self.on_checkbutton_toggled(widget, 'check_for_update')

    def _on_reset_help_clicked(self, widget):
        widget.set_sensitive(False)
        helping_hints = [
            'start_chat',
        ]
        for hint in helping_hints:
            app.config.set('show_help_%s' % hint, True)

    def on_open_advanced_editor_button_clicked(self, _widget):
        open_window('AdvancedConfig')
