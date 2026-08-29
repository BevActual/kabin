import threading
from functools import lru_cache

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .config import Config  # noqa: E402
from .settings import SettingsWindow  # noqa: E402
from .sources import discover_all  # noqa: E402
from .sources import steam as steam_source  # noqa: E402

CATEGORY_ALL = ("all", None)

_SOURCE_BADGE_CANDIDATES = {
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
}

_SIDEBAR_ICON_CANDIDATES = {
    "all": ["view-grid-symbolic", "applications-games-symbolic"],
    "favorites": ["starred-symbolic", "emblem-favorite-symbolic", "applications-games-symbolic"],
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
}

CATEGORY_FAVORITES = ("favorite", None)


@lru_cache(maxsize=None)
def _resolve_icon_name(candidates: tuple) -> str:
    display = Gdk.Display.get_default()
    icon_theme = Gtk.IconTheme.get_for_display(display)
    for name in candidates:
        if icon_theme.has_icon(name):
            return name
    return candidates[-1]


class _TileArt:
    """Loads cover art (or an icon-plate fallback) and, for Steam games, a
    transparent clear-logo that replaces the plain text title once it's in.
    Shared between grid tiles and shelf tiles so both look identical."""

    def __init__(self, game, overlay, picture, scrim, title_label):
        self.game = game
        self.overlay = overlay
        self.picture = picture
        self.scrim = scrim
        self.title_label = title_label

    def load(self):
        game = self.game
        if game.icon_path:
            self.picture.set_filename(game.icon_path)
            return
        if game.source == "steam":
            appid = game.extra.get("appid")
            if not appid:
                self._show_icon_plate(None)
                return
            cached_cover = icons.cached_path(appid)
            if cached_cover:
                self.picture.set_filename(str(cached_cover))
            else:
                icons.fetch_async(appid, self._on_cover_ready)
            self._load_logo(appid)
            return
        gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
        self._show_icon_plate(gicon)

    def _load_logo(self, appid):
        cached_logo = icons.cached_path(appid, kind="logo")
        if cached_logo:
            self._show_logo(cached_logo)
        else:
            icons.fetch_async(appid, self._on_logo_ready, kind="logo")

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

    def _show_logo(self, path):
        if self.title_label.get_parent() is self.scrim:
            self.scrim.remove(self.title_label)
        logo_picture = Gtk.Picture.new_for_filename(str(path))
        logo_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        logo_picture.set_can_shrink(True)
        logo_picture.set_halign(Gtk.Align.START)
        logo_picture.set_size_request(-1, 40)
        logo_picture.add_css_class("omagames-tile-logo")
        self.scrim.append(logo_picture)

    def _on_cover_ready(self, path):
        if path:
            self.picture.set_filename(str(path))
        else:
            self._show_icon_plate(Gio.ThemedIcon.new("applications-games-symbolic"))
        return False

    def _on_logo_ready(self, path):
        if path:
            self._show_logo(path)
        return False


def _build_tile_overlay(game):
    """A poster-style card: cover art (or icon plate), a bottom gradient
    scrim with the title/logo, and a small source badge in the corner."""
    overlay = Gtk.Overlay()
    overlay.set_size_request(170, 226)

    picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.COVER)
    overlay.set_child(picture)

    scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.END)
    scrim.add_css_class("omagames-tile-scrim")
    title_label = Gtk.Label(label=game.title, xalign=0)
    title_label.add_css_class("omagames-tile-title")
    title_label.set_wrap(True)
    title_label.set_lines(2)
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    scrim.append(title_label)
    overlay.add_overlay(scrim)

    badge_icon_name = _resolve_icon_name(
        tuple(_SOURCE_BADGE_CANDIDATES.get(game.source, ["applications-games-symbolic"]))
    )
    badge = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.START)
    badge.add_css_class("omagames-tile-badge")
    badge_image = Gtk.Image.new_from_icon_name(badge_icon_name)
    badge_image.set_pixel_size(12)
    badge.append(badge_image)
    overlay.add_overlay(badge)

    art = _TileArt(game, overlay, picture, scrim, title_label)
    art.load()
    return overlay, art


class GameTile(Gtk.FlowBoxChild):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.set_focusable(True)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class("omagames-tile")
        overlay, self._art = _build_tile_overlay(game)
        self.set_child(overlay)


