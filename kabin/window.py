import threading
import time
from functools import lru_cache

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .artwork import fetch_remote_cover  # noqa: E402
from .artwork_queue import ArtworkQueue  # noqa: E402
from .config import Config  # noqa: E402
from .network import HostService, prepare_remote_session  # noqa: E402
from .settings import SettingsWindow  # noqa: E402
from .sources import discover_all_with_status  # noqa: E402
from .sources import steam as steam_source  # noqa: E402
from .systems import get_system  # noqa: E402

CATEGORY_HOME = ("home", None)
CATEGORY_ALL = ("all", None)

_SOURCE_BADGE_CANDIDATES = {
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
    "remote": ["network-server-symbolic", "network-workgroup-symbolic"],
    "network-offline": ["network-offline-symbolic", "network-error-symbolic"],
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

_remote_artwork = ArtworkQueue(
    fetch_remote_cover,
    lambda callback, result: GLib.idle_add(callback, result),
)


@lru_cache(maxsize=None)
def _resolve_icon_name(candidates: tuple) -> str:
    display = Gdk.Display.get_default()
    icon_theme = Gtk.IconTheme.get_for_display(display)
    for name in candidates:
        if icon_theme.has_icon(name):
            return name
    return candidates[-1]


class _TileArt:
    """Loads cover art or an icon-plate fallback for a reusable game card."""

    def __init__(self, game, overlay, picture):
        self.game = game
        self.overlay = overlay
        self.picture = picture

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
            return
        if game.source == "remote" and game.extra.get("has_artwork"):
            self._show_icon_plate(Gio.ThemedIcon.new("network-server-symbolic"))
            host = game.extra["host"]
            _remote_artwork.request(
                host,
                host.get("token", ""),
                game.extra["remote_id"],
                self._on_remote_cover_ready,
            )
            return
        gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
        self._show_icon_plate(gicon)

    def _on_remote_cover_ready(self, path):
        if path:
            self.overlay.set_child(self.picture)
            self.picture.set_filename(str(path))
        return False

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

    def _on_cover_ready(self, path):
        if path:
            self.picture.set_filename(str(path))
        else:
            self._show_icon_plate(Gio.ThemedIcon.new("applications-games-symbolic"))
        return False

def _tile_subtitle(game) -> str:
    if game.source == "remote":
        return game.subtitle or "Kabin Host"
    if game.source == "roms":
        return game.subtitle or "Console"
    if game.source == "steam":
        return "Steam"
    return "Installed app"


def _build_tile_content(game):
    """Build an artwork-first card with a stable, readable text footer."""
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    content.set_size_request(170, -1)

    overlay = Gtk.Overlay()
    overlay.set_size_request(170, 226)
    overlay.set_overflow(Gtk.Overflow.HIDDEN)
    overlay.add_css_class("kabin-tile-art")

    picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.COVER)
    overlay.set_child(picture)

    badge_icon_name = _resolve_icon_name(
        tuple(_SOURCE_BADGE_CANDIDATES.get(game.source, ["applications-games-symbolic"]))
    )
    badge = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.START)
    badge.add_css_class("kabin-tile-badge")
    badge_image = Gtk.Image.new_from_icon_name(badge_icon_name)
    badge_image.set_pixel_size(12)
    badge.append(badge_image)
    overlay.add_overlay(badge)

    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    text.add_css_class("kabin-tile-text")
    title = Gtk.Label(label=game.title, xalign=0)
    title.set_ellipsize(Pango.EllipsizeMode.END)
    title.set_tooltip_text(game.title)
    title.add_css_class("kabin-tile-title")
    title.add_css_class("heading")
    subtitle = Gtk.Label(label=_tile_subtitle(game), xalign=0)
    subtitle.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle.add_css_class("kabin-tile-subtitle")
    subtitle.add_css_class("caption")
    subtitle.add_css_class("dim-label")
    text.append(title)
    text.append(subtitle)
    content.append(overlay)
    content.append(text)

    art = _TileArt(game, overlay, picture)
    art.load()
    return content, art


class GameItem(GObject.Object):
    def __init__(self, game):
        super().__init__()
        self.game = game


