import gi


def require_versions():
    gi.require_versions({'Gdk': '3.0',
                         'GLib': '2.0',
                         'Gio': '2.0',
                         'Gtk': '3.0',
                         'GtkSource': '4',
                         'GObject': '2.0',
                         'Pango': '1.0'})

require_versions()

from gajim.common import app
from gajim.common.settings import Settings

app.settings = Settings(in_memory=True)
app.settings.init()
