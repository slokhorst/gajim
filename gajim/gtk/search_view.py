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
from typing import Union
from typing import Optional

import datetime
import logging
import time
import re

from gi.repository import GObject
from gi.repository import Gtk
import cairo

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import FILE_CATEGORIES
from gajim.common.i18n import _
from gajim.common.storage.archive import SearchLogRow

from .conversation.message_widget import MessageWidget
from .builder import get_builder

log = logging.getLogger('gajim.gui.search_view')


class SearchView(Gtk.Box):
    __gsignals__ = {
        'hide-search': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            ()),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        self.set_size_request(300, -1)

        self._account: Optional[str] = None
        self._jid: Optional[JID] = None
        self._results: list[SearchLogRow] = []
        self._scope: str = 'everywhere'

        self._ui = get_builder('search_view.ui')
        self._ui.results_listbox.set_header_func(self._header_func)
        self.add(self._ui.search_box)

        self._ui.connect_signals(self)

        app.ged.register_event_handler('account-enabled',
                                       ged.GUI1,
                                       self._on_account_state)
        app.ged.register_event_handler('account-disabled',
                                       ged.GUI1,
                                       self._on_account_state)
        self.show_all()

    def _on_account_state(self, _event: Any) -> None:
        self.clear()

    @staticmethod
    def _header_func(row: Union[CounterRow, ResultRow],
                     before: Optional[Union[CounterRow, ResultRow]]) -> None:

        if before is None:
            if isinstance(row, CounterRow):
                row.set_header(None)
            else:
                row.set_header(RowHeader(row.account, row.jid, row.time))
        else:
            if isinstance(row, CounterRow):
                row.set_header(None)
                return
            date1 = time.strftime('%x', time.localtime(row.time))
            date2 = time.strftime('%x', time.localtime(before.time))
            if before.jid != row.jid:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            elif date1 != date2:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            else:
                row.set_header(None)

    def _on_hide_clicked(self, _button: Gtk.Button) -> None:
        self.emit('hide-search')

    def clear(self) -> None:
        self._ui.search_entry.set_text('')
        self._clear_results()

    def _clear_results(self) -> None:
        for row in self._ui.results_listbox.get_children():
            self._ui.results_listbox.remove(row)
            row.destroy()

    def _on_search(self, entry: Gtk.Entry) -> None:
        self._clear_results()
        self._ui.date_hint.hide()
        text = entry.get_text()
        if not text:
            return

        # from:user
        # This works only for MUC, because contact_name is not
        # available for single contacts in logs.db.
        text, from_filters = self._strip_filters(text, 'from')

        # before:date
        text, before_filters = self._strip_filters(text, 'before')
        if before_filters is not None:
            try:
                before_filters = min([datetime.datetime.fromisoformat(date) for
                                      date in before_filters])
            except ValueError:
                self._ui.date_hint.show()
                return

        # after:date
        text, after_filters = self._strip_filters(text, 'after')
        if after_filters is not None:
            try:
                after_filters = min([datetime.datetime.fromisoformat(date) for
                                     date in after_filters])
                # if only the day is specified, we want to look after the
                # end of that day.
                # if precision is increased,we do want to look during the
                # day as well.
                if after_filters.hour == after_filters.minute == 0:
                    after_filters += datetime.timedelta(days=1)
            except ValueError:
                self._ui.date_hint.show()
                return

        # has:'file'|'img'|'video'|filetype
        text, has_filters = self._strip_filters(text, 'has')

        everywhere = self._ui.search_checkbutton.get_active()
        context = self._account is not None and self._jid is not None

        if not context or everywhere:
            self._scope = 'everywhere'
            self._results = app.storage.archive.search_all_logs(
                text,
                from_users=from_filters,
                before=before_filters,
                after=after_filters)
        else:
            self._scope = 'contact'
            self._results = app.storage.archive.search_log(
                self._account,
                self._jid,
                text,
                from_users=from_filters,
                before=before_filters,
                after=after_filters)

        if has_filters is not None:
            filetypes: list[str] = []
            for filetype in has_filters:
                types = FILE_CATEGORIES.get(filetype)
                if types is None:
                    filetypes.append(filetype)
                else:
                    for type_ in types:
                        filetypes.append(type_)
            self._filter_results_for_files(filetypes)

        self._add_counter()
        self._add_results()

    def _filter_results_for_files(self, filetypes: list[str]) -> None:
        if 'file' in filetypes:
            results: list[SearchLogRow] = []
            for result in self._results:
                if result.additional_data.get_value('gajim', 'oob_url'):
                    results.append(result)
            self._results = results
        else:
            results: list[SearchLogRow] = []
            for result in self._results:
                url = result.additional_data.get_value('gajim', 'oob_url')
                if url is None:
                    continue
                extension = str(url).rsplit('.', maxsplit=1)[-1]
                if extension in filetypes:
                    results.append(result)
            self._results = results

    @staticmethod
    def _strip_filters(text: str,
                       filter_name: str) -> tuple[str, Optional[list[str]]]:
        filters: list[str] = []
        start = 0
        new_text = ''
        for search_filter in re.finditer(filter_name + r':(\S+)\s?', text):
            end, new_start = search_filter.span()
            new_text += text[start:end]
            filters.append(search_filter.group(1))
            start = new_start
        new_text += text[start:]
        return new_text, filters or None

    def _add_counter(self) -> None:
        results_count = len(self._results)
        if results_count:
            self._ui.results_listbox.add(CounterRow(results_count))

    def _add_results(self) -> None:
        accounts = self._get_accounts()
        for msg in self._results[:25]:
            if self._scope == 'everywhere':
                archive_jid = app.storage.archive.get_jid_from_id(msg.jid_id)
                result_row = ResultRow(
                    msg,
                    accounts[msg.account_id],
                    archive_jid.jid)
            else:
                assert self._account is not None
                assert self._jid is not None
                result_row = ResultRow(msg, self._account, self._jid)

            self._ui.results_listbox.add(result_row)
        self._results = self._results[25:]

    def _on_edge_reached(self,
                         _scrolledwin: Gtk.ScrolledWindow,
                         pos: Gtk.PositionType) -> None:
        if pos != Gtk.PositionType.BOTTOM:
            return

        self._add_results()

    @staticmethod
    def _get_accounts() -> dict[int, str]:
        accounts: dict[int, str] = {}
        for account in app.settings.get_accounts():
            account_id = app.storage.archive.get_account_id(account)
            accounts[account_id] = account
        return accounts

    @staticmethod
    def _on_row_activated(_listbox: SearchView, row: ResultRow) -> None:
        control = app.window.get_active_control()
        if control is not None:
            if control.contact.jid == row.jid:
                control.scroll_to_message(row.log_line_id, row.timestamp)
                return

        # Wrong chat or no control opened
        # TODO: type 'pm' is KindConstant.CHAT_MSG_RECV, too
        jid = JID.from_string(row.jid)
        app.window.add_chat(row.account, jid, row.type, select=True)
        control = app.window.get_active_control()
        if control is not None:
            control.scroll_to_message(row.log_line_id, row.timestamp)

    def set_focus(self) -> None:
        self._ui.search_entry.grab_focus()

    def set_context(self, account: Optional[str], jid: Optional[JID]) -> None:
        self._account = account
        self._jid = jid
        self._ui.search_checkbutton.set_active(jid is None)


