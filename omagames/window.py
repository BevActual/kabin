import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .config import Config  # noqa: E402
from .settings import SettingsWindow  # noqa: E402
from .sources import discover_all  # noqa: E402

CATEGORY_ALL = ("all", None)


class GameTile(Gtk.FlowBoxChild):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.set_focusable(True)
        self.add_css_class("card")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        self._art_slot = Gtk.Box()
        self._art_slot.set_size_request(160, 214)
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_size_request(160, 214)
        self._art_slot.append(self.picture)
        box.append(self._art_slot)

        label = Gtk.Label(label=game.title)
        label.set_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_lines(2)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(20)
        box.append(label)

        if game.subtitle:
            sub = Gtk.Label(label=game.subtitle)
            sub.add_css_class("dim-label")
            sub.add_css_class("caption")
            box.append(sub)

        self.set_child(box)
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
            return
        if game.gicon:
            self._show_gicon(game.gicon)
        elif game.icon_name:
            self._show_gicon(Gio.ThemedIcon.new(game.icon_name))

    def _show_gicon(self, gicon):
        self._art_slot.remove(self.picture)
        image = Gtk.Image.new_from_gicon(gicon)
        image.set_pixel_size(72)
        image.set_hexpand(True)
        image.set_vexpand(True)
        self._art_slot.append(image)

    def _on_art_ready(self, path):
        if path:
            self.picture.set_filename(str(path))
        else:
            self._show_gicon(Gio.ThemedIcon.new("applications-games-symbolic"))
        return False


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self._category = CATEGORY_ALL
        self._search_text = ""
        self._sidebar_rows = {}

        self.set_title("Games")
        self.set_default_size(1100, 720)
        self.maximize()

        self._build_ui()
        self.refresh()

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    # -- UI construction ------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search games…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh_button)

        settings_button = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Settings")
        settings_button.connect("clicked", lambda *_: self._open_settings())
        header.pack_end(settings_button)

        toolbar_view.add_top_bar(header)

        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(200)
        split_view.set_max_sidebar_width(260)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroller = Gtk.ScrolledWindow(child=self.sidebar_list)
        sidebar_page = Adw.NavigationPage(title="Library", child=sidebar_scroller)
        split_view.set_sidebar(sidebar_page)

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_max_children_per_line(12)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_row_spacing(12)
        self.flow_box.set_column_spacing(12)
        self.flow_box.set_homogeneous(True)
        self.flow_box.set_activate_on_single_click(True)
        self.flow_box.set_filter_func(self._filter_tile)
        self.flow_box.connect("child-activated", self._on_tile_activated)
        self.flow_box.set_margin_top(16)
        self.flow_box.set_margin_bottom(16)
        self.flow_box.set_margin_start(16)
        self.flow_box.set_margin_end(16)

        content_scroller = Gtk.ScrolledWindow(child=self.flow_box)
        content_scroller.set_hexpand(True)
        content_scroller.set_vexpand(True)

        self.empty_status = Adw.StatusPage(
            title="No games found",
            description="Add ROM directories in Settings, or install some Steam games.",
            icon_name="applications-games-symbolic",
        )
        self.empty_status.set_vexpand(True)

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(content_scroller, "games")
        self.content_stack.add_named(self.empty_status, "empty")

        content_page = Adw.NavigationPage(title="Games", child=self.content_stack)
        split_view.set_content(content_page)

        toolbar_view.set_content(split_view)
        self.set_content(toolbar_view)

    def _rebuild_sidebar(self, games):
        self.sidebar_list.remove_all()
        self._sidebar_rows = {}

        systems = sorted({g.subtitle for g in games if g.source == "roms" and g.subtitle})
        entries = [("All Games", CATEGORY_ALL)]
        if any(g.source == "steam" for g in games):
            entries.append(("Steam", ("source", "steam")))
        if any(g.source == "desktop" for g in games):
            entries.append(("Other Apps", ("source", "desktop")))
        for system in systems:
            entries.append((system, ("system", system)))

        for label_text, category in entries:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=label_text, xalign=0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(12)
            label.set_margin_end(12)
            row.set_child(label)
            self.sidebar_list.append(row)
            self._sidebar_rows[row] = category

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
        self.content_stack.set_visible_child_name("games" if games else "empty")
        return False

    # -- filtering & interaction -------------------------------------------

    def _filter_tile(self, child: GameTile) -> bool:
        game = child.game
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

    def _on_search_changed(self, entry):
        self._search_text = entry.get_text().strip().casefold()
        self.flow_box.invalidate_filter()

    def _on_sidebar_selected(self, listbox, row):
        if row is None:
            self._category = CATEGORY_ALL
        else:
            self._category = self._sidebar_rows.get(row, CATEGORY_ALL)
        self.flow_box.invalidate_filter()

    def _on_tile_activated(self, flow_box, child: GameTile):
        if child.game.launch:
            child.game.launch()

    def _open_settings(self):
        settings_window = SettingsWindow(self.config, transient_for=self)
        settings_window.connect("close-request", lambda *_: self.refresh() or False)
        settings_window.present()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        from gi.repository import Gdk

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
