# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp @ hoerist.com>
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

from __future__ import annotations

import typing
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import cast

import gc
import os
import sys
import logging
import weakref
import pprint
from collections import defaultdict

import nbxmpp
from nbxmpp.idlequeue import IdleQueue
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

import gajim
from gajim.common import types
from gajim.common import config as c_config
from gajim.common import configpaths
from gajim.common import ged as ged_module
from gajim.common.i18n import LANG
from gajim.common.const import Display

if typing.TYPE_CHECKING:
    from gajim.gui.main import MainWindow
    from gajim.gui.application import GajimApplication
    from gajim.common.storage.cache import CacheStorage
    from gajim.common.storage.archive import MessageArchiveStorage
    from gajim.common.cert_store import CertificateStore


interface = cast(types.InterfaceT, None)
thread_interface = lambda *args: None # Interface to run a thread and then a callback
config = c_config.Config()
settings = cast(types.SettingsT, None)
version = gajim.__version__
connections: dict[str, types.Client] = {}
avatar_cache: dict[str, dict[str, Any]] = {}
bob_cache: dict[str, bytes] = {}
ipython_window = None
app = None # type: GajimApplication
window = None # type: MainWindow

ged = ged_module.GlobalEventsDispatcher() # Global Events Dispatcher
plugin_manager = None # Plugins Manager

class Storage:
    def __init__(self):
        self.cache: CacheStorage = None
        self.archive: MessageArchiveStorage = None

storage = Storage()

css_config = cast(types.CSSConfigT, None)

transport_type: dict[str, str] = {}

# dict of rooms that must be automatically configured
# and for which we have a list of invities
# {account: {room_jid: {'invities': []}}}
automatic_rooms: dict[str, dict[str, dict[str, list[str]]]] = {}

# list of contacts that has just signed in
newly_added: dict[str, list[str]] = {}

# list of contacts that has just signed out
to_be_removed: dict[str, list[str]] = {}

notification = None

# list of our nick names in each account
nicks: dict[str, str] = {}

# should we block 'contact signed in' notifications for this account?
# this is only for the first 30 seconds after we change our show
# to something else than offline
# can also contain account/transport_jid to block notifications for contacts
# from this transport
block_signed_in_notifications: dict[str, bool] = {}

proxy65_manager = None

cert_store = cast('CertificateStore', None)

task_manager = None

# zeroconf account name
ZEROCONF_ACC_NAME = 'Local'

# These will be set in app.gui_interface.
idlequeue = cast(IdleQueue, None)
socks5queue = None

gupnp_igd = None

gsound_ctx = None

_dependencies = {
    'AVAHI': False,
    'PYBONJOUR': False,
    'FARSTREAM': False,
    'GST': False,
    'AV': False,
    'GEOCLUE': False,
    'UPNP': False,
    'GSOUND': False,
    'GSPELL': False,
    'IDLE': False,
    'APPINDICATOR': False,
    'AYATANA_APPINDICATOR': False,
}

_tasks: dict[int, list[Any]] = defaultdict(list)


class RecentGroupchat(NamedTuple):
    room: str
    server: str
    nickname: str


def print_version() -> None:
    log('gajim').info('Gajim Version: %s', gajim.__version__)


def get_client(account: str) -> types.Client:
    return connections[account]


def is_installed(dependency: str) -> bool:
    if dependency == 'ZEROCONF':
        # Alias for checking zeroconf libs
        return _dependencies['AVAHI'] or _dependencies['PYBONJOUR']
    return _dependencies[dependency]


def is_flatpak() -> bool:
    return gajim.IS_FLATPAK


def is_portable() -> bool:
    return gajim.IS_PORTABLE


def is_display(display: Display) -> bool:
    # XWayland reports as Display X11, so try with env var
    is_wayland = os.environ.get('XDG_SESSION_TYPE') == 'wayland'
    if is_wayland and display == Display.WAYLAND:
        return True

    default = Gdk.Display.get_default()
    if default is None:
        log('gajim').warning('Could not determine window manager')
        return False
    return default.__class__.__name__ == display.value


def disable_dependency(dependency: str) -> None:
    _dependencies[dependency] = False


