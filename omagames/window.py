import threading
from functools import lru_cache

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .config import Config  # noqa: E402
from .settings import SettingsWindow  # noqa: E402
from .sources import discover_all  # noqa: E402

CATEGORY_ALL = ("all", None)

_SOURCE_BADGE_CANDIDATES = {
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
}

_SIDEBAR_ICON_CANDIDATES = {
    "all": ["view-grid-symbolic", "applications-games-symbolic"],
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
}


@lru_cache(maxsize=None)
def _resolve_icon_name(candidates: tuple) -> str:
    display = Gdk.Display.get_default()
    icon_theme = Gtk.IconTheme.get_for_display(display)
    for name in candidates:
        if icon_theme.has_icon(name):
            return name
    return candidates[-1]


class GameTile(Gtk.FlowBoxChild):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.set_focusable(True)
        self.add_css_class("omagames-tile")

        self.overlay = Gtk.Overlay()
        self.overlay.set_size_request(170, 226)

        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.overlay.set_child(self.picture)

        scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END)
        scrim.add_css_class("omagames-tile-scrim")
        title_label = Gtk.Label(label=game.title, xalign=0)
        title_label.add_css_class("omagames-tile-title")
        title_label.set_wrap(True)
        title_label.set_lines(2)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        scrim.append(title_label)
        self.overlay.add_overlay(scrim)

        badge_icon_name = _resolve_icon_name(
            tuple(_SOURCE_BADGE_CANDIDATES.get(game.source, ["applications-games-symbolic"]))
        )
        badge = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.START)
        badge.add_css_class("omagames-tile-badge")
        badge_image = Gtk.Image.new_from_icon_name(badge_icon_name)
        badge_image.set_pixel_size(12)
        badge.append(badge_image)
        self.overlay.add_overlay(badge)

        self.set_child(self.overlay)
        self._load_art()

    def _load_art(self):
        game = self.game
        if game.icon_path:
            self.picture.set_filename(game.icon_path)
            return
        if game.source == "steam":
            appid = game.extra.get("appid")
            cached = icons.cached_path(appid) if appid else None
            if cached:
                self.picture.set_filename(str(cached))
            elif appid:
                icons.fetch_async(appid, self._on_art_ready)
            else:
                self._show_icon_plate(None)
            return
        gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
        self._show_icon_plate(gicon)

    def _show_icon_plate(self, gicon):
        plate = Gtk.Box(hexpand=True, vexpand=True)
        plate.add_css_class("omagames-tile-plate")
        image = (
            Gtk.Image.new_from_gicon(gicon)
            if gicon
            else Gtk.Image.new_from_icon_name("applications-games-symbolic")
        )
        image.set_pixel_size(64)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        image.set_hexpand(True)
        image.set_vexpand(True)
        plate.append(image)
        self.overlay.set_child(plate)

    def _on_art_ready(self, path):
        if path:
            self.picture.set_filename(str(path))
        else:
            self._show_icon_plate(Gio.ThemedIcon.new("applications-games-symbolic"))
        return False


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self._category = CATEGORY_ALL
        self._search_text = ""
        self._sidebar_rows = {}
        self._games = []

        self.set_title("Games")
        self.set_default_size(1100, 720)
        self.maximize()
        self.add_css_class("omagames-window")

        self._build_ui()
        self.refresh()

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    # -- UI construction ------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("omagames-topbar")

        brand_box = Gtk.Box(spacing=6)
        brand_box.add_css_class("omagames-brand")
        brand_icon = Gtk.Image.new_from_icon_name("applications-games-symbolic")
        brand_icon.add_css_class("omagames-brand-mark")
        brand_word = Gtk.Label(label="OMAGAMES")
        brand_word.add_css_class("omagames-brand-word")
        brand_box.append(brand_icon)
        brand_box.append(brand_word)
        header.pack_start(brand_box)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search games…")
        self.search_entry.add_css_class("omagames-search")
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh_button.add_css_class("omagames-icon-button")
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh_button)

        settings_button = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Settings")
        settings_button.add_css_class("omagames-icon-button")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", lambda *_: self._open_settings())
        header.pack_end(settings_button)

        toolbar_view.add_top_bar(header)

        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(220)
        split_view.set_max_sidebar_width(280)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.add_css_class("omagames-sidebar")
        self.sidebar_list.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroller = Gtk.ScrolledWindow(child=self.sidebar_list)
        sidebar_page = Adw.NavigationPage(title="Library", child=sidebar_scroller)
        split_view.set_sidebar(sidebar_page)

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_max_children_per_line(12)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_row_spacing(16)
        self.flow_box.set_column_spacing(16)
        self.flow_box.set_homogeneous(True)
        self.flow_box.set_activate_on_single_click(True)
        self.flow_box.set_filter_func(self._filter_tile)
        self.flow_box.connect("child-activated", self._on_tile_activated)
        self.flow_box.set_margin_top(20)
        self.flow_box.set_margin_bottom(20)
        self.flow_box.set_margin_start(20)
        self.flow_box.set_margin_end(20)

        content_scroller = Gtk.ScrolledWindow(child=self.flow_box)
        content_scroller.add_css_class("omagames-content")
        content_scroller.set_hexpand(True)
        content_scroller.set_vexpand(True)

        self.empty_status = Adw.StatusPage(
            title="No games found",
            description="Add ROM directories in Settings, or install some Steam games.",
            icon_name="applications-games-symbolic",
        )
        self.empty_status.set_vexpand(True)
        open_settings_button = Gtk.Button(label="Open Settings", halign=Gtk.Align.CENTER)
        open_settings_button.add_css_class("suggested-action")
        open_settings_button.add_css_class("omagames-empty-cta")
        open_settings_button.connect("clicked", lambda *_: self._open_settings())
        self.empty_status.set_child(open_settings_button)

        self.no_matches_status = Adw.StatusPage(
            title="No matches",
            description="Try a different search or category.",
            icon_name="edit-find-symbolic",
        )
        self.no_matches_status.set_vexpand(True)

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(content_scroller, "games")
        self.content_stack.add_named(self.empty_status, "empty")
        self.content_stack.add_named(self.no_matches_status, "no-matches")

        content_page = Adw.NavigationPage(title="Games", child=self.content_stack)
        split_view.set_content(content_page)

        toolbar_view.set_content(split_view)
        self.set_content(toolbar_view)

    def _add_sidebar_header(self, text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_focusable(False)
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("omagames-sidebar-header")
        row.set_child(label)
        self.sidebar_list.append(row)

    def _add_sidebar_row(self, label_text, icon_key, count, category):
        icon_name = _resolve_icon_name(tuple(_SIDEBAR_ICON_CANDIDATES.get(icon_key, [])))

        content = Gtk.Box(spacing=10)
        content.add_css_class("omagames-sidebar-row")

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class("omagames-sidebar-icon")
        content.append(icon)

        label = Gtk.Label(label=label_text, xalign=0, hexpand=True)
        label.add_css_class("omagames-sidebar-label")
        content.append(label)

        count_label = Gtk.Label(label=str(count))
        count_label.add_css_class("omagames-sidebar-count")
        content.append(count_label)

        row = Gtk.ListBoxRow()
        row.set_child(content)
        self.sidebar_list.append(row)
        self._sidebar_rows[row] = category

    def _rebuild_sidebar(self, games):
        self.sidebar_list.remove_all()
        self._sidebar_rows = {}

        steam_count = sum(1 for g in games if g.source == "steam")
        desktop_count = sum(1 for g in games if g.source == "desktop")
        systems = sorted({g.subtitle for g in games if g.source == "roms" and g.subtitle})

        self._add_sidebar_row("All Games", "all", len(games), CATEGORY_ALL)
        if steam_count:
            self._add_sidebar_row("Steam", "steam", steam_count, ("source", "steam"))
        if desktop_count:
            self._add_sidebar_row("Other Apps", "desktop", desktop_count, ("source", "desktop"))
        if systems:
            self._add_sidebar_header("ROM Systems")
            for system in systems:
                count = sum(1 for g in games if g.source == "roms" and g.subtitle == system)
                self._add_sidebar_row(system, "roms", count, ("system", system))

        first_row = self.sidebar_list.get_row_at_index(0)
        if first_row:
            self.sidebar_list.select_row(first_row)

    # -- data loading -----------------------------------------------------

    def refresh(self):
        self.config.load()

        def worker():
            games = discover_all(self.config)
            GLib.idle_add(self._on_games_loaded, games)

        threading.Thread(target=worker, daemon=True).start()

    def _on_games_loaded(self, games):
        self._games = games
        self._rebuild_sidebar(games)
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)
        for game in games:
            self.flow_box.append(GameTile(game))
        self._update_stack_visibility()
        return False

    # -- filtering & interaction -------------------------------------------

    def _matches(self, game) -> bool:
        if self._search_text and self._search_text not in game.title.casefold():
            return False
        kind, value = self._category
        if kind == "all":
            return True
        if kind == "source":
            return game.source == value
        if kind == "system":
            return game.source == "roms" and game.subtitle == value
        return True

    def _filter_tile(self, child: GameTile) -> bool:
        return self._matches(child.game)

    def _update_stack_visibility(self):
        if not self._games:
            self.content_stack.set_visible_child_name("empty")
        elif not any(self._matches(g) for g in self._games):
            self.content_stack.set_visible_child_name("no-matches")
        else:
            self.content_stack.set_visible_child_name("games")

    def _on_search_changed(self, entry):
        self._search_text = entry.get_text().strip().casefold()
        self.flow_box.invalidate_filter()
        self._update_stack_visibility()

    def _on_sidebar_selected(self, listbox, row):
        if row is None:
            self._category = CATEGORY_ALL
        else:
            self._category = self._sidebar_rows.get(row, CATEGORY_ALL)
        self.flow_box.invalidate_filter()
        self._update_stack_visibility()

    def _on_tile_activated(self, flow_box, child: GameTile):
        if child.game.launch:
            child.game.launch()

    def _open_settings(self):
        settings_window = SettingsWindow(self.config, transient_for=self)
        settings_window.connect("close-request", lambda *_: self.refresh() or False)
        settings_window.present()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape and self.is_fullscreen():
            self.unfullscreen()
            return True
        if keyval == Gdk.KEY_F11:
            if self.is_fullscreen():
                self.unfullscreen()
            else:
                self.fullscreen()
            return True
        return False
