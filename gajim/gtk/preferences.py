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

from __future__ import annotations
from typing import Any
from typing import Optional
from typing import cast

import logging
import sys

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common.const import THRESHOLD_OPTIONS
from gajim.common.i18n import _
from gajim.common.helpers import open_file
from gajim.common.multimedia_helpers import AudioInputManager
from gajim.common.multimedia_helpers import AudioOutputManager
from gajim.common.multimedia_helpers import VideoInputManager
from gajim.common.events import StyleChanged
from gajim.common.events import ThemeUpdate

from .const import Setting
from .const import SettingKind
from .const import SettingType
from .emoji_chooser import emoji_chooser
from .settings import SettingsBox
from .settings import SettingsDialog
from .sidebar_switcher import SideBarSwitcher
from .video_preview import VideoPreview
from .util import open_window
from .util import get_app_window
from .builder import get_builder

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

log = logging.getLogger('gajim.gui.preferences')


class Preferences(Gtk.ApplicationWindow):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('PreferencesWindow')
        self.set_default_size(900, 650)
        self.set_resizable(True)
        self.set_title(_('Preferences'))

        self._ui = get_builder('preferences.ui')

        self._video_preview: Optional[VideoPreview] = None
        self._prefs = {}

        side_bar_switcher = SideBarSwitcher()
        side_bar_switcher.set_stack(self._ui.stack)
        self._ui.grid.attach(side_bar_switcher, 0, 0, 1, 1)

        self.add(self._ui.grid)

        self._check_emoji_theme()

        prefs = [
            ('window_behaviour', WindowBehaviour),
            ('chats', Chats),
            ('group_chats', GroupChats),
            ('file_preview', FilePreview),
            ('visual_notifications', VisualNotifications),
            ('sounds', Sounds),
            ('status_message', StatusMessage),
            ('automatic_status', AutomaticStatus),
            ('themes', Themes),
            ('emoji', Emoji),
            ('server', Server),
            ('audio', Audio),
            ('video', Video),
            ('miscellaneous', Miscellaneous),
            ('advanced', Advanced),
        ]

        self._add_prefs(prefs)
        self._add_video_preview()

        self._ui.audio_video_info_bar.set_revealed(not app.is_installed('AV'))

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)

        self.show_all()
        if sys.platform not in ('win32', 'darwin'):
            self._ui.emoji.hide()

    def get_ui(self):
        return self._ui

    def _add_prefs(self, prefs):
        for ui_name, klass in prefs:
            pref_box = getattr(self._ui, ui_name)
            if ui_name == 'video' and sys.platform == 'win32':
                continue

            pref = klass(self)
            pref_box.add(pref)
            self._prefs[ui_name] = pref

    def _add_video_preview(self) -> None:
        if sys.platform == 'win32':
            return
        self._video_preview = VideoPreview()
        self._ui.video.add(self._video_preview.widget)

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def get_video_preview(self) -> Optional[VideoPreview]:
        return self._video_preview

    @staticmethod
    def _on_features_clicked(_widget: Gtk.InfoBar,
                             _response: Gtk.ResponseType
                             ) -> None:
        open_window('Features')

    def update_theme_list(self) -> None:
        self._prefs['themes'].update_theme_list()

    def update_proxy_list(self) -> None:
        self._prefs['miscellaneous'].update_proxy_list()

    @staticmethod
    def _check_emoji_theme() -> None:
        # Ensure selected emoji theme is valid
        emoji_themes = helpers.get_available_emoticon_themes()
        settings_theme = app.settings.get('emoticons_theme')
        if settings_theme not in emoji_themes:
            app.settings.set('emoticons_theme', 'font')

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._prefs.clear()
        app.check_finalize(self)


class PreferenceBox(SettingsBox):
    def __init__(self, settings: list[Setting]) -> None:
        SettingsBox.__init__(self, None)
        self.get_style_context().add_class('settings-border')
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_vexpand(False)
        self.set_valign(Gtk.Align.END)

        for setting in settings:
            self.add_setting(setting)
        self.update_states()