class RowHeader(Gtk.Box):
    def __init__(self, account: str, jid: JID, timestamp: float) -> None:
        Gtk.Box.__init__(self)
        self.set_hexpand(True)

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.header_box)

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        self._ui.header_name_label.set_text(contact.name or '')

        local_time = time.localtime(timestamp)
        date = time.strftime('%x', local_time)
        self._ui.header_date_label.set_text(date)

        self.show_all()


class CounterRow(Gtk.ListBoxRow):
    def __init__(self, count: int) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.set_activatable(False)
        self.type = 'counter'
        self.jid = ''  # Has to be there for header_func
        self.time = 0.0
        self.get_style_context().add_class('search-view-counter')

        if count == 1:
            counter_text = _('1 result')
        else:
            counter_text = _('%s results') % count
        label = Gtk.Label(label=counter_text)
        self.add(label)
        self.show_all()


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, msg: Any, account: str, jid: JID) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.account = account
        self.jid = jid
        self.time = msg.time
        self._client = app.get_client(account)

        self.log_line_id = msg.log_line_id
        self.timestamp = msg.time
        self.kind = msg.kind

        self.type = 'contact'
        if msg.kind == KindConstant.GC_MSG:
            self.type = 'groupchat'

        self.contact = self._client.get_module('Contacts').get_contact(
            jid, groupchat=self.type == 'groupchat')

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.result_row_grid)

        kind = 'status'
        contact_name = msg.contact_name
        if msg.kind in (
                KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
            kind = 'incoming'
            contact_name = self.contact.name
        elif msg.kind == KindConstant.GC_MSG:
            kind = 'incoming'
        elif msg.kind in (
                KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
            kind = 'outgoing'
            contact_name = app.nicks[account]
        self._ui.row_name_label.set_text(contact_name)

        avatar = self._get_avatar(kind, contact_name)
        self._ui.row_avatar.set_from_surface(avatar)

        local_time = time.localtime(msg.time)
        date = time.strftime('%H:%M', local_time)
        self._ui.row_time_label.set_label(date)

        message_widget = MessageWidget(account, selectable=False)
        message_widget.add_with_styling(msg.message, nickname=contact_name)
        self._ui.result_row_grid.attach(message_widget, 1, 1, 2, 1)

        self.show_all()

    def _get_avatar(self,
                    kind: str,
                    name: str) -> Optional[cairo.ImageSurface]:

        scale = self.get_scale_factor()
        if self.contact.is_groupchat:
            contact = self.contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self.contact

        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
