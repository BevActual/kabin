import threading
from functools import lru_cache

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .artwork import fetch_remote_cover  # noqa: E402
from .config import Config  # noqa: E402
from .network import HostService, prepare_remote_session  # noqa: E402
from .settings import SettingsWindow  # noqa: E402
from .sources import discover_all  # noqa: E402
from .sources import steam as steam_source  # noqa: E402
from .systems import get_system  # noqa: E402

CATEGORY_HOME = ("home", None)
CATEGORY_ALL = ("all", None)

_SOURCE_BADGE_CANDIDATES = {
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
    "remote": ["network-server-symbolic", "network-workgroup-symbolic"],
}

_SIDEBAR_ICON_CANDIDATES = {
    "home": ["user-home-symbolic", "go-home-symbolic", "applications-games-symbolic"],
    "all": ["view-grid-symbolic", "applications-games-symbolic"],
    "favorites": ["starred-symbolic", "emblem-favorite-symbolic", "applications-games-symbolic"],
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
    "remote": ["network-server-symbolic", "network-workgroup-symbolic"],
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
        if game.source == "remote" and game.extra.get("has_artwork"):
            self._show_icon_plate(Gio.ThemedIcon.new("network-server-symbolic"))
            threading.Thread(target=self._load_remote_cover, daemon=True).start()
            return
        gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
        self._show_icon_plate(gicon)

    def _load_remote_cover(self):
        game = self.game
        try:
            path = fetch_remote_cover(
                game.extra["host"],
                game.extra["host"].get("token", ""),
                game.extra["remote_id"],
            )
        except Exception:
            path = None
        GLib.idle_add(self._on_remote_cover_ready, path)

    def _on_remote_cover_ready(self, path):
        if path:
            self.overlay.set_child(self.picture)
            self.picture.set_filename(str(path))
        return False

    def _load_logo(self, appid):
        cached_logo = icons.cached_path(appid, kind="logo")
        if cached_logo:
            self._show_logo(cached_logo)
        else:
            icons.fetch_async(appid, self._on_logo_ready, kind="logo")

    def _show_icon_plate(self, gicon):
        plate = Gtk.Box(hexpand=True, vexpand=True)
        plate.add_css_class("kabin-tile-plate")
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
        logo_picture.add_css_class("kabin-tile-logo")
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
    scrim.add_css_class("kabin-tile-scrim")
    title_label = Gtk.Label(label=game.title, xalign=0)
    title_label.add_css_class("kabin-tile-title")
    title_label.set_wrap(True)
    title_label.set_lines(2)
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    scrim.append(title_label)
    overlay.add_overlay(scrim)

    badge_icon_name = _resolve_icon_name(
        tuple(_SOURCE_BADGE_CANDIDATES.get(game.source, ["applications-games-symbolic"]))
    )
    badge = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.START)
    badge.add_css_class("kabin-tile-badge")
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
        self.add_css_class("kabin-tile")
        overlay, self._art = _build_tile_overlay(game)
        self.set_child(overlay)