class GameTile(Gtk.Box):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.set_focusable(False)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class("kabin-tile")
        content, self._art = _build_tile_content(game)
        self.append(content)


def _build_shelf_button(game, on_activate):
    content, _art = _build_tile_content(game)
    button = Gtk.Button()
    button.set_overflow(Gtk.Overflow.HIDDEN)
    button.add_css_class("kabin-tile")
    button.add_css_class("flat")
    button.set_tooltip_text(f"{game.title} — {_tile_subtitle(game)}")
    button.set_child(content)
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
        self._host_statuses = {}
        self._has_recent = False
        self._has_added = False
        self._has_favorites = False
        self._selected_game = None
        self._sort_mode = "title"
        self._location_filter = "all"
        self._favorites_only = False

        self.set_title("Kabin")
        window_state = self.config.window
        self.set_default_size(window_state["width"], window_state["height"])
        if window_state["maximized"]:
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
        brand_word.add_css_class("heading")
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

        self.filter_button = Gtk.MenuButton(
            icon_name="view-filter-symbolic",
            tooltip_text="Filter games",
        )
        self.filter_button.add_css_class("kabin-icon-button")
        self.filter_button.add_css_class("flat")
        self.filter_button.set_popover(self._build_filter_popover())
        header.pack_end(self.filter_button)

        self.sort_dropdown = Gtk.DropDown.new_from_strings(
            ["Title", "Recently Played", "Recently Added"]
        )
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

        self.game_store = Gio.ListStore.new(GameItem)
        self.game_filter = Gtk.CustomFilter.new(self._filter_item)
        self.filtered_games = Gtk.FilterListModel.new(self.game_store, self.game_filter)
        self.game_sorter = Gtk.CustomSorter.new(self._compare_items)
        self.sorted_games = Gtk.SortListModel.new(self.filtered_games, self.game_sorter)
        self.game_selection = Gtk.SingleSelection.new(self.sorted_games)
        self.game_selection.set_autoselect(True)

        tile_factory = Gtk.SignalListItemFactory()
        tile_factory.connect("bind", self._bind_game_tile)
        tile_factory.connect("unbind", self._unbind_game_tile)
        self.game_grid = Gtk.GridView.new(self.game_selection, tile_factory)
        self.game_grid.set_max_columns(12)
        self.game_grid.set_min_columns(2)
        self.game_grid.set_single_click_activate(False)
        self.game_grid.add_css_class("kabin-game-grid")
        self.game_grid.connect("activate", self._on_tile_activated)
        self.game_selection.connect("notify::selected-item", self._on_tile_selected)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)
        library_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.library_title = Gtk.Label(label="All Games", xalign=0)
        self.library_title.add_css_class("kabin-library-title")
        self.library_title.add_css_class("title-1")
        self.library_subtitle = Gtk.Label(xalign=0)
        self.library_subtitle.add_css_class("kabin-library-subtitle")
        self.library_subtitle.add_css_class("dim-label")
        library_header.append(self.library_title)
        library_header.append(self.library_subtitle)
        content_box.append(library_header)
        content_box.append(self.recent_section)
        content_box.append(self.added_section)
        content_box.append(self.favorite_section)
        self.game_scroller = Gtk.ScrolledWindow(child=self.game_grid)
        self.game_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.game_scroller.set_hexpand(True)
        self.game_scroller.set_vexpand(True)
        content_box.append(self.game_scroller)
        content_box.add_css_class("kabin-content")

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
        self.content_stack.add_named(content_box, "games")
        self.content_stack.add_named(self.empty_status, "empty")
        self.content_stack.add_named(self.no_matches_status, "no-matches")
        self.content_stack.add_named(self.loading_status, "loading")

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(220)
        self.main_stack.add_named(self.content_stack, "library")
        self.main_stack.add_named(self._build_details_panel(), "details")

        self.shortcut_bar = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        self.shortcut_bar.add_css_class("kabin-shortcut-bar")
        for shortcut in ("Enter  Open", "Esc  Back", "/  Search", "F11  Fullscreen"):
            label = Gtk.Label(label=shortcut)
            label.add_css_class("kabin-shortcut")
            label.add_css_class("caption")
            self.shortcut_bar.append(label)
        toolbar_view.add_bottom_bar(self.shortcut_bar)

        # A heavily downscaled artwork backdrop behind Kabin's own translucent
        # surface palette. Keeping it subtle prevents cover colors from
        # competing with navigation and text.
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
        self.toast_overlay = Adw.ToastOverlay(child=toolbar_view)
        self.set_content(self.toast_overlay)

        compact = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760px"))
        compact.add_setter(split_view, "collapsed", True)
        compact.add_setter(self.details_content, "orientation", Gtk.Orientation.VERTICAL)
        compact.add_setter(self.details_content, "spacing", 20)
        compact.add_setter(self.details_content, "margin-start", 20)
        compact.add_setter(self.details_content, "margin-end", 20)
        compact.add_setter(self.details_art_frame, "width-request", 240)
        compact.add_setter(self.details_art_frame, "height-request", 322)
        compact.add_setter(self.details_info, "width-request", -1)
        compact.add_setter(self.shortcut_bar, "visible", False)
        self.add_breakpoint(compact)

    def _build_shelf(self, title):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        header = Gtk.Label(label=title, xalign=0)
        header.add_css_class("kabin-shelf-header")
        header.add_css_class("heading")
        section.append(header)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroller.set_min_content_height(278)
        shelf = Gtk.Box(spacing=16)
        scroller.set_child(shelf)
        section.append(scroller)
        section.set_visible(False)
        return section, shelf

    def _build_filter_popover(self):
        popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        heading = Gtk.Label(label="Show games from", xalign=0)
        heading.add_css_class("heading")
        content.append(heading)

        self.location_filters = {}
        first = None
        for value, label in (
            ("all", "Everywhere"),
            ("local", "This device"),
            ("remote", "Kabin hosts"),
        ):
            choice = Gtk.CheckButton(label=label)
            if first is None:
                first = choice
            else:
                choice.set_group(first)
            choice.set_active(value == "all")
            choice.connect("toggled", self._on_location_filter_changed, value)
            content.append(choice)
            self.location_filters[value] = choice

        content.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.favorites_filter = Gtk.CheckButton(label="Favorites only")
        self.favorites_filter.connect("toggled", self._on_favorites_filter_changed)
        content.append(self.favorites_filter)
        popover.set_child(content)
        return popover

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

        self.details_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=36)
        self.details_content.set_halign(Gtk.Align.CENTER)
        self.details_content.set_valign(Gtk.Align.CENTER)
        self.details_content.set_margin_top(24)
        self.details_content.set_margin_bottom(48)
        self.details_content.set_margin_start(48)
        self.details_content.set_margin_end(48)

        self.details_art_frame = Gtk.Box()
        self.details_art_frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.details_art_frame.add_css_class("kabin-details-art-frame")
        self.details_art_frame.set_size_request(320, 430)
        self.details_picture = Gtk.Picture()
        self.details_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.details_art_frame.append(self.details_picture)
        self.details_content.append(self.details_art_frame)

        self.details_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.details_info.set_size_request(420, -1)
        self.details_info.set_valign(Gtk.Align.CENTER)

        self.details_title = Gtk.Label(xalign=0, wrap=True)
        self.details_title.add_css_class("kabin-details-title")
        self.details_title.add_css_class("title-1")
        self.details_info.append(self.details_title)

        self.details_meta = Gtk.Label(xalign=0, wrap=True)
        self.details_meta.add_css_class("kabin-details-meta")
        self.details_meta.add_css_class("dim-label")
        self.details_info.append(self.details_meta)

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

        self.details_more_button = Gtk.MenuButton(
            icon_name="view-more-symbolic",
            tooltip_text="More game actions",
        )
        self.details_more_button.add_css_class("kabin-icon-button")
        self.details_more_button.add_css_class("flat")
        more_popover = Gtk.Popover()
        more_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        more_content.set_margin_top(8)
        more_content.set_margin_bottom(8)
        more_content.set_margin_start(8)
        more_content.set_margin_end(8)
        hide_button = Gtk.Button(label="Hide from Library", icon_name="view-conceal-symbolic")
        hide_button.add_css_class("flat")
        hide_button.connect("clicked", self._hide_selected_game)
        more_content.append(hide_button)
        more_popover.set_child(more_content)
        self.details_more_button.set_popover(more_popover)

        action_row = Gtk.Box(spacing=8, halign=Gtk.Align.START)
        action_row.append(self.details_play_button)
        action_row.append(self.details_favorite_button)
        action_row.append(self.details_more_button)
        self.details_info.append(action_row)

        self.details_description = Gtk.Label(xalign=0, wrap=True)
        self.details_description.add_css_class("kabin-details-description")
        self.details_description.add_css_class("body")
        self.details_description.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.details_info.append(self.details_description)
        self.details_content.append(self.details_info)

        scroller.set_child(self.details_content)
        panel.append(scroller)

        return panel

    def _add_sidebar_header(self, text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_focusable(False)
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("kabin-sidebar-header")
        label.add_css_class("caption")
        label.add_css_class("dim-label")
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
            count_label.add_css_class("caption")
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
                status = self._host_statuses.get(host, {})
                state = status.get("state")
                badge = "Re-pair" if state == "auth" else ("Offline" if state == "offline" else count)
                icon = "network-offline" if state in ("auth", "offline") else "remote"
                self._add_sidebar_row(host, icon, badge, ("host", host))
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
            games, host_statuses = discover_all_with_status(self.config)
            GLib.idle_add(self._on_games_loaded, games, host_statuses)

        threading.Thread(target=worker, daemon=True).start()

    def _on_games_loaded(self, games, host_statuses=None):
        self._games = games
        self._host_statuses = host_statuses or {}
        self._rebuild_sidebar(games, preserve_category=self._category)
        self.game_store.remove_all()
        for game in games:
            self.game_store.append(GameItem(game))
        self._rebuild_recent_shelf(games)
        self._update_stack_visibility()
        self._update_library_header()

        if self.game_selection.get_n_items():
            self.game_selection.set_selected(0)
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
        filters_active = self._location_filter != "all" or self._favorites_only
        on_home = not self._search_text and not filters_active and self._category == CATEGORY_HOME
        self.recent_section.set_visible(self._has_recent and on_home)
        self.added_section.set_visible(self._has_added and on_home)
        self.favorite_section.set_visible(self._has_favorites and on_home)
        has_shelves = self._has_recent or self._has_added or self._has_favorites
        self.game_scroller.set_visible(not on_home or not has_shelves)

    # -- filtering & interaction -------------------------------------------

    def _matches_context(self, game) -> bool:
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

    def _matches(self, game) -> bool:
        if not self._matches_context(game):
            return False
        if self._favorites_only and not self.config.is_favorite(game.id):
            return False
        if self._location_filter == "local" and game.source == "remote":
            return False
        if self._location_filter == "remote" and game.source != "remote":
            return False
        return True

    def _filter_item(self, item: GameItem, *_user_data) -> bool:
        return self._matches(item.game)

    def _compare_items(self, item_a: GameItem, item_b: GameItem, *_user_data) -> int:
        game_a, game_b = item_a.game, item_b.game
        if self._sort_mode == "recent":
            recent = self.config.recent
            time_a = recent.get(game_a.id, 0)
            time_b = recent.get(game_b.id, 0)
            if time_a != time_b:
                return -1 if time_a > time_b else 1
        elif self._sort_mode == "added":
            time_a = game_a.extra.get("added_at", 0)
            time_b = game_b.extra.get("added_at", 0)
            if time_a != time_b:
                return -1 if time_a > time_b else 1
        key_a, key_b = game_a.sort_key, game_b.sort_key
        return -1 if key_a < key_b else (1 if key_a > key_b else 0)

    def _bind_game_tile(self, _factory, list_item):
        list_item.set_child(GameTile(list_item.get_item().game))

    def _unbind_game_tile(self, _factory, list_item):
        list_item.set_child(None)

    def _on_sort_changed(self, dropdown, _pspec):
        self._sort_mode = {0: "title", 1: "recent", 2: "added"}.get(
            dropdown.get_selected(), "title"
        )
        self.game_sorter.changed(Gtk.SorterChange.DIFFERENT)

    def _on_location_filter_changed(self, choice, value):
        if choice.get_active():
            self._location_filter = value
            self._apply_library_filters()

    def _on_favorites_filter_changed(self, choice):
        self._favorites_only = choice.get_active()
        self._apply_library_filters()

    def _apply_library_filters(self):
        active = self._location_filter != "all" or self._favorites_only
        if active:
            self.filter_button.add_css_class("kabin-filter-active")
        else:
            self.filter_button.remove_css_class("kabin-filter-active")
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._sync_selection_to_filter()

    def _update_stack_visibility(self):
        kind, value = self._category
        host_unavailable = (
            kind == "host"
            and self._host_statuses.get(value, {}).get("state") in ("auth", "offline")
        )
        if host_unavailable:
            self.content_stack.set_visible_child_name("no-matches")
        elif not self._games:
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
        context_count = sum(1 for game in self._games if self._matches_context(game))
        noun = "game" if count == 1 else "games"
        self.library_title.set_label(title)
        count_text = (
            f"{count} of {context_count} games"
            if count != context_count
            else f"{count} {noun}"
        )
        self.library_subtitle.set_label(f"{context} · {count_text}")
        if kind == "system" and count == 0:
            self.no_matches_status.set_title(f"No {title} games found")
            self.no_matches_status.set_description(
                "Add supported game files to this console library, then refresh Kabin."
            )
        elif kind == "host" and self._host_statuses.get(value, {}).get("state") != "online":
            status = self._host_statuses.get(value, {})
            state = status.get("state")
            title = "Pair with this host again" if state == "auth" else f"{value} is offline"
            description = (
                "Open Network & Hosts to pair again and verify this host's identity."
                if state == "auth"
                else "Check that Kabin Host is running on the other device, then use Refresh."
            )
            self.no_matches_status.set_title(title)
            self.no_matches_status.set_description(description)
        else:
            self.no_matches_status.set_title("No matches")
            self.no_matches_status.set_description(
                "Try a different search, category, or filter."
            )

    def _on_search_changed(self, entry):
        self._search_text = entry.get_text().strip().casefold()
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
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
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._sync_selection_to_filter()

    def _sync_selection_to_filter(self):
        selected = self.game_selection.get_selected_item()
        if selected and self._matches(selected.game):
            return

        if not self.game_selection.get_n_items():
            self.game_selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self._show_details(None)
        else:
            self.game_selection.set_selected(0)

    def _launch_game(self, game):
        if game.launch:
            self.config.record_played(game.id)
            self._rebuild_recent_shelf(self._games)
            game.launch()

    def _on_tile_activated(self, _grid, position):
        item = self.game_selection.get_item(position)
        if item:
            self._open_details(item.game)

    def _on_tile_selected(self, _selection, _pspec):
        item = self.game_selection.get_selected_item()
        self._show_details(item.game if item else None)

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
        if not self._matches(self._selected_game):
            self._close_details()
        self._apply_library_filters()

    def _hide_selected_game(self, _button):
        game = self._selected_game
        if not game:
            return
        self.details_more_button.popdown()
        self.config.hide(game.id, game.title)
        self._close_details()
        self.refresh()
        toast = Adw.Toast(title=f"Hidden {game.title}", button_label="Undo", timeout=5)
        toast.connect("button-clicked", self._undo_hidden_game, game.id)
        self.toast_overlay.add_toast(toast)

    def _undo_hidden_game(self, _toast, game_id):
        self.config.unhide(game_id)
        self.refresh()

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
        last_played = self.config.recent.get(game.id)
        if last_played:
            played_date = time.strftime("%b %d, %Y", time.localtime(last_played)).replace(" 0", " ")
            meta_parts.append(f"Last played {played_date}")

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
                host = game.extra["host"]
                _remote_artwork.request(
                    host,
                    host.get("token", ""),
                    game.extra["remote_id"],
                    lambda path: self._on_remote_details_art_ready(game, path),
                )

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
        self.config.save_window_state(self.get_width(), self.get_height(), self.is_maximized())
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
            self.game_grid.grab_focus()
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