class WindowBehaviour(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        main_window_on_startup_items = {
            'always': _('Always'),
            'never': _('Never'),
            'last_state': _('Restore last state'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Show Gajim on Startup'),
                    SettingType.CONFIG,
                    'show_main_window_on_startup',
                    props={'entries': main_window_on_startup_items},
                    desc=_('Show window when starting Gajim')),

            Setting(SettingKind.SWITCH,
                    _('Quit Gajim on Close'),
                    SettingType.CONFIG,
                    'quit_on_main_window_x_button',
                    desc=_('Quit when closing Gajim’s window')),
        ]

        PreferenceBox.__init__(self, settings)


class Chats(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        speller_desc = None
        if not app.is_installed('GSPELL'):
            speller_desc = _('Needs gspell to be installed')

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Spell Checking'),
                    SettingType.CONFIG,
                    'use_speller',
                    desc=speller_desc,
                    enabled_func=self._speller_available,
                    callback=self._on_use_speller),

            Setting(SettingKind.SWITCH,
                    _('Message Receipts (✔)'),
                    SettingType.CONFIG,
                    'positive_184_ack',
                    desc=_('Add a checkmark to received messages')),

            Setting(SettingKind.SWITCH,
                    _('XHTML Formatting'),
                    SettingType.CONFIG,
                    'show_xhtml',
                    desc=_('Render XHTML styles (colors, etc.) of incoming '
                           'messages')),

            Setting(SettingKind.SWITCH,
                    _('Show Send Message Button'),
                    SettingType.CONFIG,
                    'show_send_message_button'),

            Setting(SettingKind.SWITCH,
                    _('Show Status Changes'),
                    SettingType.CONFIG,
                    'print_status_in_chats',
                    desc=_('For example: "Julia is now online"')),

            Setting(SettingKind.SWITCH,
                    _('Show Chat State In Banner'),
                    SettingType.CONFIG,
                    'show_chatstate_in_banner',
                    desc=_('Show the contact’s chat state (e.g. typing) in '
                           'the chats tab’s banner')),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _speller_available() -> bool:
        return app.is_installed('GSPELL')

    @staticmethod
    def _on_use_speller(value: bool, *args: Any) -> None:
        if not value:
            return

        lang = app.settings.get('speller_language')
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        app.settings.set('speller_language', gspell_lang.get_code())
        for ctrl in app.window.get_controls():
            ctrl.set_speller()


class GroupChats(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Default Sync Threshold'),
                    SettingType.CONFIG,
                    'gc_sync_threshold_public_default',
                    desc=_('Default for new public group chats'),
                    props={'entries': THRESHOLD_OPTIONS}),

            Setting(SettingKind.SWITCH,
                    _('Direct Messages'),
                    SettingType.CONFIG,
                    'muc_prefer_direct_msg',
                    desc=_('Prefer direct messages in private group chats ')),

            Setting(SettingKind.SWITCH,
                    _('Sort Participant List by Status'),
                    SettingType.CONFIG,
                    'sort_by_show_in_muc',
                    callback=self._on_sort_by_show_in_muc),

            Setting(SettingKind.SWITCH,
                    _('Status Messages in Participants List'),
                    SettingType.CONFIG,
                    'show_status_msgs_in_roster',
                    callback=self._on_show_status_in_roster),

            Setting(SettingKind.SWITCH,
                    _('Show Subject'),
                    SettingType.CONFIG,
                    'show_subject_on_join'),

            Setting(SettingKind.SWITCH,
                    _('Show Joined / Left'),
                    SettingType.CONFIG,
                    'gc_print_join_left_default',
                    desc=_('Default for new group chats'),
                    props={'button-text': _('Reset'),
                           'button-tooltip': _('Reset all group chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_join_left}),

            Setting(SettingKind.SWITCH,
                    _('Show Status Changes'),
                    SettingType.CONFIG,
                    'gc_print_status_default',
                    desc=_('Default for new group chats'),
                    props={'button-text': _('Reset'),
                           'button-tooltip': _('Reset all group chats to the '
                                               'current default value'),
                           'button-style': 'destructive-action',
                           'button-callback': self._reset_print_status}),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_sort_by_show_in_muc(_value: bool, *args: Any) -> None:
        for ctrl in app.window.get_controls():
            if ctrl.is_groupchat:
                ctrl.roster.invalidate_sort()

    @staticmethod
    def _on_show_status_in_roster(_value: bool, *args: Any) -> None:
        for ctrl in app.window.get_controls():
            if ctrl.is_groupchat:
                ctrl.roster.draw_contacts()

    @staticmethod
    def _reset_join_left(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings('print_join_left', None)

    @staticmethod
    def _reset_print_status(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings('print_status', None)


class FilePreview(PreferenceBox):
    def __init__(self, *args: Any) -> None:
        sizes = {
            262144: '256 KiB',
            524288: '512 KiB',
            1048576: '1 MiB',
            5242880: '5 MiB',
            10485760: '10 MiB',
        }

        actions = {
            'open': _('Open'),
            'save_as': _('Save As…'),
            'open_folder': _('Open Folder'),
            'copy_link_location': _('Copy Link Location'),
            'open_link_in_browser': _('Open Link in Browser'),
        }

        settings = [
            Setting(SettingKind.SPIN,
                    _('Preview Size'),
                    SettingType.CONFIG,
                    'preview_size',
                    desc=_('Size of preview image'),
                    props={'range_': (100, 1000)}),

            Setting(SettingKind.POPOVER,
                    _('Allowed File Size'),
                    SettingType.CONFIG,
                    'preview_max_file_size',
                    desc=_('Maximum file size for preview generation'),
                    props={'entries': sizes}),

            Setting(SettingKind.SWITCH,
                    _('Preview in Public Group Chats'),
                    SettingType.CONFIG,
                    'preview_anonymous_muc',
                    desc=_('Generate preview automatically in public '
                           'group chats (may disclose your data)')),

            Setting(SettingKind.SWITCH,
                    _('Preview all Image URLs'),
                    SettingType.CONFIG,
                    'preview_allow_all_images',
                    desc=_('Generate preview for any URLs containing images '
                           '(may be unsafe)')),

            Setting(SettingKind.POPOVER,
                    _('Left Click Action'),
                    SettingType.CONFIG,
                    'preview_leftclick_action',
                    desc=_('Action when left-clicking a preview'),
                    props={'entries': actions}),

            Setting(SettingKind.SWITCH,
                    _('HTTPS Verification'),
                    SettingType.CONFIG,
                    'preview_verify_https',
                    desc=_('Whether to check for a valid certificate')),
        ]

        PreferenceBox.__init__(self, settings)


class VisualNotifications(PreferenceBox):
    def __init__(self, *args: Any) -> None:
        trayicon_items = {
            'never': _('Hide icon'),
            'on_event': _('Only show for pending events'),
            'always': _('Always show icon'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Notification Area Icon'),
                    SettingType.CONFIG,
                    'trayicon',
                    props={'entries': trayicon_items},
                    callback=self._on_trayicon),

            Setting(SettingKind.NOTIFICATIONS,
                    _('Show Notifications'),
                    SettingType.DIALOG,
                    props={'dialog': NotificationsDialog}),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _on_trayicon(value: str, *args: Any) -> None:
        if value == 'never':
            app.interface.hide_systray()
        elif value == 'on_event':
            app.interface.show_systray()
        else:
            app.interface.show_systray()


class NotificationsDialog(SettingsDialog):
    def __init__(self, account: str, parent: Preferences) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Show Notifications'),
                    SettingType.CONFIG,
                    'show_notifications'),

            Setting(SettingKind.SWITCH,
                    _('Notifications When Away'),
                    SettingType.CONFIG,
                    'show_notifications_away',
                    desc=_('Show notifications even if you are Away, '
                           'Busy, etc.'),
                    bind='show_notifications'),
        ]

        SettingsDialog.__init__(self, parent, _('Notifications'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Sounds(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Play Sounds'),
                    SettingType.CONFIG,
                    'sounds_on',
                    desc=_('Play sounds to notify about events'),
                    props={'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_manage_sounds}),

            Setting(SettingKind.SWITCH,
                    _('Sounds When Away'),
                    SettingType.CONFIG,
                    'sounddnd',
                    desc=_('Play sounds even when you are Away, Busy, etc.'),
                    bind='sounds_on'),
        ]

        PreferenceBox.__init__(self, settings)

    def _on_manage_sounds(self, _button: Gtk.Button) -> None:
        open_window('ManageSounds', transient_for=self.get_toplevel())


class StatusMessage(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Sign In'),
                    SettingType.CONFIG,
                    'ask_online_status'),

            Setting(SettingKind.SWITCH,
                    _('Sign Out'),
                    SettingType.CONFIG,
                    'ask_offline_status'),

            Setting(SettingKind.SWITCH,
                    _('Status Change'),
                    SettingType.CONFIG,
                    'always_ask_for_status_message'),
        ]

        PreferenceBox.__init__(self, settings)


class AutomaticStatus(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [
            Setting(SettingKind.AUTO_AWAY,
                    _('Auto Away'),
                    SettingType.DIALOG,
                    desc=_('Change your status to \'Away\' after a certain '
                           'amount of time'),
                    props={'dialog': AutoAwayDialog}),

            Setting(SettingKind.AUTO_EXTENDED_AWAY,
                    _('Auto Not Available'),
                    SettingType.DIALOG,
                    desc=_('Change your status to \'Not Available\' after a '
                           'certain amount of time'),
                    props={'dialog': AutoExtendedAwayDialog}),

        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_auto_away() -> bool:
        return app.settings.get('autoaway')

    @staticmethod
    def _get_auto_xa() -> bool:
        return app.settings.get('autoxa')


class AutoAwayDialog(SettingsDialog):
    def __init__(self, account: str, parent: Preferences) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Auto Away'),
                    SettingType.CONFIG,
                    'autoaway'),

            Setting(SettingKind.SPIN,
                    _('Time Until Away'),
                    SettingType.CONFIG,
                    'autoawaytime',
                    desc=_('Minutes until your status gets changed'),
                    props={'range_': (1, 720)},
                    bind='autoaway'),

            Setting(SettingKind.ENTRY,
                    _('Status Message'),
                    SettingType.CONFIG,
                    'autoaway_message',
                    bind='autoaway'),
        ]

        SettingsDialog.__init__(self, parent, _('Auto Away Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class AutoExtendedAwayDialog(SettingsDialog):
    def __init__(self, account: str, parent: Preferences) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Auto Not Available'),
                    SettingType.CONFIG,
                    'autoxa'),

            Setting(SettingKind.SPIN,
                    _('Time Until Not Available'),
                    SettingType.CONFIG,
                    'autoxatime',
                    desc=_('Minutes until your status gets changed'),
                    props={'range_': (1, 720)},
                    bind='autoxa'),

            Setting(SettingKind.ENTRY,
                    _('Status Message'),
                    SettingType.CONFIG,
                    'autoxa_message',
                    bind='autoxa'),
        ]

        SettingsDialog.__init__(self, parent, _('Auto Extended Away Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Themes(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        theme_items = self._get_theme_items()

        dark_theme_items = {
            0: _('Disabled'),
            1: _('Enabled'),
            2: _('System'),
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Dark Theme'),
                    SettingType.CONFIG,
                    'dark_theme',
                    props={'entries': dark_theme_items},
                    callback=self._on_dark_theme),

            Setting(SettingKind.POPOVER,
                    _('Theme'),
                    SettingType.CONFIG,
                    'roster_theme',
                    name='roster_theme',
                    props={'entries': theme_items,
                           'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_edit_themes},
                    callback=self._on_theme_changed),
        ]

        PreferenceBox.__init__(self, settings)

    @staticmethod
    def _get_theme_items() -> list[str]:
        theme_items = ['default']
        for settings_theme in app.css_config.themes:
            theme_items.append(settings_theme)
        return theme_items

    def update_theme_list(self) -> None:
        self.get_setting('roster_theme').update_entries(self._get_theme_items())

    def _on_edit_themes(self, _button: Gtk.Button) -> None:
        open_window('Themes', transient=self.get_toplevel())

    @staticmethod
    def _on_theme_changed(value: str, *args: Any) -> None:
        app.css_config.change_theme(value)
        app.ged.raise_event(ThemeUpdate())
        app.ged.raise_event(StyleChanged())

    @staticmethod
    def _on_dark_theme(value: str, *args: Any) -> None:
        app.css_config.set_dark_theme(int(value))
        app.ged.raise_event(StyleChanged())


class Emoji(PreferenceBox):
    def __init__(self, *args: Any) -> None:
        if sys.platform not in ('win32', 'darwin'):
            PreferenceBox.__init__(self, [])
            return

        emoji_themes_items: list[str] = []
        for theme in helpers.get_available_emoticon_themes():
            emoji_themes_items.append(theme)

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Emoji Theme'),
                    SettingType.CONFIG,
                    'emoticons_theme',
                    desc=_('Choose from various emoji styles'),
                    props={'entries': emoji_themes_items},
                    callback=self._on_emoticons_theme)
        ]

        PreferenceBox.__init__(self, settings)

    def _on_emoticons_theme(self, *args: Any) -> None:
        emoji_chooser.load()
        self._toggle_emoticons()

    @staticmethod
    def _toggle_emoticons() -> None:
        for ctrl in app.window.get_controls():
            ctrl.toggle_emoticons()


class Server(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        settings = [

            Setting(SettingKind.USE_STUN_SERVER,
                    _('Use STUN Server'),
                    SettingType.DIALOG,
                    desc=_('Helps to establish calls through firewalls'),
                    props={'dialog': StunServerDialog}),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(app.is_installed('AV'))


class StunServerDialog(SettingsDialog):
    def __init__(self, account: str, parent: Preferences) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Use STUN Server'),
                    SettingType.CONFIG,
                    'use_stun_server'),

            Setting(SettingKind.ENTRY,
                    _('STUN Server'),
                    SettingType.CONFIG,
                    'stun_server',
                    bind='use_stun_server')
        ]

        SettingsDialog.__init__(self, parent, _('STUN Server Settings'),
                                Gtk.DialogFlags.MODAL, settings, account)


class Audio(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        deps_installed = app.is_installed('AV')

        audio_input_devices = {}
        audio_output_devices = {}
        if deps_installed:
            audio_input_devices = AudioInputManager().get_devices()
            audio_output_devices = AudioOutputManager().get_devices()

        audio_input_items = self._create_av_combo_items(audio_input_devices)
        audio_output_items = self._create_av_combo_items(audio_output_devices)

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Audio Input Device'),
                    SettingType.CONFIG,
                    'audio_input_device',
                    desc=_('Select your audio input (e.g. microphone)'),
                    props={'entries': audio_input_items}),

            Setting(SettingKind.POPOVER,
                    _('Audio Output Device'),
                    SettingType.CONFIG,
                    'audio_output_device',
                    desc=_('Select an audio output (e.g. speakers, '
                           'headphones)'),
                    props={'entries': audio_output_items}),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(deps_installed)

    @staticmethod
    def _create_av_combo_items(items_dict: dict[str, str]) -> dict[str, str]:
        items = enumerate(sorted(
            items_dict.items(),
            key=lambda x: '' if x[1].startswith('auto') else x[0].lower()))
        combo_items: dict[str, str] = {}
        for _index, (name, value) in items:
            combo_items[value] = name
        return combo_items


class Video(PreferenceBox):
    def __init__(self, *args: Any) -> None:

        deps_installed = app.is_installed('AV')

        video_input_devices = {}
        if deps_installed:
            video_input_devices = VideoInputManager().get_devices()

        video_input_items = self._create_av_combo_items(video_input_devices)

        video_framerates = {
            '': _('Default'),
            '15/1': '15 fps',
            '10/1': '10 fps',
            '5/1': '5 fps',
            '5/2': '2.5 fps',
        }

        video_sizes = {
            '': _('Default'),
            '800x600': '800x600',
            '640x480': '640x480',
            '320x240': '320x240',
        }

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Video Input Device'),
                    SettingType.CONFIG,
                    'video_input_device',
                    props={'entries': video_input_items},
                    desc=_('Select your video input device (e.g. webcam, '
                           'screen capture)'),
                    callback=self._on_video_input_changed),

            Setting(SettingKind.POPOVER,
                    _('Video Framerate'),
                    SettingType.CONFIG,
                    'video_framerate',
                    props={'entries': video_framerates}),

            Setting(SettingKind.POPOVER,
                    _('Video Resolution'),
                    SettingType.CONFIG,
                    'video_size',
                    props={'entries': video_sizes}),

            Setting(SettingKind.SWITCH,
                    _('Show My Video Stream'),
                    SettingType.CONFIG,
                    'video_see_self',
                    desc=_('Show your own video stream in calls')),

            Setting(SettingKind.SWITCH,
                    _('Live Preview'),
                    SettingType.VALUE,
                    desc=_('Show a live preview to test your video source'),
                    callback=self._toggle_live_preview),
        ]

        PreferenceBox.__init__(self, settings)

        self.set_sensitive(deps_installed)

    @staticmethod
    def _on_video_input_changed(_value: str, *args: Any) -> None:
        pref_win = cast(Preferences, get_app_window('Preferences'))
        preview = pref_win.get_video_preview()
        if preview is None or not preview.is_active:
            # changed signal gets triggered when we fill the combobox
            return
        preview.refresh()

    @staticmethod
    def _toggle_live_preview(value: bool, *args: Any) -> None:
        pref_win = cast(Preferences, get_app_window('Preferences'))
        preview = pref_win.get_video_preview()
        preview.toggle_preview(value)

    @staticmethod
    def _create_av_combo_items(items_dict: dict[str, str]) -> dict[str, str]:
        items = enumerate(sorted(
            items_dict.items(),
            key=lambda x: '' if x[1].startswith('auto') else x[0].lower()))
        combo_items: dict[str, str] = {}
        for _index, (name, value) in items:
            combo_items[value] = name
        return combo_items


class Miscellaneous(PreferenceBox):
    def __init__(self, pref_window: Preferences) -> None:
        self._hints_list = [
            'start_chat',
        ]

        settings = [
            Setting(SettingKind.POPOVER,
                    _('Global Proxy'),
                    SettingType.CONFIG,
                    'global_proxy',
                    name='global_proxy',
                    props={'entries': self._get_proxies(),
                           'default-text': _('System'),
                           'button-icon-name': 'preferences-system-symbolic',
                           'button-callback': self._on_proxy_edit}),

            Setting(SettingKind.SWITCH,
                    _('Use System Keyring'),
                    SettingType.CONFIG,
                    'use_keyring',
                    desc=_('Use your system’s keyring to store passwords')),
        ]

        if sys.platform in ('win32', 'darwin'):
            settings.append(
                Setting(SettingKind.SWITCH,
                        _('Check For Updates'),
                        SettingType.CONFIG,
                        'check_for_update',
                        desc=_('Check for Gajim updates periodically')))

        PreferenceBox.__init__(self, settings)

        reset_button = pref_window.get_ui().reset_button
        reset_button.connect('clicked', self._on_reset_hints)
        reset_button.set_sensitive(self._check_hints_reset)

    @staticmethod
    def _get_proxies() -> dict[str, str]:
        return {proxy: proxy for proxy in app.settings.get_proxies()}

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        open_window('ManageProxies')

    def update_proxy_list(self) -> None:
        self.get_setting('global_proxy').update_entries(self._get_proxies())

    def _check_hints_reset(self) -> bool:
        for hint in self._hints_list:
            if app.settings.get(f'show_help_{hint}') is False:
                return True
        return False

    def _on_reset_hints(self, button: Gtk.Button) -> None:
        for hint in self._hints_list:
            app.settings.set(f'show_help_{hint}', True)
        button.set_sensitive(False)


class Advanced(PreferenceBox):
    def __init__(self, pref_window: Preferences) -> None:

        settings = [
            Setting(SettingKind.SWITCH,
                    _('Debug Logging'),
                    SettingType.VALUE,
                    app.get_debug_mode(),
                    props={'button-icon-name': 'folder-symbolic',
                           'button-callback': self._on_open_debug_logs},
                    callback=self._on_debug_logging),
        ]

        PreferenceBox.__init__(self, settings)

        pref_window.get_ui().ace_button.connect(
            'clicked', self._on_advanced_config_editor)

    @staticmethod
    def _on_debug_logging(value: bool, *args: Any) -> None:
        app.set_debug_mode(value)

    @staticmethod
    def _on_open_debug_logs(*args: Any) -> None:
        open_file(configpaths.get('DEBUG'))

    @staticmethod
    def _on_advanced_config_editor(*args: Any) -> None:
        open_window('AdvancedConfig')
