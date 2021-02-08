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
from enum import IntEnum

from gi.repository import Gtk

from nbxmpp.modules import dataforms

from gajim.common import app
from gajim.common.i18n import _

from .dataform import DataFormWidget
from .dataform import FakeDataFormWidget

log = logging.getLogger('gajim.gui.registration')


class Page(IntEnum):
    REQUEST = 0
    FORM = 1
    SENDING = 2
    SUCCESS = 3
    ERROR = 4


class ServiceRegistration(Gtk.Assistant):
    def __init__(self, account, agent):
        Gtk.Assistant.__init__(self)

        self._con = app.connections[account]
        self._agent = agent
        self._account = account
        self._data_form_widget = None
        self._is_form = None

        self.set_application(app.app)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.set_default_size(600, 400)
        self.get_style_context().add_class('dialog-margin')

        self._add_page(RequestPage())
        self._add_page(FormPage())
        self._add_page(SendingPage())
        self._add_page(SuccessfulPage())
        self._add_page(ErrorPage())

        self.connect('prepare', self._on_page_change)
        self.connect('cancel', self._on_cancel)
        self.connect('close', self._on_cancel)

        self._remove_sidebar()
        self.show_all()

    def _add_page(self, page):
        self.append_page(page)
        self.set_page_type(page, page.type_)
        self.set_page_title(page, page.title)
        self.set_page_complete(page, page.complete)

    def _remove_sidebar(self):
        main_box = self.get_children()[0]
        sidebar = main_box.get_children()[0]
        main_box.remove(sidebar)

    def _build_dataform(self, form, is_form):
        if not is_form:
            return FakeDataFormWidget(form)

        dataform = dataforms.extend_form(node=form)

        form_widget = DataFormWidget(dataform)
        form_widget.connect('is-valid', self._on_is_valid)
        form_widget.validate()
        return form_widget

    def _on_page_change(self, _assistant, _page):
        if self.get_current_page() == Page.REQUEST:
            self._con.get_module('Register').get_register_form(
                self._agent, self._on_get_success, self._on_error)
        elif self.get_current_page() == Page.SENDING:
            self._register()
            self.commit()

    def _on_get_success(self, form, is_form):
        log.info('Show Form page')
        self._is_form = is_form
        self._data_form_widget = self._build_dataform(form, is_form)
        self.get_nth_page(Page.FORM).set_form(self._data_form_widget)
        self.set_current_page(Page.FORM)

    def _on_is_valid(self, _widget, is_valid):
        self.set_page_complete(self.get_nth_page(Page.FORM), is_valid)

    def _on_error(self, error_text, form=None, is_form=False):
        if form is not None:
            log.info('Show Form page')
            self._is_form = is_form
            self._data_form_widget = self._build_dataform(form, is_form)
            self.get_nth_page(Page.FORM).set_form(self._data_form_widget,
                                                  error_text=error_text)
            self.set_current_page(Page.FORM)
        else:
            log.info('Show Error page')
            self.get_nth_page(Page.ERROR).set_text(error_text)
            self.set_current_page(Page.ERROR)

    def _on_cancel(self, _widget):
        self.destroy()

    def _register(self):
        log.info('Show Sending page')
        form = self._data_form_widget.get_submit_form()
        self._con.get_module('Register').register_agent(
            self._agent,
            form,
            self._is_form,
            self._on_register_success,
            self._on_error)

    def _on_register_success(self):
        log.info('Show Success page')
        self.set_current_page(Page.SUCCESS)


class RequestPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.INTRO
    title = _('Register')
    complete = False

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        spinner = Gtk.Spinner()
        self.pack_start(spinner, True, True, 0)
        spinner.start()


class SendingPage(RequestPage):

    type_ = Gtk.AssistantPageType.PROGRESS
    title = _('Register')
    complete = False


class FormPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.INTRO
    title = _('Register')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._form = None
        self._label = Gtk.Label()
        self._label.set_no_show_all(True)
        self._label.get_style_context().add_class('error-color')
        self.pack_end(self._label, False, False, 0)

    def set_form(self, form, error_text=None):
        if self._form is not None:
            self.remove(self._form)
            self._form.destroy()
            self._label.hide()
        self._form = form

        if error_text is not None:
            self._label.set_text(error_text)
            self._label.show()

        self.pack_start(form, True, True, 0)
        self._form.show_all()


class SuccessfulPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.SUMMARY
    title = _('Registration successful')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)

        icon = Gtk.Image.new_from_icon_name('object-select-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('success-color')
        icon.set_valign(Gtk.Align.END)
        label = Gtk.Label(label=_('Registration successful'))
        label.get_style_context().add_class('bold16')
        label.set_valign(Gtk.Align.START)

        self.add(icon)
        self.add(label)


class ErrorPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.SUMMARY
    title = _('Registration failed')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)

        icon = Gtk.Image.new_from_icon_name('dialog-error-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('error-color')
        icon.set_valign(Gtk.Align.END)
        self._label = Gtk.Label()
        self._label.get_style_context().add_class('bold16')
        self._label.set_valign(Gtk.Align.START)

        self.add(icon)
        self.add(self._label)

    def set_text(self, text):
        self._label.set_text(text)
