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

import os
import logging
import hashlib
from math import pi
from functools import lru_cache
from collections import defaultdict

from gi.repository import Gdk
from gi.repository import GdkPixbuf
import cairo

from gajim.common import configpaths
from gajim.common.helpers import Singleton
from gajim.common.const import AvatarSize

from gajim.gtk.util import load_pixbuf
from gajim.gtk.util import text_to_color
from gajim.gtk.util import scale_with_ratio


log = logging.getLogger('gajim.gtk.avatar')


@lru_cache(maxsize=1024)
def generate_avatar(letters, color, size, scale):
    # Get color for nickname with XEP-0392
    color_r, color_g, color_b = color

    # Set up colors and size
    if scale is not None:
        size = size * scale

    width = size
    height = size
    font_size = size * 0.5

    # Set up surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = cairo.Context(surface)

    context.set_source_rgb(color_r, color_g, color_b)
    context.rectangle(0, 0, width, height)
    context.fill()

    # Draw letters
    context.select_font_face('sans-serif',
                             cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_NORMAL)
    context.set_font_size(font_size)
    extends = context.text_extents(letters)
    if isinstance(extends, tuple):
        # For cairo < 1.15
        x_bearing, y_bearing, ex_width, ex_height = extends[0:4]
    else:
        x_bearing = extends.x_bearing
        y_bearing = extends.y_bearing
        ex_width = extends.width
        ex_height = extends.height

    x_pos = width / 2 - (ex_width / 2 + x_bearing)
    y_pos = height / 2 - (ex_height / 2 + y_bearing)
    context.move_to(x_pos, y_pos)
    context.set_source_rgb(0.95, 0.95, 0.95)
    # use cairo.OPERATOR_OVER legacy constant because its
    # compatible with cairo < 1.13
    context.set_operator(cairo.OPERATOR_OVER)
    context.show_text(letters)

    return context.get_target()


def clip_circle(surface):
    new_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     surface.get_width(),
                                     surface.get_height())
    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)

    width = surface.get_width()
    height = surface.get_height()
    radius = width / 2

    context.arc(width / 2, height / 2, radius, 0, 2 * pi)

    context.clip()
    context.paint()

    return context.get_target()


class AvatarStorage(metaclass=Singleton):
    def __init__(self):
        self._cache = defaultdict(dict)

    def invalidate_cache(self, jid):
        self._cache.pop(jid, None)

    def get_pixbuf(self, contact, size, scale):
        surface = self.get_surface(contact, size, scale)
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)

    def get_surface(self, contact, size, scale):
        jid = contact.jid
        if contact.is_gc_contact:
            jid = contact.get_full_jid()

        surface = self._cache[jid].get((size, scale))
        if surface is not None:
            return surface

        surface = self._get_avatar_from_storage(contact, size, scale)
        if surface is not None:
            self._cache[jid][(size, scale)] = surface
            return surface

        surface = self._generate_default_avatar(contact, size, scale)
        self._cache[jid][(size, scale)] = surface
        return surface

    def prepare_for_publish(self, path):
        success, data = self._load_for_publish(path)
        if not success:
            return None, None

        sha = self.save_avatar(data)
        if sha is None:
            return None, None
        return data, sha

    @staticmethod
    def _load_for_publish(path):
        pixbuf = load_pixbuf(path)
        if pixbuf is None:
            return None

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width > AvatarSize.PUBLISH or height > AvatarSize.PUBLISH:
            # Scale only down, never up
            width, height = scale_with_ratio(AvatarSize.PUBLISH, width, height)
            pixbuf = pixbuf.scale_simple(width,
                                         height,
                                         GdkPixbuf.InterpType.BILINEAR)

        return pixbuf.save_to_bufferv('png', [], [])

    @staticmethod
    def save_avatar(data):
        """
        Save an avatar to the harddisk

        :param data:  bytes

        returns SHA1 value of the avatar or None on error
        """
        if data is None:
            return None

        sha = hashlib.sha1(data).hexdigest()
        path = os.path.join(configpaths.get('AVATAR'), sha)
        try:
            with open(path, 'wb') as output_file:
                output_file.write(data)
        except Exception:
            log.error('Storing avatar failed', exc_info=True)
            return None
        return sha

    @staticmethod
    def get_avatar_path(filename):
        path = os.path.join(configpaths.get('AVATAR'), filename)
        if not os.path.isfile(path):
            return None
        return path

    def pixbuf_from_filename(self, filename):
        path = self.get_avatar_path(filename)
        if path is None:
            return None
        return load_pixbuf(path)

    def surface_from_filename(self, filename, size, scale):
        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None

        return Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)

    def _load_surface_from_storage(self, contact, size, scale):
        filename = contact.avatar_sha
        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None
        return Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)

    def _get_avatar_from_storage(self, contact, size, scale):
        if contact.avatar_sha is None:
            return None

        surface = self._load_surface_from_storage(contact, size, scale)
        if surface is None:
            return None
        return clip_circle(surface)

    @staticmethod
    def _generate_default_avatar(contact, size, scale):
        # Get initial from name
        name = contact.get_shown_name()
        letter = name[0].capitalize()

        # Use nickname for group chats and bare JID for single contacts
        if contact.is_gc_contact:
            color_string = contact.name
        else:
            color_string = contact.jid
        color = text_to_color(color_string)
        surface = generate_avatar(letter, color, size, scale)
        return clip_circle(surface)