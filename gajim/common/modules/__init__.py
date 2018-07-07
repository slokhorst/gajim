# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

import logging
from importlib import import_module
from pathlib import Path

log = logging.getLogger('gajim.c.m')

imported_modules = []
_modules = {}

for file in Path(__file__).parent.iterdir():
    if file.stem == '__init__':
        continue

    module = import_module('.%s' % file.stem, package='gajim.common.modules')
    if hasattr(module, 'get_instance'):
        log.info('Load module: %s', file.stem)
        imported_modules.append(module)


class ModuleMock:
    def __getattr__(self, key):
        def _mock(self, *args, **kwargs):
            return
        return _mock


def register(con, *args, **kwargs):
    if con in _modules:
        return
    _modules[con.name] = {}
    for module in imported_modules:
        instance, name = module.get_instance(con, *args, **kwargs)
        _modules[con.name][name] = instance


def unregister(con):
    del _modules[con.name]


def get(account, name):
    try:
        return _modules[account][name]
    except KeyError:
        return ModuleMock()


def get_handlers(con):
    handlers = []
    for module in _modules[con.name].values():
        handlers += module.handlers
    return handlers