def _build_shelf_button(game, on_activate):
    overlay, _art = _build_tile_overlay(game)
    button = Gtk.Button()
    button.set_overflow(Gtk.Overflow.HIDDEN)
    button.add_css_class("kabin-tile")
    button.add_css_class("flat")
    button.set_child(overlay)
    button.connect("clicked", lambda *_: on_activate(game))
    return button


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self.host_service = HostService(self.config, lambda: list(self._games))
        self._category = CATEGORY_HOME
        self._search_text = ""
        self._sidebar_rows = {}
        self._games = []
        self._has_recent = False
        self._has_added = False
        self._has_favorites = False
        self._selected_game = None
        self._sort_mode = "title"

        self.set_title("Kabin")
        self.set_default_size(1100, 720)
        self.maximize()
        self.add_css_class("kabin-window")

        self._build_ui()
        self.refresh()
        if self.config.network["host_enabled"]:
            self.host_service.start()
        self.connect("close-request", self._on_close_request)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    # -- UI construction ------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("kabin-topbar")

        brand_box = Gtk.Box(spacing=6)
        brand_box.add_css_class("kabin-brand")
        brand_icon = Gtk.Image.new_from_icon_name("applications-games-symbolic")
        brand_icon.add_css_class("kabin-brand-mark")
        brand_word = Gtk.Label(label="KABIN")
        brand_word.add_css_class("kabin-brand-word")
        brand_box.append(brand_icon)
        brand_box.append(brand_word)
        header.pack_start(brand_box)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search games…")
        self.search_entry.add_css_class("kabin-search")
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh_button.add_css_class("kabin-icon-button")
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh_button)

        self.sort_dropdown = Gtk.DropDown.new_from_strings(["Title", "Recently Played"])
        self.sort_dropdown.set_tooltip_text("Sort by")
        self.sort_dropdown.add_css_class("kabin-sort")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        header.pack_end(self.sort_dropdown)

        settings_button = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Settings")
        settings_button.add_css_class("kabin-icon-button")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", lambda *_: self._open_settings())
        header.pack_end(settings_button)

        toolbar_view.add_top_bar(header)

        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(220)
        split_view.set_max_sidebar_width(280)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.add_css_class("kabin-sidebar")
        self.sidebar_list.connect("row-selected", self._on_sidebar_selected)
        sidebar_scroller = Gtk.ScrolledWindow(child=self.sidebar_list)
        sidebar_page = Adw.NavigationPage(title="Library", child=sidebar_scroller)
        split_view.set_sidebar(sidebar_page)

        self.recent_section, self.recent_shelf = self._build_shelf("Continue Playing")
        self.added_section, self.added_shelf = self._build_shelf("Recently Added")
        self.favorite_section, self.favorite_shelf = self._build_shelf("Favorites")

        self.flow_box = Gtk.FlowBox()
        self.flow_box.set_valign(Gtk.Align.START)
        self.flow_box.set_max_children_per_line(12)
        self.flow_box.set_min_children_per_line(2)
        self.flow_box.set_row_spacing(16)
        self.flow_box.set_column_spacing(16)
        self.flow_box.set_homogeneous(True)
        # Single click selects; Enter or double-click opens the game page.
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
        library_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.library_title = Gtk.Label(label="All Games", xalign=0)
        self.library_title.add_css_class("kabin-library-title")
        self.library_subtitle = Gtk.Label(xalign=0)
        self.library_subtitle.add_css_class("kabin-library-subtitle")
        library_header.append(self.library_title)
        library_header.append(self.library_subtitle)
        content_box.append(library_header)
        content_box.append(self.recent_section)
        content_box.append(self.added_section)
        content_box.append(self.favorite_section)
        content_box.append(self.flow_box)

        content_scroller = Gtk.ScrolledWindow(child=content_box)
        content_scroller.add_css_class("kabin-content")
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
        open_settings_button.add_css_class("kabin-empty-cta")
        open_settings_button.connect("clicked", lambda *_: self._open_settings())
        self.empty_status.set_child(open_settings_button)

        self.no_matches_status = Adw.StatusPage(
            title="No matches",
            description="Try a different search or category.",
            icon_name="edit-find-symbolic",
        )
        self.no_matches_status.set_vexpand(True)

        self.loading_status = Adw.StatusPage(
            title="Updating your library",
            description="Finding games and refreshing artwork…",
            icon_name="view-refresh-symbolic",
        )
        self.loading_status.set_vexpand(True)

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(content_scroller, "games")
        self.content_stack.add_named(self.empty_status, "empty")
        self.content_stack.add_named(self.no_matches_status, "no-matches")
        self.content_stack.add_named(self.loading_status, "loading")

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(220)
        self.main_stack.add_named(self.content_stack, "library")
        self.main_stack.add_named(self._build_details_panel(), "details")

        shortcut_bar = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        shortcut_bar.add_css_class("kabin-shortcut-bar")
        for shortcut in ("Enter  Open", "Esc  Back", "/  Search", "F11  Fullscreen"):
            label = Gtk.Label(label=shortcut)
            label.add_css_class("kabin-shortcut")
            shortcut_bar.append(label)
        toolbar_view.add_bottom_bar(shortcut_bar)

        # A heavily downscaled (blurred-by-upscale), theme-tinted backdrop
        # from the selected game's art - the tint comes from the Omarchy
        # theme's own background color, not the raw box art, so it still
        # reads as "this app in your theme" rather than clashing with it.
        self.backdrop_picture = Gtk.Picture()
        self.backdrop_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.backdrop_picture.set_can_shrink(True)
        self.backdrop_picture.add_css_class("kabin-backdrop")

        body_overlay = Gtk.Overlay()
        body_overlay.set_child(self.backdrop_picture)
        body_overlay.add_overlay(self.main_stack)

        content_page = Adw.NavigationPage(title="Games", child=body_overlay)
        split_view.set_content(content_page)

        toolbar_view.set_content(split_view)
        self.set_content(toolbar_view)

    def _build_shelf(self, title):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        header = Gtk.Label(label=title, xalign=0)
        header.add_css_class("kabin-shelf-header")
        section.append(header)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroller.set_min_content_height(226)
        shelf = Gtk.Box(spacing=16)
        scroller.set_child(shelf)
        section.append(scroller)
        section.set_visible(False)
        return section, shelf

    def _build_details_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("kabin-details-page")

        back_button = Gtk.Button(label="Back to library", icon_name="go-previous-symbolic")
        back_button.set_halign(Gtk.Align.START)
        back_button.add_css_class("flat")
        back_button.add_css_class("kabin-details-back")
        back_button.connect("clicked", lambda *_: self._close_details())
        panel.append(back_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=36)
        content.set_halign(Gtk.Align.CENTER)
        content.set_valign(Gtk.Align.CENTER)
        content.set_margin_top(24)
        content.set_margin_bottom(48)
        content.set_margin_start(48)
        content.set_margin_end(48)

        art_frame = Gtk.Box()
        art_frame.set_overflow(Gtk.Overflow.HIDDEN)
        art_frame.add_css_class("kabin-details-art-frame")
        art_frame.set_size_request(320, 430)
        self.details_picture = Gtk.Picture()
        self.details_picture.set_content_fit(Gtk.ContentFit.COVER)
        art_frame.append(self.details_picture)
        content.append(art_frame)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        info.set_size_request(420, -1)
        info.set_valign(Gtk.Align.CENTER)

        self.details_title = Gtk.Label(xalign=0, wrap=True)
        self.details_title.add_css_class("kabin-details-title")
        info.append(self.details_title)

        self.details_meta = Gtk.Label(xalign=0, wrap=True)
        self.details_meta.add_css_class("kabin-details-meta")
        info.append(self.details_meta)

        self.details_play_button = Gtk.Button(label="Play")
        self.details_play_button.add_css_class("suggested-action")
        self.details_play_button.add_css_class("pill")
        self.details_play_button.connect("clicked", lambda *_: self._launch_selected())

        self.details_favorite_icon = Gtk.Image.new_from_icon_name("non-starred-symbolic")
        self.details_favorite_button = Gtk.Button()
        self.details_favorite_button.set_child(self.details_favorite_icon)
        self.details_favorite_button.add_css_class("kabin-icon-button")
        self.details_favorite_button.add_css_class("flat")
        self.details_favorite_button.connect("clicked", lambda *_: self._toggle_favorite_selected())

        action_row = Gtk.Box(spacing=8, halign=Gtk.Align.START)
        action_row.append(self.details_play_button)
        action_row.append(self.details_favorite_button)
        info.append(action_row)

        self.details_description = Gtk.Label(xalign=0, wrap=True)
        self.details_description.add_css_class("kabin-details-description")
        self.details_description.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        info.append(self.details_description)
        content.append(info)

        scroller.set_child(content)
        panel.append(scroller)

        return panel

    def _add_sidebar_header(self, text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_focusable(False)
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("kabin-sidebar-header")
        row.set_child(label)
        self.sidebar_list.append(row)

    def _add_sidebar_row(self, label_text, icon_key, count, category):
        icon_name = _resolve_icon_name(tuple(_SIDEBAR_ICON_CANDIDATES.get(icon_key, [])))

        content = Gtk.Box(spacing=10)
        content.add_css_class("kabin-sidebar-row")

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class("kabin-sidebar-icon")
        content.append(icon)

        label = Gtk.Label(label=label_text, xalign=0, hexpand=True)
        label.add_css_class("kabin-sidebar-label")
        content.append(label)

        if count is not None:
            count_label = Gtk.Label(label=str(count))
            count_label.add_css_class("kabin-sidebar-count")
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
        remote_hosts = {g.subtitle for g in games if g.source == "remote" and g.subtitle}
        remote_hosts.update(
            host.get("name")
            for host in self.config.network.get("remote_hosts", [])
            if host.get("name")
        )
        systems = {g.subtitle for g in games if g.source == "roms" and g.subtitle}
        for entry in self.config.rom_dirs:
            definition = get_system(entry.get("system", ""))
            systems.add(definition.name if definition else entry.get("system", "ROMs"))

        self._add_sidebar_header("HOME")
        self._add_sidebar_row("Home", "home", None, CATEGORY_HOME)
        if favorite_count:
            self._add_sidebar_row("Favorites", "favorites", favorite_count, CATEGORY_FAVORITES)
        self._add_sidebar_header("PC")
        self._add_sidebar_row("All Games", "all", len(games), CATEGORY_ALL)
        if steam_count:
            self._add_sidebar_row("Steam", "steam", steam_count, ("source", "steam"))
        if desktop_count:
            self._add_sidebar_row("Other Apps", "desktop", desktop_count, ("source", "desktop"))
        if remote_hosts:
            self._add_sidebar_header("KABIN HOSTS")
            for host in sorted(remote_hosts):
                count = sum(1 for game in games if game.source == "remote" and game.subtitle == host)
                self._add_sidebar_row(host, "remote", count, ("host", host))
        if systems:
            self._add_sidebar_header("CONSOLES")
            for system in sorted(systems):
                count = sum(1 for g in games if g.source == "roms" and g.subtitle == system)
                self._add_sidebar_row(system, "roms", count, ("system", system))

        self._add_sidebar_header("MANAGE")
        self._add_sidebar_row("Network & Hosts", "remote", None, ("action", "network"))
        self._add_sidebar_row("Emulation Center", "roms", None, ("action", "emulation"))

        target_category = preserve_category if preserve_category is not None else CATEGORY_HOME
        target_row = next(
            (row for row, category in self._sidebar_rows.items() if category == target_category),
            None,
        )
        fallback = next(
            (row for row, category in self._sidebar_rows.items() if category == CATEGORY_HOME), None
        )
        self.sidebar_list.select_row(target_row or fallback)

    # -- data loading -----------------------------------------------------

    def refresh(self):
        self.config.load()
        if hasattr(self, "content_stack"):
            self._close_details()
            self.content_stack.set_visible_child_name("loading")

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
        self._update_library_header()

        first_child = self.flow_box.get_child_at_index(0)
        if first_child:
            self.flow_box.select_child(first_child)
        else:
            self._show_details(None)
        return False

    def _rebuild_recent_shelf(self, games):
        while (child := self.recent_shelf.get_first_child()) is not None:
            self.recent_shelf.remove(child)
        while (child := self.favorite_shelf.get_first_child()) is not None:
            self.favorite_shelf.remove(child)
        while (child := self.added_shelf.get_first_child()) is not None:
            self.added_shelf.remove(child)

        games_by_id = {g.id: g for g in games}
        recent_games = [
            games_by_id[gid] for gid in self.config.recent_ids(limit=8) if gid in games_by_id
        ]
        for game in recent_games:
            self.recent_shelf.append(_build_shelf_button(game, self._open_details))

        added_games = sorted(
            (game for game in games if game.extra.get("added_at")),
            key=lambda game: game.extra["added_at"],
            reverse=True,
        )[:8]
        for game in added_games:
            self.added_shelf.append(_build_shelf_button(game, self._open_details))

        favorite_games = [game for game in games if self.config.is_favorite(game.id)][:8]
        for game in favorite_games:
            self.favorite_shelf.append(_build_shelf_button(game, self._open_details))

        self._has_recent = bool(recent_games)
        self._has_added = bool(added_games)
        self._has_favorites = bool(favorite_games)
        self._update_recent_visibility()

    def _update_recent_visibility(self):
        on_home = not self._search_text and self._category == CATEGORY_HOME
        self.recent_section.set_visible(self._has_recent and on_home)
        self.added_section.set_visible(self._has_added and on_home)
        self.favorite_section.set_visible(self._has_favorites and on_home)

    # -- filtering & interaction -------------------------------------------

    def _matches(self, game) -> bool:
        if self._search_text and self._search_text not in game.title.casefold():
            return False
        kind, value = self._category
        if kind in ("home", "all"):
            return True
        if kind == "favorite":
            return self.config.is_favorite(game.id)
        if kind == "source":
            return game.source == value
        if kind == "system":
            return game.source == "roms" and game.subtitle == value
        if kind == "host":
            return game.source == "remote" and game.subtitle == value
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

    def _update_library_header(self):
        kind, value = self._category
        if kind == "system":
            title = value
            context = "Console library"
        elif kind == "host":
            title, context = value, "Remote Kabin library"
        elif kind == "source" and value == "steam":
            title, context = "Steam", "PC library"
        elif kind == "source" and value == "desktop":
            title, context = "Other Games", "Installed PC games"
        elif kind == "favorite":
            title, context = "Favorites", "Your saved games"
        elif kind == "home":
            title, context = "Welcome back", "Pick up where you left off"
        else:
            title, context = "All Games", "Every installed library"
        count = sum(1 for game in self._games if self._matches(game))
        noun = "game" if count == 1 else "games"
        self.library_title.set_label(title)
        self.library_subtitle.set_label(f"{context} · {count} {noun}")
        if kind == "system" and count == 0:
            self.no_matches_status.set_title(f"No {title} games found")
            self.no_matches_status.set_description(
                "Add supported game files to this console library, then refresh Kabin."
            )
        else:
            self.no_matches_status.set_title("No matches")
            self.no_matches_status.set_description("Try a different search or category.")

    def _on_search_changed(self, entry):
        self._search_text = entry.get_text().strip().casefold()
        self.flow_box.invalidate_filter()
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._sync_selection_to_filter()

    def _on_sidebar_selected(self, listbox, row):
        category = self._sidebar_rows.get(row, CATEGORY_HOME) if row else CATEGORY_HOME
        if category[0] == "action":
            self._open_settings(category[1])
            current_row = next(
                (item for item, value in self._sidebar_rows.items() if value == self._category),
                None,
            )
            if current_row:
                self.sidebar_list.select_row(current_row)
            return
        self._category = category
        self._close_details()
        self.flow_box.invalidate_filter()
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._sync_selection_to_filter()

    def _sync_selection_to_filter(self):
        selected = self.flow_box.get_selected_children()
        if selected and self._matches(selected[0].game):
            return

        child = self.flow_box.get_first_child()
        while child is not None and not self._matches(child.game):
            child = child.get_next_sibling()

        if child is None:
            self.flow_box.unselect_all()
            self._show_details(None)
        else:
            self.flow_box.select_child(child)

    def _launch_game(self, game):
        if game.launch:
            self.config.record_played(game.id)
            self._rebuild_recent_shelf(self._games)
            game.launch()

    def _on_tile_activated(self, flow_box, child: GameTile):
        self._open_details(child.game)

    def _on_tile_selected(self, flow_box):
        selected = flow_box.get_selected_children()
        self._show_details(selected[0].game if selected else None)

    def _launch_selected(self):
        if self._selected_game:
            if self._selected_game.source == "remote":
                self._prepare_remote_selected()
                return
            self._launch_game(self._selected_game)

    def _prepare_remote_selected(self):
        game = self._selected_game
        if not game or game.source != "remote":
            return
        host = game.extra.get("host", {})
        token = host.get("token", "")
        remote_id = game.extra.get("remote_id", "")
        self.details_play_button.set_label("Preparing…")
        self.details_play_button.set_sensitive(False)

        def worker():
            try:
                session = prepare_remote_session(host, token, remote_id)
                error = None
            except Exception as exc:
                session, error = None, str(exc)
            GLib.idle_add(self._on_remote_session_prepared, game, session, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_remote_session_prepared(self, game, session, error):
        if self._selected_game is not game:
            return False
        if error:
            self.details_play_button.set_label("Retry Stream")
            self.details_play_button.set_sensitive(True)
            self.details_description.set_label(f"Could not prepare the host session · {error}")
            return False
        game.extra["session"] = session
        self.details_play_button.set_label("Session Ready")
        self.details_play_button.set_sensitive(False)
        self.details_description.set_label(
            "The host reserved this game successfully. Waiting for Kabin's native WebRTC media channel before launching."
        )
        return False

    def _open_details(self, game):
        self._show_details(game)
        self.main_stack.set_visible_child_name("details")
        self.details_play_button.grab_focus()

    def _close_details(self):
        if hasattr(self, "main_stack"):
            self.main_stack.set_visible_child_name("library")

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
        self._rebuild_recent_shelf(self._games)

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
            self._update_backdrop(None)
            return

        self.details_title.set_label(game.title)
        self.details_description.set_label("")
        self.details_play_button.set_label("Play")
        self.details_play_button.set_sensitive(bool(game.launch))
        self.details_picture.set_paintable(None)
        self._update_backdrop(None)

        source_labels = {"steam": "Steam", "desktop": "Installed App", "remote": "Kabin Host"}
        meta_parts = [source_labels.get(game.source, game.subtitle or game.source.title())]

        if game.source == "remote":
            remote_system = game.extra.get("remote_system")
            if remote_system:
                meta_parts.append(remote_system)
            meta_parts.append(game.subtitle)
            self.details_play_button.set_label("Stream")
            self.details_play_button.set_sensitive(True)
            self.details_description.set_label(
                "Available from this Kabin Host. Native streaming session support is the next network milestone."
            )
            if game.extra.get("has_artwork"):
                threading.Thread(
                    target=self._load_remote_details_art,
                    args=(game,),
                    daemon=True,
                ).start()

        if game.icon_path:
            self.details_picture.set_filename(game.icon_path)
            self._update_backdrop(game.icon_path)
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

    def _load_remote_details_art(self, game):
        try:
            host = game.extra["host"]
            path = fetch_remote_cover(host, host.get("token", ""), game.extra["remote_id"])
        except Exception:
            path = None
        GLib.idle_add(self._on_remote_details_art_ready, game, path)

    def _on_remote_details_art_ready(self, game, path):
        if path and self._selected_game is game:
            self.details_picture.set_filename(str(path))
            self._update_backdrop(path)
        return False

    def _open_settings(self, page=None):
        settings_window = SettingsWindow(
            self.config,
            host_service=self.host_service,
            initial_page=page,
            transient_for=self,
        )
        settings_window.connect("close-request", lambda *_: self.refresh() or False)
        settings_window.present()

    def _on_close_request(self, *_args):
        self.host_service.stop()
        return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if (control and keyval in (Gdk.KEY_f, Gdk.KEY_F)) or keyval == Gdk.KEY_slash:
            self.search_entry.grab_focus()
            return True
        if control and keyval == Gdk.KEY_comma:
            self._open_settings()
            return True
        if keyval == Gdk.KEY_Escape and self.search_entry.get_text():
            self.search_entry.set_text("")
            self.flow_box.grab_focus()
            return True
        if keyval == Gdk.KEY_Escape and self.main_stack.get_visible_child_name() == "details":
            self._close_details()
            return True
        if keyval == Gdk.KEY_BackSpace and self.main_stack.get_visible_child_name() == "details":
            self._close_details()
            return True
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