def detect_dependencies() -> None:
    import gi

    # ZEROCONF
    try:
        import pybonjour  # pylint: disable=unused-import
        _dependencies['PYBONJOUR'] = True
    except Exception:
        pass

    try:
        gi.require_version('Avahi', '0.6')
        from gi.repository import Avahi  # pylint: disable=unused-import
        _dependencies['AVAHI'] = True
    except Exception:
        pass

    try:
        gi.require_version('Gst', '1.0')
        gi.require_version('GstPbutils', '1.0')
        from gi.repository import Gst
        from gi.repository import GstPbutils  # pylint: disable=unused-import
        success, _argv = Gst.init_check(None)
        _dependencies['GST'] = success
    except Exception:
        pass

    try:
        gi.require_version('Farstream', '0.2')
        from gi.repository import Farstream
        _dependencies['FARSTREAM'] = True
    except Exception as error:
        log('gajim').warning('AV dependency test failed: %s', error)

    try:
        if _dependencies['GST'] and _dependencies['FARSTREAM']:
            conference = Gst.ElementFactory.make('fsrtpconference', None)
            conference.new_session(Farstream.MediaType.AUDIO)
            from gajim.gui.gstreamer import create_gtk_widget
            gtk_widget = create_gtk_widget()
            if gtk_widget is not None:
                _dependencies['AV'] = True
    except Exception as error:
        log('gajim').warning('AV dependency test failed: %s', error)

    # GEOCLUE
    try:
        gi.require_version('Geoclue', '2.0')
        from gi.repository import Geoclue  # pylint: disable=unused-import
        _dependencies['GEOCLUE'] = True
    except (ImportError, ValueError):
        pass

    # UPNP
    try:
        gi.require_version('GUPnPIgd', '1.0')
        from gi.repository import GUPnPIgd
        global gupnp_igd
        gupnp_igd = GUPnPIgd.SimpleIgd()
        _dependencies['UPNP'] = True
    except ValueError:
        pass

    # IDLE
    try:
        from gajim.common import idle
        if idle.Monitor.is_available():
            _dependencies['IDLE'] = True
    except Exception:
        pass

    # GSOUND
    try:
        gi.require_version('GSound', '1.0')
        from gi.repository import GSound
        global gsound_ctx
        gsound_ctx = GSound.Context()
        try:
            gsound_ctx.init()
            _dependencies['GSOUND'] = True
        except GLib.Error as error:
            log('gajim').warning('GSound init failed: %s', error)
    except (ImportError, ValueError):
        pass

    # GSPELL
    try:
        gi.require_version('Gspell', '1')
        from gi.repository import Gspell
        langs = Gspell.language_get_available()
        for lang in langs:
            log('gajim').info('%s (%s) dict available',
                              lang.get_name(), lang.get_code())
        if langs:
            _dependencies['GSPELL'] = True
    except (ImportError, ValueError):
        pass

    # APPINDICATOR
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3  # pylint: disable=unused-import
        _dependencies['APPINDICATOR'] = True
    except (ImportError, ValueError):
        pass
    # AYATANA APPINDICATOR
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3  # pylint: disable=unused-import
        _dependencies['AYATANA_APPINDICATOR'] = True
    except (ImportError, ValueError):
        pass

    # Print results
    for dep, val in _dependencies.items():
        log('gajim').info('%-13s %s', dep, val)

    log('gajim').info('Used language: %s', LANG)


def detect_desktop_env() -> Optional[str]:
    if sys.platform in ('win32', 'darwin'):
        return sys.platform

    desktop = os.environ.get('XDG_CURRENT_DESKTOP')
    if desktop is None:
        return None

    if 'gnome' in desktop.lower():
        return 'gnome'
    return desktop

desktop_env = detect_desktop_env()


def get_server_from_jid(jid: str) -> str:
    pos = jid.find('@') + 1 # after @
    return jid[pos:]


def get_room_and_nick_from_fjid(jid: str) -> list[str]:
    # fake jid is the jid for a contact in a room
    # gaim@conference.jabber.no/nick/nick-continued
    # return ('gaim@conference.jabber.no', 'nick/nick-continued')
    l = jid.split('/', 1)
    if len(l) == 1: # No nick
        l.append('')
    return l


def get_jid_without_resource(jid: str) -> str:
    return jid.split('/')[0]


def get_number_of_accounts() -> int:
    """
    Return the number of ALL accounts
    """
    return len(connections.keys())


def get_number_of_connected_accounts(
        accounts_list: Optional[list[str]] = None) -> int:
    """
    Returns the number of connected accounts. You can optionally pass an
    accounts_list and if you do those will be checked, else all will be checked
    """
    connected_accounts = 0
    if accounts_list is None:
        accounts = connections.keys()
    else:
        accounts = accounts_list
    for account in accounts:
        if account_is_connected(account):
            connected_accounts = connected_accounts + 1
    return connected_accounts


