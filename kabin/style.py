from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

_STYLE_PATH = Path(__file__).resolve().parent.parent / "data" / "style.css"

_KABIN_PALETTE = """
@define-color accent_color #ffb454;
@define-color accent_bg_color #d98724;
@define-color accent_fg_color #120d06;
@define-color window_bg_color #101217;
@define-color window_fg_color #f4f1ea;
@define-color view_bg_color #151820;
@define-color view_fg_color #f4f1ea;
@define-color headerbar_bg_color #0c0e13;
@define-color headerbar_fg_color #f4f1ea;
@define-color card_bg_color #191c24;
@define-color card_fg_color #f4f1ea;

@define-color bg_color #101217;
@define-color bg_dark_color #0c0e13;
@define-color bg_darker_color #080a0f;
@define-color bg_light_color #191c24;
@define-color fg_color #f4f1ea;
@define-color fg_dim_color #a9adb7;
@define-color selection_color #343a47;
@define-color muted_color #272c36;
@define-color success_color #65d995;
@define-color warning_color #ffb454;
@define-color error_color #ff6b6b;
"""


def build_stylesheet() -> str:
    try:
        rules = _STYLE_PATH.read_text()
    except OSError:
        rules = ""
    return _KABIN_PALETTE + "\n" + rules


def apply():
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    provider = Gtk.CssProvider()
    provider.load_from_string(build_stylesheet())
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
