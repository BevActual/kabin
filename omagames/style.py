from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from . import theme  # noqa: E402

_STYLE_PATH = Path(__file__).resolve().parent.parent / "data" / "style.css"

_DEFINE_TEMPLATE = """
@define-color accent_color {accent};
@define-color bg_color {background};
@define-color bg_dark_color {dark_background};
@define-color bg_darker_color {darker_background};
@define-color bg_light_color {lighter_background};
@define-color fg_color {foreground};
@define-color fg_dim_color {light_foreground};
@define-color selection_color {selection};
@define-color muted_color {muted};
"""


def build_stylesheet() -> str:
    colors = theme.load_colors()
    defines = _DEFINE_TEMPLATE.format(**colors)
    try:
        rules = _STYLE_PATH.read_text()
    except OSError:
        rules = ""
    return defines + "\n" + rules


def apply():
    provider = Gtk.CssProvider()
    provider.load_from_string(build_stylesheet())
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
