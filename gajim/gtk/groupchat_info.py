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

from gi.repository import Gdk
from gi.repository import Gtk

from nbxmpp.protocol import NS_MAM_1
from nbxmpp.protocol import NS_MAM_2

from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.helpers import open_uri
from gajim.common.const import RFC5646_LANGUAGE_TAGS

from gajim.gtk.util import get_builder


MUC_FEATURES = {
    'mam': (
        'feather-server-symbolic',
        Q_('?Group chat feature:Archiving'),
        _('Messages are archived on the server')),
    'muc_persistent': (
        'feather-hard-drive-symbolic',
        Q_('?Group chat feature:Persistent'),
        _('This group chat persists '
          'even if it\'s unoccupied')),
    'muc_temporary': (
        'feather-clock-symbolic',
        Q_('?Group chat feature:Temporary'),
        _('This group chat will be destroyed '
          'once the last occupant left')),
    'muc_moderated': (
        'feather-mic-off-symbolic',
        Q_('?Group chat feature:Moderated'),
        _('Participants entering this group chat need '
          'to request permission to send messages')),
    'muc_unmoderated': (
        'feather-mic-symbolic',
        Q_('?Group chat feature:Not Moderated'),
        _('Participants entering this group chat can '
          'write messages to all participants')),
    'muc_open': (
        'feather-globe-symbolic',
        Q_('?Group chat feature:Open'),
        _('Anyone can join this group chat')),
    'muc_membersonly': (
        'feather-user-check-symbolic',
        Q_('?Group chat feature:Members Only'),
        _('This group chat is restricted '
          'to members only')),
    'muc_public': (
        'feather-eye-symbolic',
        Q_('?Group chat feature:Public'),
        _('Group chat can be found via search')),
    'muc_hidden': (
        'feather-eye-off-symbolic',
        Q_('?Group chat feature:Hidden'),
        _('This group chat can not be found via search')),
    'muc_nonanonymous': (
        'feather-shield-off-symbolic',
        Q_('?Group chat feature:Not Anonymous'),
        _('All other group chat occupants '
          'can see your XMPP address')),
    'muc_semianonymous': (
        'feather-shield-symbolic',
        Q_('?Group chat feature:Semi-Anonymous'),
        _('Only moderators can see your XMPP address')),
    'muc_passwordprotected': (
        'feather-lock-symbolic',
        Q_('?Group chat feature:Password Required'),
        _('This group chat '
          'does require a password upon entry')),
    'muc_unsecured': (
        'feather-unlock-symbolic',
        Q_('?Group chat feature:No Password Required'),
        _('This group chat does not require '
          'a password upon entry')),
}


class GroupChatInfoScrolled(Gtk.ScrolledWindow):
    def __init__(self, account):
        Gtk.ScrolledWindow.__init__(self)
        self.set_size_request(400, -1)
        self.set_min_content_height(400)
        self.set_policy(Gtk.PolicyType.NEVER,
                        Gtk.PolicyType.AUTOMATIC)
        self._account = account
        self._ui = get_builder('groupchat_info_scrolled.ui')
        self.add(self._ui.info_grid)
        self._ui.connect_signals(self)
        self.show_all()

    def set_author(self, author, epoch_timestamp=None):
        if not author:
            return

        if epoch_timestamp is not None:
            time_ = time.strftime('%c', time.localtime(epoch_timestamp))
            author = '{} - {}'.format(author, time_)

        self._ui.author.set_text(author)
        self._ui.author.set_visible(True)
        self._ui.author_label.set_visible(True)

    def set_subject(self, subject):
        if not subject:
            return
        self._ui.subject.set_text(subject)
        self._ui.subject.set_visible(True)
        self._ui.subject_label.set_visible(True)

    def set_from_disco_info(self, info):
        # Set name
        has_name = bool(info.muc_name)
        self._ui.name.set_text(info.muc_name or '')
        self._ui.name.set_visible(has_name)
        self._ui.name_label.set_visible(has_name)

        # Set description
        has_desc = bool(info.muc_description)
        self._ui.description.set_text(info.muc_description or '')
        self._ui.description.set_visible(has_desc)
        self._ui.description_label.set_visible(has_desc)

        # Set subject
        has_subject = bool(info.muc_subject)
        self._ui.subject.set_text(info.muc_subject or '')
        self._ui.subject.set_visible(has_subject)
        self._ui.subject_label.set_visible(has_subject)

        # Set user
        has_users = info.muc_users is not None
        self._ui.users.set_text(info.muc_users or '')
        self._ui.users.set_visible(has_users)
        self._ui.users_image.set_visible(has_users)

        # Set address
        self._ui.address.set_text(str(info.jid))

        # Set contacts
        has_contacts = bool(info.muc_contacts)
        if has_contacts:
            for contact in info.muc_contacts:
                self._ui.contact_box.add(self._get_contact_button(contact))

        self._ui.contact_box.set_visible(has_contacts)
        self._ui.contact_label.set_visible(has_contacts)

        # Set discussion logs
        has_log_uri = bool(info.muc_log_uri)
        self._ui.logs.set_uri(info.muc_log_uri or '')
        self._ui.logs.set_label('Website')
        self._ui.logs.set_visible(has_log_uri)
        self._ui.logs_label.set_visible(has_log_uri)

        # Set room language
        has_lang = bool(info.muc_lang)
        lang = ''
        if has_lang:
            lang = RFC5646_LANGUAGE_TAGS.get(info.muc_lang, info.muc_lang)
        self._ui.lang.set_text(lang)
        self._ui.lang.set_visible(has_lang)
        self._ui.lang_image.set_visible(has_lang)

        self._add_features(info.features)

    def _add_features(self, features):
        grid = self._ui.info_grid
        features = list(features)

        has_mam = NS_MAM_2 in features or NS_MAM_1 in features
        if has_mam:
            features.append('mam')

        row = 10
        for feature in features:
            icon, name, tooltip = MUC_FEATURES.get(feature, (None, None, None))
            if icon is None:
                continue
            grid.attach(self._get_feature_icon(icon, tooltip), 0, row, 1, 1)
            grid.attach(self._get_feature_label(name), 1, row, 1, 1)
            row += 1
        grid.show_all()

    @staticmethod
    def _on_activate_log_link(button):
        open_uri(button.get_uri())
        return Gdk.EVENT_STOP

    def _on_activate_contact_link(self, button):
        open_uri('xmpp:%s?message' % button.get_uri(), account=self._account)
        return Gdk.EVENT_STOP

    @staticmethod
    def _get_feature_icon(icon, tooltip):
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_valign(Gtk.Align.CENTER)
        image.set_halign(Gtk.Align.END)
        image.set_tooltip_text(tooltip)
        return image

    @staticmethod
    def _get_feature_label(text):
        label = Gtk.Label(label=text, use_markup=True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        return label

    def _get_contact_button(self, contact):
        button = Gtk.LinkButton.new(contact)
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('link-button')
        button.connect('activate-link', self._on_activate_contact_link)
        button.show()
        return button