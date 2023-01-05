# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from dataclasses import dataclass
from dataclasses import field

from gajim.common.events import ApplicationEvent
from gajim.plugins.manifest import PluginManifest


@dataclass
class PluginAdded(ApplicationEvent):
    name: str = field(init=False, default='plugin-added')
    manifest: PluginManifest


@dataclass
class PluginRemoved(ApplicationEvent):
    name: str = field(init=False, default='plugin-removed')
    manifest: PluginManifest