def get_available_clients() -> list[types.Client]:
    clients: list[types.Client] = []
    for client in connections.values():
        if client.state.is_available:
            clients.append(client)
    return clients


def get_connected_accounts(exclude_local: bool = False) -> list[str]:
    """
    Returns a list of CONNECTED accounts
    """
    account_list: list[str] = []
    for account in connections:
        if account == 'Local' and exclude_local:
            continue
        if account_is_connected(account):
            account_list.append(account)
    return account_list


def get_accounts_sorted() -> list[str]:
    '''
    Get all accounts alphabetically sorted with Local first
    '''
    account_list = settings.get_accounts()
    account_list.sort(key=str.lower)
    if 'Local' in account_list:
        account_list.remove('Local')
        account_list.insert(0, 'Local')
    return account_list


def get_enabled_accounts_with_labels(
        exclude_local: bool = True,
        connected_only: bool = False,
        private_storage_only: bool = False) -> list[list[str]]:
    """
    Returns a list with [account, account_label] entries.
    Order by account_label
    """
    accounts: list[list[str]] = []
    for acc in connections:
        if exclude_local and account_is_zeroconf(acc):
            continue
        if connected_only and not account_is_connected(acc):
            continue
        if private_storage_only and not account_supports_private_storage(acc):
            continue

        accounts.append([acc, get_account_label(acc)])

    accounts.sort(key=lambda xs: str.lower(xs[1]))
    return accounts


def get_account_label(account: str) -> str:
    return settings.get_account_setting(account, 'account_label') or account


def account_is_zeroconf(account: str) -> bool:
    return connections[account].is_zeroconf


def account_supports_private_storage(account: str) -> bool:
    # If Delimiter module is not available we can assume
    # Private Storage is not available
    return connections[account].get_module('Delimiter').available


def account_is_connected(account: str) -> bool:
    if account not in connections:
        return False
    return (connections[account].state.is_connected or
            connections[account].state.is_available)


def account_is_available(account: str) -> bool:
    if account not in connections:
        return False
    return connections[account].state.is_available


def account_is_disconnected(account: str) -> bool:
    return not account_is_connected(account)


def zeroconf_is_connected() -> bool:
    return account_is_connected(ZEROCONF_ACC_NAME) and \
            settings.get_account_setting(ZEROCONF_ACC_NAME, 'is_zeroconf')


def get_transport_name_from_jid(
        jid: str,
        use_config_setting: bool = True) -> Optional[str]:

    """
    Returns 'gg', 'irc' etc

    If JID is not from transport returns None.
    """
    # TODO: Rewrite/remove

    #FIXME: jid can be None! one TB I saw had this problem:
    # in the code block # it is a groupchat presence in handle_event_notify
    # jid was None. Yann why?
    if not jid:
        return

    host = get_server_from_jid(jid)
    if host in transport_type:
        return transport_type[host]

    # host is now f.e. icq.foo.org or just icq (sometimes on hacky transports)
    host_splitted = host.split('.')
    if host_splitted:
        # now we support both 'icq.' and 'icq' but not icqsucks.org
        host = host_splitted[0]

    if host in ('irc', 'icq', 'sms', 'weather', 'mrim', 'facebook'):
        return host
    if host == 'gg':
        return 'gadu-gadu'
    if host == 'jit':
        return 'icq'
    if host == 'facebook':
        return 'facebook'
    return None

def jid_is_transport(jid: str) -> bool:
    # if not '@' or '@' starts the jid then it is transport
    if jid.find('@') <= 0:
        return True
    return False


def get_jid_from_account(account_name: str) -> str:
    """
    Return the jid we use in the given account
    """
    name = settings.get_account_setting(account_name, 'name')
    hostname = settings.get_account_setting(account_name, 'hostname')
    jid = name + '@' + hostname
    return jid


def get_account_from_jid(jid: str) -> Optional[str]:
    for account in settings.get_accounts():
        if jid == get_jid_from_account(account):
            return account


def get_hostname_from_account(account_name: str, use_srv: bool = False) -> str:
    """
    Returns hostname (if custom hostname is used, that is returned)
    """
    if use_srv and connections[account_name].connected_hostname:
        return connections[account_name].connected_hostname
    if settings.get_account_setting(account_name, 'use_custom_host'):
        return settings.get_account_setting(account_name, 'custom_host')
    return settings.get_account_setting(account_name, 'hostname')