def _build_shelf_button(game, on_activate):
    overlay, _art = _build_tile_overlay(game)
    button = Gtk.Button()
    button.set_overflow(Gtk.Overflow.HIDDEN)
    button.add_css_class("omagames-tile")
    button.add_css_class("flat")
    button.set_child(overlay)
    button.connect("clicked", lambda *_: on_activate(game))
    return button


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self._category = CATEGORY_ALL
        self._search_text = ""
        self._sidebar_rows = {}
        self._games = []
        self._has_recent = False
        self._selected_game = None
        self._sort_mode = "title"

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

        self.sort_dropdown = Gtk.DropDown.new_from_strings(["Title", "Recently Played"])
        self.sort_dropdown.set_tooltip_text("Sort by")
        self.sort_dropdown.add_css_class("omagames-sort")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        header.pack_end(self.sort_dropdown)

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

        self.recent_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        recent_header = Gtk.Label(label="Recently Played", xalign=0)
        recent_header.add_css_class("omagames-shelf-header")
        self.recent_section.append(recent_header)
        recent_scroller = Gtk.ScrolledWindow()
        recent_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        recent_scroller.set_min_content_height(226)
        self.recent_shelf = Gtk.Box(spacing=16)
        recent_scroller.set_child(self.recent_shelf)
        self.recent_section.append(recent_scroller)
        self.recent_section.set_visible(False)

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_max_children_per_line(12)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_row_spacing(16)
        self.flow_box.set_column_spacing(16)
        self.flow_box.set_homogeneous(True)
        # Single click selects (updates the details panel); Enter or a
        # double-click activates (launches) - browsing shouldn't risk an
        # accidental launch the way single-click-to-activate did.
        self.flow_box.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.flow_box.set_activate_on_single_click(False)
        self.flow_box.set_filter_func(self._filter_tile)
        self.flow_box.set_sort_func(self._sort_tiles)
        self.flow_box.connect("selected-children-changed", self._on_tile_selected)
        self.flow_box.connect("child-activated", self._on_tile_activated)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        content_box.append(self.recent_section)
        content_box.append(self.flow_box)

        content_scroller = Gtk.ScrolledWindow(child=content_box)
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

        details_widget = self._build_details_panel()

        body_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        body_paned.set_start_child(self.content_stack)
        body_paned.set_resize_start_child(True)
        body_paned.set_shrink_start_child(False)
        body_paned.set_end_child(details_widget)
        body_paned.set_resize_end_child(False)
        body_paned.set_shrink_end_child(False)
        body_paned.set_hexpand(True)
        body_paned.set_vexpand(True)

        # A heavily downscaled (blurred-by-upscale), theme-tinted backdrop
        # from the selected game's art - the tint comes from the Omarchy
        # theme's own background color, not the raw box art, so it still
        # reads as "this app in your theme" rather than clashing with it.
        self.backdrop_picture = Gtk.Picture()
        self.backdrop_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.backdrop_picture.set_can_shrink(True)
        self.backdrop_picture.add_css_class("omagames-backdrop")

        body_overlay = Gtk.Overlay()
        body_overlay.set_child(self.backdrop_picture)
        body_overlay.add_overlay(body_paned)

        content_page = Adw.NavigationPage(title="Games", child=body_overlay)
        split_view.set_content(content_page)

        toolbar_view.set_content(split_view)
        self.set_content(toolbar_view)

    def _build_details_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("omagames-details")

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)

        art_frame = Gtk.Box()
        art_frame.set_overflow(Gtk.Overflow.HIDDEN)
        art_frame.add_css_class("omagames-details-art-frame")
        art_frame.set_size_request(-1, 180)
        self.details_picture = Gtk.Picture()
        self.details_picture.set_content_fit(Gtk.ContentFit.COVER)
        art_frame.append(self.details_picture)
        content.append(art_frame)

        self.details_title = Gtk.Label(xalign=0, wrap=True)
        self.details_title.add_css_class("omagames-details-title")
        content.append(self.details_title)

        self.details_meta = Gtk.Label(xalign=0, wrap=True)
        self.details_meta.add_css_class("omagames-details-meta")
        content.append(self.details_meta)

        self.details_play_button = Gtk.Button(label="Play")
        self.details_play_button.add_css_class("suggested-action")
        self.details_play_button.add_css_class("pill")
        self.details_play_button.connect("clicked", lambda *_: self._launch_selected())

        self.details_favorite_icon = Gtk.Image.new_from_icon_name("non-starred-symbolic")
        self.details_favorite_button = Gtk.Button()
        self.details_favorite_button.set_child(self.details_favorite_icon)
        self.details_favorite_button.add_css_class("omagames-icon-button")
        self.details_favorite_button.add_css_class("flat")
        self.details_favorite_button.connect("clicked", lambda *_: self._toggle_favorite_selected())

        action_row = Gtk.Box(spacing=8, halign=Gtk.Align.START)
        action_row.append(self.details_play_button)
        action_row.append(self.details_favorite_button)
        content.append(action_row)

        self.details_description = Gtk.Label(xalign=0, wrap=True)
        self.details_description.add_css_class("omagames-details-description")
        self.details_description.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        content.append(self.details_description)

        scroller.set_child(content)
        panel.append(scroller)

        self.details_empty = Adw.StatusPage(
            title="No game selected",
            description="Choose a game to see its details here.",
            icon_name="applications-games-symbolic",
        )
        self.details_empty.set_vexpand(True)

        details_stack = Gtk.Stack()
        details_stack.add_named(panel, "details")
        details_stack.add_named(self.details_empty, "empty")
        details_stack.set_size_request(320, -1)
        self.details_stack = details_stack
        return details_stack

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

    def _rebuild_sidebar(self, games, preserve_category=None):
        self.sidebar_list.remove_all()
        self._sidebar_rows = {}

        favorite_count = sum(1 for g in games if self.config.is_favorite(g.id))
        steam_count = sum(1 for g in games if g.source == "steam")
        desktop_count = sum(1 for g in games if g.source == "desktop")
        systems = sorted({g.subtitle for g in games if g.source == "roms" and g.subtitle})

        self._add_sidebar_row("All Games", "all", len(games), CATEGORY_ALL)
        if favorite_count:
            self._add_sidebar_row("Favorites", "favorites", favorite_count, CATEGORY_FAVORITES)
        if steam_count:
            self._add_sidebar_row("Steam", "steam", steam_count, ("source", "steam"))
        if desktop_count:
            self._add_sidebar_row("Other Apps", "desktop", desktop_count, ("source", "desktop"))
        if systems:
            self._add_sidebar_header("ROM Systems")
            for system in systems:
                count = sum(1 for g in games if g.source == "roms" and g.subtitle == system)
                self._add_sidebar_row(system, "roms", count, ("system", system))

        target_category = preserve_category if preserve_category is not None else CATEGORY_ALL
        target_row = next(
            (row for row, category in self._sidebar_rows.items() if category == target_category),
            None,
        )
        self.sidebar_list.select_row(target_row or self.sidebar_list.get_row_at_index(0))

    # -- data loading -----------------------------------------------------

    def refresh(self):
        self.config.load()

        def worker():
            games = discover_all(self.config)
            GLib.idle_add(self._on_games_loaded, games)

        threading.Thread(target=worker, daemon=True).start()

    def _on_games_loaded(self, games):
        self._games = games
        self._rebuild_sidebar(games, preserve_category=self._category)
        while (child := self.flow_box.get_first_child()) is not None:
            self.flow_box.remove(child)
        for game in games:
            self.flow_box.append(GameTile(game))
        self._rebuild_recent_shelf(games)
        self._update_stack_visibility()

        first_child = self.flow_box.get_child_at_index(0)
        if first_child:
            self.flow_box.select_child(first_child)
        else:
            self._show_details(None)
        return False

    def _rebuild_recent_shelf(self, games):
        while (child := self.recent_shelf.get_first_child()) is not None:
            self.recent_shelf.remove(child)

        games_by_id = {g.id: g for g in games}
        recent_games = [
            games_by_id[gid] for gid in self.config.recent_ids(limit=8) if gid in games_by_id
        ]
        for game in recent_games:
            self.recent_shelf.append(_build_shelf_button(game, self._launch_game))

        self._has_recent = bool(recent_games)
        self._update_recent_visibility()

    def _update_recent_visibility(self):
        show = self._has_recent and not self._search_text and self._category == CATEGORY_ALL
        self.recent_section.set_visible(show)

    # -- filtering & interaction -------------------------------------------

    def _matches(self, game) -> bool:
        if self._search_text and self._search_text not in game.title.casefold():
            return False
        kind, value = self._category
        if kind == "all":
            return True
        if kind == "favorite":
            return self.config.is_favorite(game.id)
        if kind == "source":
            return game.source == value
        if kind == "system":
            return game.source == "roms" and game.subtitle == value
        return True

    def _filter_tile(self, child: GameTile) -> bool:
        return self._matches(child.game)

    def _sort_tiles(self, child_a: GameTile, child_b: GameTile) -> int:
        if self._sort_mode == "recent":
            recent = self.config.recent
            time_a = recent.get(child_a.game.id, 0)
            time_b = recent.get(child_b.game.id, 0)
            if time_a != time_b:
                return -1 if time_a > time_b else 1
        key_a, key_b = child_a.game.sort_key, child_b.game.sort_key
        return -1 if key_a < key_b else (1 if key_a > key_b else 0)

    def _on_sort_changed(self, dropdown, _pspec):
        self._sort_mode = "recent" if dropdown.get_selected() == 1 else "title"
        self.flow_box.invalidate_sort()

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
        self._update_recent_visibility()

    def _on_sidebar_selected(self, listbox, row):
        if row is None:
            self._category = CATEGORY_ALL
        else:
            self._category = self._sidebar_rows.get(row, CATEGORY_ALL)
        self.flow_box.invalidate_filter()
        self._update_stack_visibility()
        self._update_recent_visibility()

    def _launch_game(self, game):
        if game.launch:
            self.config.record_played(game.id)
            game.launch()

    def _on_tile_activated(self, flow_box, child: GameTile):
        self._launch_game(child.game)

    def _on_tile_selected(self, flow_box):
        selected = flow_box.get_selected_children()
        self._show_details(selected[0].game if selected else None)

    def _launch_selected(self):
        if self._selected_game:
            self._launch_game(self._selected_game)

    def _update_backdrop(self, cover_path):
        if cover_path is None:
            self.backdrop_picture.set_paintable(None)
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(cover_path))
        except GLib.Error:
            self.backdrop_picture.set_paintable(None)
            return
        # Shrink drastically first so the inevitable upscale-to-fill blurs
        # it - a cheap stand-in for a real gaussian blur.
        width, height = pixbuf.get_width(), pixbuf.get_height()
        scale = 32 / max(width, height, 1)
        small_width = max(1, round(width * scale))
        small_height = max(1, round(height * scale))
        small = pixbuf.scale_simple(small_width, small_height, GdkPixbuf.InterpType.BILINEAR)
        if small is None:
            self.backdrop_picture.set_paintable(None)
            return
        self.backdrop_picture.set_paintable(Gdk.Texture.new_for_pixbuf(small))

    def _toggle_favorite_selected(self):
        if not self._selected_game:
            return
        self.config.toggle_favorite(self._selected_game.id)
        self._update_favorite_button()
        self._rebuild_sidebar(self._games, preserve_category=self._category)

    def _update_favorite_button(self):
        if not self._selected_game:
            return
        is_favorite = self.config.is_favorite(self._selected_game.id)
        self.details_favorite_icon.set_from_icon_name(
            "starred-symbolic" if is_favorite else "non-starred-symbolic"
        )
        self.details_favorite_button.set_tooltip_text(
            "Remove from Favorites" if is_favorite else "Add to Favorites"
        )

    def _show_details(self, game):
        self._selected_game = game
        if game is None:
            self.details_stack.set_visible_child_name("empty")
            self._update_backdrop(None)
            return
        self.details_stack.set_visible_child_name("details")

        self.details_title.set_label(game.title)
        self.details_description.set_label("")
        self.details_picture.set_paintable(None)
        self._update_backdrop(None)

        source_labels = {"steam": "Steam", "desktop": "Installed App"}
        meta_parts = [source_labels.get(game.source, game.subtitle or game.source.title())]

        if game.icon_path:
            self.details_picture.set_filename(game.icon_path)
        elif game.source == "steam":
            appid = game.extra.get("appid")
            if appid:
                cached = icons.cached_path(appid)
                if cached:
                    self.details_picture.set_filename(str(cached))
                    self._update_backdrop(cached)
                metadata = steam_source.load_local_metadata(appid, self.config.data.get("steam_root"))
                if metadata.get("developers"):
                    meta_parts.append(", ".join(metadata["developers"][:2]))
                if metadata.get("description"):
                    self.details_description.set_label(metadata["description"])

        self.details_meta.set_label(" · ".join(meta_parts))
        self._update_favorite_button()

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
