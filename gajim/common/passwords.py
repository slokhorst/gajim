# Copyright (C) 2006 Gustavo J. A. M. Carneiro <gjcarneiro AT gmail.com>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (c) 2009 Thorsten Glaser <t.glaser AT tarent.de>
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

import logging
import keyring

from gajim.common import app

__all__ = ['get_password', 'save_password']

log = logging.getLogger('gajim.password')


backends = keyring.backend.get_all_keyring()
for backend in backends:
    log.info('Found keyring backend: %s', backend)

keyring_backend = keyring.get_keyring()
log.info('Select %s backend', keyring_backend)

KEYRING_AVAILABLE = any(keyring.core.recommended(backend)
                        for backend in backends)


class SecretPasswordStorage:
    """
    Store password using Keyring
    """

    @staticmethod
    def save_password(account_name, password):
        if not KEYRING_AVAILABLE:
            log.warning('No recommended keyring backend available.'
                        'Passwords cannot be stored.')
            return True
        try:
            log.info('Save password to keyring')
            keyring_backend.set_password('gajim', account_name, password)
            return True
        except Exception:
            log.exception('Save password failed')
            return False

    @staticmethod
    def get_password(account_name):
        log.info('Request password from keyring')
        if not KEYRING_AVAILABLE:
            return
        try:
            # For security reasons remove clear-text password
            ConfigPasswordStorage.delete_password(account_name)
            return keyring_backend.get_password('gajim', account_name)
        except Exception:
            log.exception('Request password failed')
            return

    @staticmethod
    def delete_password(account_name):
        log.info('Remove password from keyring')
        if not KEYRING_AVAILABLE:
            return
        try:
            return keyring_backend.delete_password('gajim', account_name)
        except keyring.errors.PasswordDeleteError as error:
            log.warning('Removing password failed: %s', error)
        except Exception:
            log.exception('Removing password failed')


class ConfigPasswordStorage:
    """
    Store password directly in Gajim's config
    """

    @staticmethod
    def get_password(account_name):
        return app.config.get_per('accounts', account_name, 'password')

    @staticmethod
    def save_password(account_name, password):
        app.config.set_per('accounts', account_name, 'password', password)
        return True

    @staticmethod
    def delete_password(account_name):
        app.config.set_per('accounts', account_name, 'password', '')
        return True


def get_password(account_name):
    if app.config.get('use_keyring'):
        return SecretPasswordStorage.get_password(account_name)
    return ConfigPasswordStorage.get_password(account_name)


def save_password(account_name, password):
    if account_name in app.connections:
        app.connections[account_name].password = password

    if not app.config.get_per('accounts', account_name, 'savepass'):
        return True

    if app.config.get('use_keyring'):
        return SecretPasswordStorage.save_password(account_name, password)
    return ConfigPasswordStorage.save_password(account_name, password)


def delete_password(account_name):
    if account_name in app.connections:
        app.connections[account_name].password = None

    if app.config.get('use_keyring'):
        return SecretPasswordStorage.delete_password(account_name)
    return ConfigPasswordStorage.delete_password(account_name)