def get_notification_image_prefix(jid: str) -> str:
    """
    Returns the prefix for the notification images
    """
    transport_name = get_transport_name_from_jid(jid)
    if transport_name in ['icq', 'facebook']:
        prefix = transport_name
    else:
        prefix = 'jabber'
    return prefix


def get_recent_groupchats(account: str) -> list[RecentGroupchat]:
    recent_groupchats = settings.get_account_setting(
        account, 'recent_groupchats').split()

    recent_list: list[RecentGroupchat] = []
    for groupchat in recent_groupchats:
        jid = nbxmpp.JID.from_string(groupchat)
        recent = RecentGroupchat(jid.localpart, jid.domain, jid.resource)
        recent_list.append(recent)
    return recent_list


def add_recent_groupchat(account: str, room_jid: str, nickname: str) -> None:
    recent = settings.get_account_setting(
        account, 'recent_groupchats').split()
    full_jid = room_jid + '/' + nickname
    if full_jid in recent:
        recent.remove(full_jid)
    recent.insert(0, full_jid)
    if len(recent) > 10:
        recent = recent[0:9]
    config_value = ' '.join(recent)
    settings.set_account_setting(account, 'recent_groupchats', config_value)


def get_priority(account: str, show: str) -> int:
    """
    Return the priority an account must have
    """
    if not show:
        show = 'online'

    if show in ('online', 'chat', 'away', 'xa', 'dnd') and \
    settings.get_account_setting(account, 'adjust_priority_with_status'):
        prio = settings.get_account_setting(account, 'autopriority_' + show)
    else:
        prio = settings.get_account_setting(account, 'priority')
    if prio < -128:
        prio = -128
    elif prio > 127:
        prio = 127
    return prio


def log(domain: str) -> logging.Logger:
    if domain != 'gajim':
        domain = 'gajim.%s' % domain
    return logging.getLogger(domain)


def prefers_app_menu() -> bool:
    if sys.platform == 'darwin':
        return True
    if sys.platform == 'win32':
        return False
    return app.prefers_app_menu()


def load_css_config() -> None:
    global css_config
    from gajim.gui.css_config import CSSConfig
    css_config = CSSConfig()


def set_debug_mode(enable: bool) -> None:
    debug_folder = configpaths.get('DEBUG')
    debug_enabled = debug_folder / 'debug-enabled'
    if enable:
        debug_enabled.touch()
    else:
        if debug_enabled.exists():
            debug_enabled.unlink()


def get_debug_mode() -> bool:
    debug_folder = configpaths.get('DEBUG')
    debug_enabled = debug_folder / 'debug-enabled'
    return debug_enabled.exists()


def get_stored_bob_data(algo_hash: str) -> Optional[bytes]:
    try:
        return bob_cache[algo_hash]
    except KeyError:
        filepath = configpaths.get('BOB') / algo_hash
        if filepath.exists():
            with open(str(filepath), 'r+b') as file:
                data = file.read()
            return data
    return None


def register_task(self, task):
    _tasks[id(self)].append(task)


def remove_task(task, id_) -> None:
    try:
        _tasks[id_].remove(task)
    except Exception:
        pass
    else:
        if not _tasks[id_]:
            del _tasks[id_]


def cancel_tasks(obj: Any) -> None:
    id_ = id(obj)
    if id_ not in _tasks:
        return

    task_list = _tasks[id_]
    for task in task_list:
        task.cancel()


def check_finalize(obj: Any) -> None:
    if 'GAJIM_LEAK' not in os.environ:
        return

    name = obj.__class__.__name__
    logger = logging.getLogger('gajim.leak')
    finalizer = weakref.finalize(obj, logger.info, f'{name} has been finalized')

    g_objects: list[str] = []
    if isinstance(obj, GObject.Object):
        g_objects.append(name)

        def g_object_finalized():
            g_objects.remove(name)

        obj.weak_ref(g_object_finalized)

    def is_finalizer_ref(ref):
        try:
            return isinstance(ref[2][0], str)
        except Exception:
            return False

    def check_finalized():
        gc.collect()
        gc.collect()

        if g_objects:
            logger.warning('GObject not finalized: %s', name)

        tup = finalizer.peek()
        if tup is None:
            return

        logger.warning('%s not finalized', name)
        logger.warning('References:')
        for ref in gc.get_referrers(tup[0]):
            if is_finalizer_ref(ref):
                continue
            if isinstance(ref, dict):
                logger.warning('\n%s', pprint.pformat(ref))
            else:
                logger.warning(ref)

    GLib.timeout_add_seconds(2, check_finalized)
