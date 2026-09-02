import queue
import threading
import time
from functools import lru_cache
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .artwork import fetch_openlibrary_cover, fetch_remote_cover, fetch_steamgriddb_cover  # noqa: E402
from .artwork_queue import ArtworkQueue  # noqa: E402
from .browse import first_index_for_prefix, pick_random_index  # noqa: E402
from .config import Config  # noqa: E402
from .cover_picker import CoverPicker  # noqa: E402
from .gamepad import GamepadMonitor, cycle_index, move_grid_index  # noqa: E402
from .home import (  # noqa: E402
    added_heading,
    continue_caption,
    continue_heading,
    continue_tile_scale,
    hero_meta_line,
    hero_uses_bleed,
    library_tile_scale,
    move_home_focus,
    show_library_sort,
    split_home_shelves,
)
from .kinds import CABINET_KIND, KINDS, count_noun, get_kind, kind_for  # noqa: E402
from .library import (  # noqa: E402
    CATEGORY_HOME,
    can_play_media,
    can_read_remote,
    compare_items,
    empty_state_message,
    file_details,
    library_group_for,
    local_path,
    play_count_label,
    rom_launch_summary,
    library_scope_filters,
    is_playing,
    item_progress,
    matches,
    matches_context,
    next_queue_index,
    play_button_label,
    queue_for,
    reader_progress_targets,
    related_items,
    resume_hint,
    sidebar_entries,
    sidebar_highlight_category,
)
from .media import MediaHelperError, MediaHelperSession, PlaybackSession, create_client_offer  # noqa: E402
from .network import (  # noqa: E402
    HostService,
    fetch_remote_media,
    prepare_remote_session,
    push_remote_progress,
    signal_remote_session,
)
from .playback import (  # noqa: E402
    adopt_progress,
    format_clock,
    helper_ready,
    playable_file,
    plays_in_kabin,
    resume_seconds,
    resume_track,
    save_progress,
    track_count,
)
from .reader import (  # noqa: E402
    HTML_READER_BACKENDS,
    PDF_RENDER_WIDTH,
    apply_reader_webview_settings,
    opens_in_kabin_reader,
    open_reader_pages,
    reader_backend_for,
    reader_cache_root,
    reader_uri_allowed,
    prune_remote_read_cache,
    remote_read_cache_path,
    remote_read_suffix,
    resume_page,
    resume_scroll,
    save_page_progress,
    scroll_adjustment,
    step_adjustment,
    sync_progress_from_remote,
    uses_tap_zones,
)
from .sessions import (  # noqa: E402
    PlaySession,
    format_play_time,
    quick_failure_message,
    recordable_seconds,
)
from .settings import SettingsWindow  # noqa: E402
from .sources import (  # noqa: E402
    discover_local_with_errors,
    discover_remote,
    remote_host_names,
)
from .sources import steam as steam_source  # noqa: E402


def _art_fit(kind) -> Gtk.ContentFit:
    return Gtk.ContentFit.CONTAIN if getattr(kind, "art_fit", "cover") == "contain" else Gtk.ContentFit.COVER


_SOURCE_BADGE_CANDIDATES = {
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
    "remote": ["network-server-symbolic", "network-workgroup-symbolic"],
    "network-offline": ["network-offline-symbolic", "network-error-symbolic"],
    "book": ["accessories-ebook-reader-symbolic", "x-office-document-symbolic", "text-x-generic-symbolic"],
    "comic": ["view-paged-symbolic", "x-office-document-symbolic", "text-x-generic-symbolic"],
    "music": ["audio-x-generic-symbolic", "folder-music-symbolic", "audio-headphones-symbolic"],
    "video": ["video-x-generic-symbolic", "video-display-symbolic", "camera-video-symbolic"],
    "tv": ["video-display-symbolic", "video-x-generic-symbolic", "camera-video-symbolic"],
}

_SIDEBAR_ICON_CANDIDATES = {
    "home": ["user-home-symbolic", "go-home-symbolic", "applications-games-symbolic"],
    "all": ["view-grid-symbolic", "applications-games-symbolic"],
    "favorites": ["starred-symbolic", "emblem-favorite-symbolic", "applications-games-symbolic"],
    "steam": ["steam-symbolic", "steam", "applications-games-symbolic"],
    "desktop": ["application-x-executable-symbolic", "applications-symbolic"],
    "roms": ["media-removable-symbolic", "applications-games-symbolic"],
    "remote": ["network-server-symbolic", "network-workgroup-symbolic"],
    "book": ["accessories-ebook-reader-symbolic", "x-office-document-symbolic", "text-x-generic-symbolic"],
    "comic": ["view-paged-symbolic", "x-office-document-symbolic", "text-x-generic-symbolic"],
    "music": ["audio-x-generic-symbolic", "folder-music-symbolic", "audio-headphones-symbolic"],
    "video": ["video-x-generic-symbolic", "video-display-symbolic", "camera-video-symbolic"],
    "tv": ["video-display-symbolic", "video-x-generic-symbolic", "camera-video-symbolic"],
}

_BRAND_MARK = Path(__file__).resolve().parent.parent / "data" / "kabin-mark.svg"

# Long enough to collapse a burst of typing into one re-filter, short
# enough that results still feel live.
SEARCH_DEBOUNCE_MS = 150

_KEY_ACTIONS = {
    Gdk.KEY_Left: "left",
    Gdk.KEY_Right: "right",
    Gdk.KEY_Up: "up",
    Gdk.KEY_Down: "down",
    Gdk.KEY_Return: "confirm",
    Gdk.KEY_KP_Enter: "confirm",
    Gdk.KEY_Escape: "back",
    Gdk.KEY_Page_Up: "prev",
    Gdk.KEY_Page_Down: "next",
    Gdk.KEY_F1: "options",
    Gdk.KEY_F2: "random",
}

_remote_artwork = ArtworkQueue(
    fetch_remote_cover,
    lambda callback, result: GLib.idle_add(callback, result),
)
_sgdb_artwork = ArtworkQueue(
    fetch_steamgriddb_cover,
    lambda callback, result: GLib.idle_add(callback, result),
)
_book_artwork = ArtworkQueue(
    fetch_openlibrary_cover,
    lambda callback, result: GLib.idle_add(callback, result),
)
_artwork_api_key = ""
_openlibrary_covers = True


def _queue_book_cover(game, callback):
    if not _openlibrary_covers:
        return
    author = game.creators[0] if game.creators else ""
    _book_artwork.request_job(
        ("openlibrary", game.id),
        (game.title, author, game.id),
        callback,
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
        self._expected_id = game.id
        self._dead = False
        self.picture.connect("destroy", lambda *_: setattr(self, "_dead", True))
        if game.icon_path:
            self.picture.set_filename(game.icon_path)
            return
        if game.source in {"steam", "remote"}:
            appid = game.extra.get("appid")
            if appid:
                cached_cover = icons.cached_path(appid)
                if cached_cover:
                    self.picture.set_filename(str(cached_cover))
                    return
                self._show_icon_plate(
                    Gio.ThemedIcon.new("network-server-symbolic")
                    if game.source == "remote"
                    else None
                )
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
        if kind_for(game).id == "book" and game.extra.get("needs_artwork"):
            gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
            self._show_icon_plate(gicon)
            _queue_book_cover(game, self._on_cover_ready)
            return
        if game.extra.get("needs_artwork") and _artwork_api_key:
            gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
            self._show_icon_plate(gicon)
            _sgdb_artwork.request_job(
                ("sgdb", game.id),
                (game.title, game.id, _artwork_api_key),
                self._on_cover_ready,
            )
            return
        gicon = game.gicon or (Gio.ThemedIcon.new(game.icon_name) if game.icon_name else None)
        self._show_icon_plate(gicon)

    def _still_current(self) -> bool:
        return not getattr(self, "_dead", False) and self.game.id == getattr(
            self, "_expected_id", None
        )

    def _apply_cover(self, path):
        if not path or not self._still_current():
            return False
        self.game.icon_path = str(path)
        self.game.extra["needs_artwork"] = False
        self.overlay.set_child(self.picture)
        self.picture.set_filename(str(path))
        return True

    def _on_remote_cover_ready(self, path):
        self._apply_cover(path)
        return False

    def _show_icon_plate(self, gicon):
        plate = Gtk.Box(hexpand=True, vexpand=True)
        plate.add_css_class("kabin-tile-plate")
        image = (
            Gtk.Image.new_from_gicon(gicon)
            if gicon
            else Gtk.Image.new_from_icon_name(kind_for(self.game).icon)
        )
        image.set_pixel_size(64)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        image.set_hexpand(True)
        image.set_vexpand(True)
        plate.append(image)
        self.overlay.set_child(plate)

    def _on_cover_ready(self, path):
        if not self._apply_cover(path) and self._still_current():
            self._show_icon_plate(Gio.ThemedIcon.new(kind_for(self.game).icon))
        return False

def _tile_subtitle(game) -> str:
    kind = kind_for(game)
    if game.creators:
        return game.creators[0]
    if game.series:
        return game.series
    if game.source == "remote":
        return game.subtitle or "Kabin Host"
    if game.source == "roms":
        return game.subtitle or "Console"
    if game.source == "steam":
        return "Steam"
    if kind.id != "game":
        return game.subtitle or kind.label
    return "Installed app"


def _progress_bar(value: float) -> Gtk.LevelBar:
    bar = Gtk.LevelBar()
    bar.set_mode(Gtk.LevelBarMode.CONTINUOUS)
    bar.set_min_value(0)
    bar.set_max_value(1)
    bar.set_value(max(0.0, min(1.0, value)))
    bar.add_css_class("kabin-progress")
    bar.set_hexpand(True)
    return bar


def _build_tile_content(
    game,
    kind=None,
    progress=0.0,
    playing=False,
    show_badge=True,
    subtitle=None,
    scale=1.0,
):
    """Build an artwork-first card with a stable, readable text footer."""
    kind = kind or CABINET_KIND
    tile_width = max(1, int(kind.tile_width * scale))
    tile_height = max(1, int(kind.tile_height * scale))
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    content.set_size_request(tile_width, -1)
    content.add_css_class(f"kabin-tile-{kind.shape}")
    content.add_css_class(f"kabin-kind-{kind.id}")
    if show_badge:
        content.add_css_class("kabin-tile-mixed")
    if playing:
        content.add_css_class("kabin-tile-playing")

    overlay = Gtk.Overlay()
    overlay.set_size_request(tile_width, tile_height)
    overlay.set_overflow(Gtk.Overflow.HIDDEN)
    overlay.add_css_class("kabin-tile-art")
    overlay.add_css_class(f"kabin-art-{kind.shape}")

    picture = Gtk.Picture()
    picture.set_content_fit(_art_fit(kind))
    overlay.set_child(picture)

    if show_badge:
        badge_key = game.source if game.source in _SOURCE_BADGE_CANDIDATES else kind.id
        badge_icon_name = _resolve_icon_name(
            tuple(_SOURCE_BADGE_CANDIDATES.get(badge_key, [kind.icon]))
        )
        badge = Gtk.Box(halign=Gtk.Align.END, valign=Gtk.Align.START)
        badge.add_css_class("kabin-tile-badge")
        badge_image = Gtk.Image.new_from_icon_name(badge_icon_name)
        badge_image.set_pixel_size(12)
        badge.append(badge_image)
        overlay.add_overlay(badge)
    if playing:
        now = Gtk.Label(label="Now playing")
        now.add_css_class("kabin-now-chip")
        now.set_halign(Gtk.Align.START)
        now.set_valign(Gtk.Align.START)
        now.set_margin_start(8)
        now.set_margin_top(8)
        overlay.add_overlay(now)
    if progress > 0:
        tick = _progress_bar(progress)
        tick.set_valign(Gtk.Align.END)
        overlay.add_overlay(tick)

    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    text.add_css_class("kabin-tile-text")
    title = Gtk.Label(label=game.title, xalign=0)
    title.set_wrap(True)
    title.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    title.set_lines(2)
    title.set_ellipsize(Pango.EllipsizeMode.END)
    title.set_tooltip_text(game.title)
    title.add_css_class("kabin-tile-title")
    title.add_css_class("heading")
    caption = subtitle if subtitle is not None else _tile_subtitle(game)
    subtitle = Gtk.Label(label=caption, xalign=0)
    subtitle.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle.add_css_class("kabin-tile-subtitle")
    subtitle.add_css_class("caption")
    subtitle.add_css_class("dim-label")
    subtitle.set_visible(bool(caption))
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
    def __init__(
        self,
        game,
        kind=None,
        progress=0.0,
        playing=False,
        show_badge=True,
        subtitle=None,
        scale=1.0,
    ):
        super().__init__()
        self.game = game
        self.set_focusable(False)
        self.set_overflow(Gtk.Overflow.VISIBLE)
        self.add_css_class("kabin-tile")
        self.add_css_class(f"kabin-kind-{(kind or kind_for(game)).id}")
        if playing:
            self.add_css_class("kabin-tile-playing")
        content, self._art = _build_tile_content(
            game, kind, progress, playing, show_badge, subtitle, scale
        )
        self.append(content)


def _build_shelf_button(
    game,
    on_activate,
    progress=0.0,
    playing=False,
    subtitle=None,
    scale=1.0,
    show_badge=True,
):
    caption = subtitle if subtitle is not None else _tile_subtitle(game)
    content, _art = _build_tile_content(
        game, kind_for(game), progress, playing, show_badge, caption, scale
    )
    button = Gtk.Button()
    button.set_overflow(Gtk.Overflow.VISIBLE)
    button.add_css_class("kabin-tile")
    button.add_css_class(f"kabin-kind-{kind_for(game).id}")
    button.add_css_class("flat")
    if playing:
        button.add_css_class("kabin-tile-playing")
    button.set_tooltip_text(f"{game.title} — {caption}")
    button.set_child(content)
    button._kabin_game = game
    button.connect("clicked", lambda *_: on_activate(game))
    return button


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()
        self.host_service = HostService(self.config, lambda: list(self._games))
        self._category = CATEGORY_HOME
        self._search_text = ""
        self._search_timeout = 0
        self._sidebar_rows = {}
        self._syncing_sidebar = False
        self._games = []
        self._host_statuses = {}
        self._has_recent = False
        self._has_added = False
        self._selected_game = None
        self._sort_mode = "title"
        self._location_filter = "all"
        self._favorites_only = False
        self._unplayed_only = False
        self._refresh_generation = 0
        self._stream_helper = None
        self._play_session = None
        self._play_session_source = None
        self._play_session_minimized = False
        self._playback = None
        self._playback_item = None
        self._playback_queue = []
        self._playback_index = 0
        self._playback_auth = None
        self._playback_poll_source = None
        self._seeking = False
        self._last_progress_save = 0.0
        self._player_art_path = None
        self._reader_item = None
        self._reader_backend = None
        self._reader_pages = None
        self._reader_page_count = 0
        self._reader_page_index = 0
        self._reader_pending_fragment = ""
        self._reader_pdf_width = 0
        self._reader_request = 0
        self._reader_return_stack = "library"
        self._reader_render_queue = queue.Queue()
        threading.Thread(target=self._reader_render_loop, daemon=True).start()
        self._closing = False
        self._nav_target = "home"
        self._home_focus_rows = []
        self._home_shelf_rows = []
        self._home_focus_pos = (0, 0)
        self._gamepad = GamepadMonitor(self._queue_cabinet_action)

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
            if self.host_service.error:
                self._toast(f"Kabin Host could not start · {self.host_service.error}")
        self.connect("close-request", self._on_close_request)

        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

    # -- UI construction ------------------------------------------------

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("kabin-topbar")

        brand_box = Gtk.Box(spacing=6)
        brand_box.add_css_class("kabin-brand")
        brand_icon = Gtk.Image.new_from_file(str(_BRAND_MARK))
        brand_icon.add_css_class("kabin-brand-mark")
        brand_word = Gtk.Label(label="KABIN")
        brand_word.add_css_class("kabin-brand-word")
        brand_word.add_css_class("heading")
        brand_box.append(brand_icon)
        brand_box.append(brand_word)
        header.pack_start(brand_box)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search titles…")
        self.search_entry.add_css_class("kabin-search")
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh · F5 · Guide",
        )
        refresh_button.add_css_class("kabin-icon-button")
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh_button)

        surprise_button = Gtk.Button(
            icon_name="media-playlist-shuffle-symbolic",
            tooltip_text="Surprise me · F2",
        )
        surprise_button.add_css_class("kabin-icon-button")
        surprise_button.add_css_class("flat")
        surprise_button.connect("clicked", lambda *_: self._surprise_selected())
        header.pack_start(surprise_button)

        self.filter_button = Gtk.MenuButton(
            icon_name="view-filter-symbolic",
            tooltip_text="Filter library",
        )
        self.filter_button.add_css_class("kabin-icon-button")
        self.filter_button.add_css_class("flat")
        self.filter_button.set_popover(self._build_filter_popover())
        header.pack_end(self.filter_button)

        self.sort_dropdown = Gtk.DropDown.new_from_strings(
            ["Title", "Recent", "Recently Added", "Most opened"]
        )
        self.sort_dropdown.set_tooltip_text("Sort by")
        self.sort_dropdown.add_css_class("kabin-sort")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        header.pack_end(self.sort_dropdown)

        settings_button = Gtk.Button(
            icon_name="emblem-system-symbolic",
            tooltip_text="Settings · Start",
        )
        settings_button.add_css_class("kabin-icon-button")
        settings_button.add_css_class("flat")
        settings_button.connect("clicked", lambda *_: self._open_settings())
        header.pack_end(settings_button)

        self.now_playing_button = Gtk.Button()
        self.now_playing_button.add_css_class("kabin-now-header")
        self.now_playing_button.set_visible(False)
        self.now_playing_button.set_tooltip_text("Jump to what’s playing")
        self.now_playing_label = Gtk.Label(label="Now playing", ellipsize=Pango.EllipsizeMode.END)
        self.now_playing_button.set_child(self.now_playing_label)
        self.now_playing_button.connect("clicked", self._open_playing_details)
        header.pack_end(self.now_playing_button)

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

        self.home_continue_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
        self.home_added_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)

        self.game_store = Gio.ListStore.new(GameItem)
        self.game_filter = Gtk.CustomFilter.new(self._filter_item)
        self.filtered_games = Gtk.FilterListModel.new(self.game_store, self.game_filter)
        self.game_sorter = Gtk.CustomSorter.new(self._compare_items)
        self.sorted_games = Gtk.SortListModel.new(self.filtered_games, self.game_sorter)
        self.game_selection = Gtk.SingleSelection.new(self.sorted_games)
        self.game_selection.set_autoselect(False)

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

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.add_css_class("kabin-content")
        self.hero_section = self._build_hero()
        content_box.append(self.hero_section)

        self.library_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
        self.library_column.set_margin_top(20)
        self.library_column.set_margin_bottom(32)
        self.library_column.set_margin_start(24)
        self.library_column.set_margin_end(24)
        self.library_header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.library_title = Gtk.Label(label="Library", xalign=0)
        self.library_title.add_css_class("kabin-library-title")
        self.library_subtitle = Gtk.Label(xalign=0)
        self.library_subtitle.add_css_class("kabin-library-subtitle")
        self.library_subtitle.add_css_class("dim-label")
        self.library_header.append(self.library_title)
        self.library_header.append(self.library_subtitle)
        self.library_column.append(self.library_header)
        self.game_scope = Gtk.Box(spacing=8)
        self.game_scope.add_css_class("kabin-scope-bar")
        self.game_scope_scroller = Gtk.ScrolledWindow(child=self.game_scope)
        self.game_scope_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.game_scope_scroller.set_visible(False)
        self.library_column.append(self.game_scope_scroller)
        self.filter_bar = Gtk.Box(spacing=8)
        self.filter_bar.add_css_class("kabin-filter-bar")
        self.filter_bar.set_visible(False)
        self.library_column.append(self.filter_bar)
        self.library_column.append(self.home_continue_box)
        self.library_column.append(self.home_added_box)
        self.grid_header = Gtk.Label(label="All titles", xalign=0)
        self.grid_header.add_css_class("kabin-shelf-header")
        self.grid_header.add_css_class("heading")
        self.library_column.append(self.grid_header)
        self.game_scroller = Gtk.ScrolledWindow(child=self.game_grid)
        self.game_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.game_scroller.set_hexpand(True)
        self.game_scroller.set_vexpand(True)
        self.game_scroller.add_css_class("kabin-game-scroller")
        self.library_column.append(self.game_scroller)
        content_box.append(self.library_column)
        self.page_scroller = Gtk.ScrolledWindow(child=content_box)
        self.page_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.page_scroller.set_hexpand(True)
        self.page_scroller.set_vexpand(True)
        self.page_scroller.set_propagate_natural_height(False)
        self.page_scroller.add_css_class("kabin-page-scroller")

        self.empty_status = Adw.StatusPage(
            title="Nothing here yet",
            description="Add Steam, a ROM folder, or books, comics, music, and movies in Settings.",
            icon_name="folder-symbolic",
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
        self.no_matches_actions = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.no_matches_clear_search = Gtk.Button(label="Clear search")
        self.no_matches_clear_search.connect("clicked", lambda *_: self._clear_search())
        self.no_matches_clear_filters = Gtk.Button(label="Clear filters")
        self.no_matches_clear_filters.connect("clicked", lambda *_: self._clear_filters())
        self.no_matches_actions.append(self.no_matches_clear_search)
        self.no_matches_actions.append(self.no_matches_clear_filters)
        self.no_matches_status.set_child(self.no_matches_actions)

        self.loading_status = Adw.StatusPage(
            title="Updating your library",
            description="Finding titles and refreshing artwork…",
            icon_name="view-refresh-symbolic",
        )
        self.loading_status.set_vexpand(True)
        self.loading_status.add_css_class("kabin-status")
        self.empty_status.add_css_class("kabin-status")
        self.no_matches_status.add_css_class("kabin-status")

        self.content_stack = Gtk.Stack()
        self.content_stack.add_css_class("kabin-library-stack")
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(180)
        self.content_stack.add_named(self.page_scroller, "games")
        self.content_stack.add_named(self.empty_status, "empty")
        self.content_stack.add_named(self.no_matches_status, "no-matches")
        self.content_stack.add_named(self.loading_status, "loading")

        self.main_stack = Gtk.Stack()
        self.main_stack.add_css_class("kabin-main-stack")
        self.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.main_stack.set_transition_duration(220)
        self.main_stack.add_named(self.content_stack, "library")
        self.main_stack.add_named(self._build_details_panel(), "details")
        self.main_stack.add_named(self._build_reader_panel(), "reader")

        self.bottom_stack = Gtk.Stack()
        self.bottom_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.bottom_stack.add_named(self._build_player_bar(), "player")
        self.bottom_stack.set_visible(False)
        toolbar_view.add_bottom_bar(self.bottom_stack)

        # A heavily downscaled artwork backdrop behind Kabin's own translucent
        # surface palette. Keeping it subtle prevents cover colors from
        # competing with navigation and text.
        self.backdrop_picture = Gtk.Picture()
        self.backdrop_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.backdrop_picture.set_can_shrink(True)
        self.backdrop_picture.add_css_class("kabin-backdrop")
        self.backdrop_scrim = Gtk.Box()
        self.backdrop_scrim.add_css_class("kabin-backdrop-scrim")
        self.backdrop_scrim.set_hexpand(True)
        self.backdrop_scrim.set_vexpand(True)

        body_overlay = Gtk.Overlay()
        body_overlay.set_child(self.backdrop_picture)
        body_overlay.add_overlay(self.backdrop_scrim)
        body_overlay.add_overlay(self.main_stack)

        content_page = Adw.NavigationPage(title="Library", child=body_overlay)
        content_page.add_css_class("kabin-content-page")
        split_view.set_content(content_page)

        toolbar_view.set_content(split_view)
        self.toast_overlay = Adw.ToastOverlay(child=toolbar_view)
        self.set_content(self.toast_overlay)

        compact = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 760px"))
        compact.add_setter(split_view, "collapsed", True)
        compact.add_setter(self.details_content, "orientation", Gtk.Orientation.VERTICAL)
        compact.add_setter(self.details_content, "spacing", 20)
        compact.add_setter(self.details_column, "margin-start", 20)
        compact.add_setter(self.details_column, "margin-end", 20)
        compact.add_setter(self.details_art_frame, "width-request", 240)
        compact.add_setter(self.details_art_frame, "height-request", 322)
        compact.add_setter(self.details_info, "width-request", -1)
        self.add_breakpoint(compact)
        self._apply_grid_metrics()

    def _build_player_bar(self):
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("kabin-player")
        bar.set_hexpand(True)

        now = Gtk.Button()
        now.add_css_class("flat")
        now.add_css_class("kabin-player-now")
        now.set_tooltip_text("Open the playing title")
        now.connect("clicked", self._open_playing_details)
        now_row = Gtk.Box(spacing=12)
        self.player_art = Gtk.Picture()
        self.player_art.set_can_shrink(True)
        player_art_frame = Gtk.Overlay()
        player_art_frame.set_size_request(52, 52)
        player_art_frame.set_hexpand(False)
        player_art_frame.set_vexpand(False)
        player_art_frame.set_halign(Gtk.Align.START)
        player_art_frame.set_valign(Gtk.Align.START)
        player_art_frame.set_overflow(Gtk.Overflow.HIDDEN)
        player_art_frame.add_css_class("kabin-player-art")
        player_art_frame.set_child(Gtk.Box())
        player_art_frame.add_overlay(self.player_art)
        now_row.append(player_art_frame)
        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        copy.set_size_request(180, -1)
        self.player_title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.player_title.add_css_class("heading")
        self.player_track = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.player_track.add_css_class("caption")
        self.player_track.add_css_class("dim-label")
        copy.append(self.player_title)
        copy.append(self.player_track)
        now_row.append(copy)
        now.set_child(now_row)
        bar.append(now)

        transport = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        self.player_prev = Gtk.Button(
            icon_name="media-skip-backward-symbolic", tooltip_text="Previous track"
        )
        self.player_prev.add_css_class("flat")
        self.player_prev.add_css_class("kabin-player-button")
        self.player_prev.connect("clicked", lambda *_: self._skip_playback(-1))
        self.player_pause = Gtk.Button(
            icon_name="media-playback-pause-symbolic", tooltip_text="Pause"
        )
        self.player_pause.add_css_class("kabin-player-button")
        self.player_pause.add_css_class("kabin-player-pause")
        self.player_pause.connect("clicked", lambda *_: self._toggle_playback_pause())
        self.player_next = Gtk.Button(
            icon_name="media-skip-forward-symbolic", tooltip_text="Next track"
        )
        self.player_next.add_css_class("flat")
        self.player_next.add_css_class("kabin-player-button")
        self.player_next.connect("clicked", lambda *_: self._skip_playback(1))
        self.player_rewind = Gtk.Button(label="−10")
        self.player_rewind.add_css_class("flat")
        self.player_rewind.add_css_class("kabin-player-skip")
        self.player_rewind.set_tooltip_text("Back 10 seconds")
        self.player_rewind.connect("clicked", lambda *_: self._nudge_playback(-10))
        self.player_forward = Gtk.Button(label="+10")
        self.player_forward.add_css_class("flat")
        self.player_forward.add_css_class("kabin-player-skip")
        self.player_forward.set_tooltip_text("Ahead 10 seconds")
        self.player_forward.connect("clicked", lambda *_: self._nudge_playback(10))
        transport.append(self.player_prev)
        transport.append(self.player_rewind)
        transport.append(self.player_pause)
        transport.append(self.player_forward)
        transport.append(self.player_next)
        bar.append(transport)

        self.player_elapsed = Gtk.Label(label="0:00")
        self.player_elapsed.add_css_class("caption")
        self.player_elapsed.add_css_class("kabin-player-time")
        bar.append(self.player_elapsed)

        self.player_seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.001)
        self.player_seek.set_draw_value(False)
        self.player_seek.set_hexpand(True)
        self.player_seek.connect("change-value", self._on_seek_change)
        release = Gtk.GestureClick()
        release.connect("released", lambda *_: self._finish_seek())
        self.player_seek.add_controller(release)
        bar.append(self.player_seek)

        self.player_remaining = Gtk.Label(label="0:00")
        self.player_remaining.add_css_class("caption")
        self.player_remaining.add_css_class("kabin-player-time")
        bar.append(self.player_remaining)

        stop = Gtk.Button(icon_name="media-playback-stop-symbolic", tooltip_text="Stop")
        stop.add_css_class("flat")
        stop.add_css_class("kabin-player-button")
        stop.connect("clicked", lambda *_: self._stop_playback())
        bar.append(stop)
        return bar

    def _build_shelf(self, title, min_height=300):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header = Gtk.Label(label=title, xalign=0)
        header.add_css_class("kabin-kicker")
        header.add_css_class("kabin-shelf-header")
        section.append(header)
        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("kabin-shelf-rail")
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroller.set_propagate_natural_width(False)
        scroller.set_min_content_height(min_height)
        shelf = Gtk.Box(spacing=16)
        shelf.add_css_class("kabin-shelf-row")
        scroller.set_child(shelf)
        section.append(scroller)
        section.set_visible(False)
        return section, shelf

    def _build_hero(self):
        hero = Gtk.Box()
        hero.add_css_class("kabin-hero")
        hero.set_overflow(Gtk.Overflow.HIDDEN)
        overlay = Gtk.Overlay()
        overlay.set_size_request(-1, 360)
        overlay.set_hexpand(True)
        self.hero_picture = Gtk.Picture()
        self.hero_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.hero_picture.set_can_shrink(True)
        self.hero_picture.add_css_class("kabin-hero-bleed")
        overlay.set_child(self.hero_picture)

        row = Gtk.Box(spacing=24)
        row.set_valign(Gtk.Align.END)
        row.set_hexpand(True)
        row.add_css_class("kabin-hero-row")
        self.hero_poster = Gtk.Picture()
        self.hero_poster.set_content_fit(Gtk.ContentFit.COVER)
        self.hero_poster.set_can_shrink(True)
        self.hero_poster.set_overflow(Gtk.Overflow.HIDDEN)
        self.hero_poster.add_css_class("kabin-hero-poster")
        self.hero_poster.set_size_request(168, 252)
        row.append(self.hero_poster)

        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        copy.set_valign(Gtk.Align.END)
        copy.set_hexpand(True)
        copy.add_css_class("kabin-hero-copy")
        self.hero_kicker = Gtk.Label(xalign=0)
        self.hero_kicker.add_css_class("kabin-kicker")
        self.hero_kicker.add_css_class("kabin-hero-kicker")
        self.hero_kicker.add_css_class("caption")
        self.hero_title = Gtk.Label(xalign=0)
        self.hero_title.add_css_class("kabin-hero-title")
        self.hero_title.add_css_class("title-1")
        self.hero_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.hero_meta = Gtk.Label(xalign=0)
        self.hero_meta.add_css_class("kabin-hero-meta")
        self.hero_meta.add_css_class("dim-label")
        copy.append(self.hero_kicker)
        copy.append(self.hero_title)
        copy.append(self.hero_meta)
        self.hero_progress = _progress_bar(0)
        self.hero_progress.set_margin_top(4)
        self.hero_progress.set_visible(False)
        copy.append(self.hero_progress)
        actions = Gtk.Box(spacing=8)
        self.hero_play = Gtk.Button(label="Play")
        self.hero_play.add_css_class("suggested-action")
        self.hero_play.add_css_class("kabin-hero-play")
        self.hero_play.connect("clicked", self._on_hero_play)
        self.hero_open = Gtk.Button(label="Details")
        self.hero_open.add_css_class("kabin-hero-open")
        self.hero_open.connect("clicked", self._on_hero_clicked)
        actions.append(self.hero_play)
        actions.append(self.hero_open)
        copy.append(actions)
        row.append(copy)
        overlay.add_overlay(row)
        hero.append(overlay)
        hero.set_visible(False)
        self._featured_item = None
        return hero

    def _build_filter_popover(self):
        popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        heading = Gtk.Label(label="Show titles from", xalign=0)
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
        self.unplayed_filter = Gtk.CheckButton(label="Not opened yet")
        self.unplayed_filter.connect("toggled", self._on_unplayed_filter_changed)
        content.append(self.unplayed_filter)
        popover.set_child(content)
        return popover

    def _build_details_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("kabin-details-page")

        back_button = Gtk.Button(child=Adw.ButtonContent(icon_name="go-previous-symbolic", label="Library"))
        back_button.set_halign(Gtk.Align.START)
        back_button.add_css_class("flat")
        back_button.add_css_class("kabin-details-back")
        back_button.connect("clicked", lambda *_: self._close_details())
        panel.append(back_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        self.details_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        self.details_content.set_halign(Gtk.Align.START)
        self.details_content.set_valign(Gtk.Align.START)

        self.details_picture = Gtk.Picture()
        self.details_picture.set_can_shrink(True)
        self.details_picture.set_hexpand(True)
        self.details_picture.set_vexpand(True)
        self.details_picture.set_content_fit(Gtk.ContentFit.COVER)
        self.details_art_plate = Gtk.Box()
        self.details_art_plate.set_size_request(320, 430)
        self.details_art_frame = Gtk.Overlay()
        self.details_art_frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.details_art_frame.set_hexpand(False)
        self.details_art_frame.set_vexpand(False)
        self.details_art_frame.set_halign(Gtk.Align.START)
        self.details_art_frame.set_valign(Gtk.Align.START)
        self.details_art_frame.add_css_class("kabin-details-art-frame")
        self.details_art_frame.add_css_class("kabin-art-portrait")
        self.details_art_frame.set_size_request(320, 430)
        self.details_art_frame.set_child(self.details_art_plate)
        self.details_art_frame.add_overlay(self.details_picture)
        self.details_content.append(self.details_art_frame)

        self.details_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.details_info.set_size_request(420, -1)
        self.details_info.set_hexpand(True)
        self.details_info.set_valign(Gtk.Align.START)

        self.details_kind_chip = Gtk.Label(xalign=0)
        self.details_kind_chip.add_css_class("kabin-kicker")
        self.details_kind_chip.add_css_class("kabin-details-kicker")
        self.details_kind_chip.set_halign(Gtk.Align.START)
        self.details_now_chip = Gtk.Label(label="Now playing")
        self.details_now_chip.add_css_class("kabin-now-chip")
        self.details_now_chip.set_halign(Gtk.Align.START)
        self.details_now_chip.set_visible(False)
        kickers = Gtk.Box(spacing=10)
        kickers.append(self.details_kind_chip)
        kickers.append(self.details_now_chip)
        self.details_info.append(kickers)

        self.details_title = Gtk.Label(xalign=0, wrap=True)
        self.details_title.add_css_class("kabin-details-title")
        self.details_info.append(self.details_title)

        self.details_meta = Gtk.Label(xalign=0, wrap=True)
        self.details_meta.add_css_class("kabin-details-meta")
        self.details_meta.add_css_class("dim-label")
        self.details_info.append(self.details_meta)

        self.details_progress = _progress_bar(0)
        self.details_progress.set_visible(False)
        self.details_info.append(self.details_progress)

        self.details_play_button = Gtk.Button(label="Play")
        self.details_play_button.add_css_class("suggested-action")
        self.details_play_button.connect("clicked", lambda *_: self._launch_selected())

        self.details_favorite_icon = Gtk.Image.new_from_icon_name("non-starred-symbolic")
        self.details_favorite_button = Gtk.Button()
        self.details_favorite_button.set_child(self.details_favorite_icon)
        self.details_favorite_button.add_css_class("kabin-icon-button")
        self.details_favorite_button.add_css_class("flat")
        self.details_favorite_button.connect("clicked", lambda *_: self._toggle_favorite_selected())

        self.details_more_button = Gtk.MenuButton(
            icon_name="view-more-symbolic",
            tooltip_text="More",
        )
        self.details_more_button.add_css_class("kabin-icon-button")
        self.details_more_button.add_css_class("flat")
        more_popover = Gtk.Popover()
        more_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        more_content.set_margin_top(8)
        more_content.set_margin_bottom(8)
        more_content.set_margin_start(8)
        more_content.set_margin_end(8)
        cover_button = Gtk.Button(child=Adw.ButtonContent(icon_name="image-x-generic-symbolic", label="Change cover"))
        cover_button.add_css_class("flat")
        cover_button.connect("clicked", self._change_selected_cover)
        hide_button = Gtk.Button(child=Adw.ButtonContent(icon_name="view-conceal-symbolic", label="Hide from Library"))
        hide_button.add_css_class("flat")
        hide_button.connect("clicked", self._hide_selected_game)
        self.details_open_folder_button = Gtk.Button(
            child=Adw.ButtonContent(icon_name="folder-open-symbolic", label="Open folder")
        )
        self.details_open_folder_button.add_css_class("flat")
        self.details_open_folder_button.connect("clicked", self._open_selected_folder)
        more_content.append(cover_button)
        more_content.append(self.details_open_folder_button)
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
        self.details_tracks = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.details_tracks.add_css_class("kabin-track-list")
        self.details_tracks.set_visible(False)
        self.details_info.append(self.details_tracks)
        self.details_content.append(self.details_info)

        self.details_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
        self.details_column.set_margin_top(8)
        self.details_column.set_margin_bottom(40)
        self.details_column.set_margin_start(32)
        self.details_column.set_margin_end(32)
        self.details_column.append(self.details_content)

        self.details_related_section, self.details_related_shelf = self._build_shelf(
            "More in this series", 280
        )
        self.details_related_header = self.details_related_section.get_first_child()
        self.details_column.append(self.details_related_section)

        scroller.set_child(self.details_column)
        panel.append(scroller)

        return panel

    def _build_reader_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel.add_css_class("kabin-reader-page")

        header = Gtk.Box(spacing=8)
        header.add_css_class("kabin-reader-header")
        back_button = Gtk.Button(child=Adw.ButtonContent(icon_name="go-previous-symbolic", label="Back"))
        back_button.add_css_class("flat")
        back_button.add_css_class("kabin-reader-back")
        back_button.connect("clicked", lambda *_: self._close_reader())
        header.append(back_button)

        self.reader_title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.reader_title.add_css_class("heading")
        self.reader_title.set_hexpand(True)
        header.append(self.reader_title)

        toc_icon = _resolve_icon_name(
            ("view-list-symbolic", "format-justify-fill-symbolic", "text-x-generic-symbolic")
        )
        self.reader_toc_button = Gtk.MenuButton(icon_name=toc_icon, tooltip_text="Chapters")
        self.reader_toc_button.add_css_class("kabin-icon-button")
        self.reader_toc_button.add_css_class("flat")
        self.reader_toc_button.set_visible(False)
        header.append(self.reader_toc_button)

        self.reader_page_label = Gtk.Label()
        self.reader_page_label.add_css_class("caption")
        self.reader_page_label.add_css_class("dim-label")
        header.append(self.reader_page_label)
        panel.append(header)

        self.reader_picture = Gtk.Picture()
        self.reader_picture.set_can_shrink(True)
        self.reader_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.reader_picture.set_hexpand(True)
        self.reader_picture.set_vexpand(True)
        self.reader_picture.add_css_class("kabin-reader-picture")
        self.reader_picture.connect("notify::width", self._on_reader_pdf_size)
        self.reader_picture.connect("notify::height", self._on_reader_pdf_size)

        self.reader_status = Adw.StatusPage(title="Opening…", icon_name="view-paged-symbolic")
        self.reader_status.set_vexpand(True)

        self.reader_text_view = Gtk.TextView()
        self.reader_text_view.set_editable(False)
        self.reader_text_view.set_cursor_visible(False)
        self.reader_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.reader_text_view.add_css_class("kabin-reader-text")
        self.reader_text_view.set_left_margin(48)
        self.reader_text_view.set_right_margin(48)
        self.reader_text_view.set_top_margin(32)
        self.reader_text_view.set_bottom_margin(32)
        self.reader_text_scroller = Gtk.ScrolledWindow()
        self.reader_text_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.reader_text_scroller.set_child(self.reader_text_view)

        self.reader_content_stack = Gtk.Stack()
        self.reader_content_stack.add_named(self.reader_status, "status")
        self.reader_content_stack.add_named(self.reader_picture, "page")
        self.reader_content_stack.add_named(self.reader_text_scroller, "text")
        self.reader_webview = None

        self.reader_prev_zone = Gtk.Button()
        self.reader_prev_zone.add_css_class("flat")
        self.reader_prev_zone.add_css_class("kabin-reader-zone")
        self.reader_prev_zone.set_hexpand(True)
        self.reader_prev_zone.set_vexpand(True)
        self.reader_prev_zone.set_tooltip_text("Previous page")
        self.reader_prev_zone.connect("clicked", lambda *_: self._reader_turn(-1))

        self.reader_next_zone = Gtk.Button()
        self.reader_next_zone.add_css_class("flat")
        self.reader_next_zone.add_css_class("kabin-reader-zone")
        self.reader_next_zone.set_hexpand(True)
        self.reader_next_zone.set_vexpand(True)
        self.reader_next_zone.set_tooltip_text("Next page")
        self.reader_next_zone.connect("clicked", lambda *_: self._reader_turn(1))

        self.reader_zones = Gtk.Box(spacing=0)
        self.reader_zones.set_hexpand(True)
        self.reader_zones.set_vexpand(True)
        self.reader_zones.append(self.reader_prev_zone)
        self.reader_zones.append(self.reader_next_zone)

        overlay = Gtk.Overlay()
        overlay.set_child(self.reader_content_stack)
        overlay.add_overlay(self.reader_zones)
        overlay.set_vexpand(True)
        panel.append(overlay)

        bottom = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        bottom.add_css_class("kabin-reader-pager")
        self.reader_prev_button = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous page")
        self.reader_prev_button.add_css_class("kabin-icon-button")
        self.reader_prev_button.add_css_class("flat")
        self.reader_prev_button.connect("clicked", lambda *_: self._reader_turn(-1))
        self.reader_seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.reader_seek.set_draw_value(False)
        self.reader_seek.set_size_request(320, -1)
        self.reader_seek.connect("change-value", self._on_reader_seek_change)
        self.reader_next_button = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next page")
        self.reader_next_button.add_css_class("kabin-icon-button")
        self.reader_next_button.add_css_class("flat")
        self.reader_next_button.connect("clicked", lambda *_: self._reader_turn(1))
        bottom.append(self.reader_prev_button)
        bottom.append(self.reader_seek)
        bottom.append(self.reader_next_button)
        panel.append(bottom)

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
        row.add_css_class("kabin-sidebar-item")
        row.set_child(content)
        self.sidebar_list.append(row)
        self._sidebar_rows[row] = category

    def _rebuild_sidebar(self, games, preserve_category=None):
        self.sidebar_list.remove_all()
        self._sidebar_rows = {}
        for entry in sidebar_entries(games, self.config, self._host_statuses):
            if entry.kind == "header":
                self._add_sidebar_header(entry.label)
            else:
                self._add_sidebar_row(entry.label, entry.icon_key, entry.count, entry.category)

        target_category = sidebar_highlight_category(
            preserve_category if preserve_category is not None else CATEGORY_HOME
        )
        target_row = next(
            (row for row, category in self._sidebar_rows.items() if category == target_category),
            None,
        )
        fallback = next(
            (row for row, category in self._sidebar_rows.items() if category == CATEGORY_HOME), None
        )
        self._syncing_sidebar = True
        self.sidebar_list.select_row(target_row or fallback)
        self._syncing_sidebar = False
        self._update_game_scope()

    # -- data loading -----------------------------------------------------

    def refresh(self):
        global _artwork_api_key, _openlibrary_covers
        self.config.load()
        _artwork_api_key = self.config.artwork.get("steamgriddb_api_key", "")
        _openlibrary_covers = bool(self.config.artwork.get("openlibrary_covers", True))
        self._refresh_generation += 1
        generation = self._refresh_generation
        if hasattr(self, "content_stack"):
            self._close_details()
            self.content_stack.set_visible_child_name("loading")
            self.loading_status.set_description("Finding titles on this device…")

        def worker():
            # Local sources first, so a paired host that's powered off (a
            # full connect timeout per host) never keeps this device's own
            # titles behind "Updating your library…".
            try:
                games, scan_errors = discover_local_with_errors(self.config)
            except Exception as exc:
                GLib.idle_add(self._on_games_load_failed, generation, exc)
                return
            pending_hosts = remote_host_names(self.config)
            checking = {
                name: {"state": "checking", "message": "Checking…"} for name in pending_hosts
            }
            GLib.idle_add(self._on_games_loaded, generation, games, checking)
            if scan_errors:
                GLib.idle_add(self._report_scan_errors, generation, scan_errors)
            if not pending_hosts:
                return
            remote_games, host_statuses = discover_remote(self.config)
            GLib.idle_add(self._on_remote_loaded, generation, remote_games, host_statuses)

        threading.Thread(target=worker, daemon=True).start()

    def _on_games_load_failed(self, generation, error):
        # Without this, one bad item anywhere in the scan (a file deleted
        # out from under a Syncthing-synced media folder between being
        # listed and stat()'d, a malformed reply from a paired host, ...)
        # raises inside the daemon worker thread, which just dies -
        # _on_games_loaded never runs, and the library is stuck on
        # "Updating your library…" forever with no error shown. Fall back
        # to whatever was already loaded instead of hanging.
        if generation != self._refresh_generation:
            return False
        self._toast(f"Could not refresh your library · {error}")
        if hasattr(self, "content_stack"):
            self._update_stack_visibility()
        return False

    def _report_scan_errors(self, generation, errors):
        """One toast per source that blew up mid-scan. Without this a
        permission error or bad path empties a whole section with no hint."""
        if generation != self._refresh_generation:
            return False
        for label, detail in errors.items():
            self._toast(f"Couldn't scan {label} · {detail}")
        return False

    def _on_games_loaded(self, generation, games, host_statuses=None):
        if generation != self._refresh_generation:
            return False
        self._games = games
        self._host_statuses = host_statuses or {}
        for game in games:
            if game.source == "remote":
                adopt_progress(self.config, game.id, game.extra.get("progress"))
        sync_progress_from_remote(games, self.config)
        self._rebuild_sidebar(games, preserve_category=self._category)
        self.game_store.remove_all()
        for game in games:
            self.game_store.append(GameItem(game))
        self._apply_grid_metrics()
        self._rebuild_recent_shelf(games)
        self._update_stack_visibility()
        self._update_library_header()
        self._update_filter_bar()
        self._update_game_scope()

        if (
            self.game_selection.get_n_items()
            and self.main_stack.get_visible_child_name() == "details"
        ):
            self.game_selection.set_selected(0)
        else:
            self.game_selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self._show_details(None)
        if not self._search_text:
            self._set_nav_target(self._library_nav_target(), show_focus=False)
        return False

    def _on_remote_loaded(self, generation, remote_games, host_statuses):
        """Second half of refresh(): fold paired hosts' catalogs into the
        already-visible local library without disturbing what the user is
        looking at (selection, details, Home focus)."""
        if generation != self._refresh_generation:
            return False
        for game in remote_games:
            adopt_progress(self.config, game.id, game.extra.get("progress"))
        games = [game for game in self._games if game.source != "remote"] + list(remote_games)
        games.sort(key=lambda g: g.sort_key)
        self._games = games
        self._host_statuses = host_statuses or {}
        if remote_games:
            sync_progress_from_remote(games, self.config)
        self._rebuild_sidebar(games, preserve_category=self._category)
        for game in remote_games:
            self.game_store.append(GameItem(game))
        if remote_games:
            self._rebuild_recent_shelf(games)
        self._update_stack_visibility()
        self._update_library_header()
        self._update_filter_bar()
        self._update_game_scope()
        return False

    def _clear_box(self, box):
        while (child := box.get_first_child()) is not None:
            box.remove(child)

    def _fill_kind_shelf(self, parent, title, items, kind, *, resume=False):
        scale = continue_tile_scale(len(items)) if resume else 1.0
        section, shelf = self._build_shelf(
            title, int(kind.tile_height * scale) + 72
        )
        buttons = []
        for game in items:
            button = _build_shelf_button(
                game,
                self._start_item if resume else self._open_details,
                self._item_progress(game),
                self._is_playing(game),
                subtitle=self._continue_caption(game) if resume else None,
                scale=scale,
                show_badge=False,
            )
            shelf.append(button)
            buttons.append(button)
        section.set_visible(True)
        parent.append(section)
        if buttons:
            self._home_shelf_rows.append(buttons)

    def _rebuild_recent_shelf(self, games):
        self._clear_box(self.home_continue_box)
        self._clear_box(self.home_added_box)
        self._home_shelf_rows = []

        featured, _kicker = self._pick_featured(games)
        continue_rows, added_rows = split_home_shelves(
            games,
            self.config.recent_ids(limit=24),
            featured.id if featured else None,
        )
        for kind, items in continue_rows:
            self._fill_kind_shelf(
                self.home_continue_box,
                continue_heading(kind),
                items,
                kind,
                resume=True,
            )
        for kind, items in added_rows:
            self._fill_kind_shelf(
                self.home_added_box, added_heading(kind), items, kind
            )

        self._has_recent = bool(continue_rows)
        self._has_added = bool(added_rows)
        self._rebuild_hero(games)
        self._home_focus_rows = []
        if featured and hasattr(self, "hero_play"):
            self._home_focus_rows.append([self.hero_play, self.hero_open])
        self._home_focus_rows.extend(self._home_shelf_rows)
        self._update_recent_visibility()

    def _pick_featured(self, games):
        if self._playback_item:
            return self._playback_item, "Now playing"
        by_id = {item.id: item for item in games}
        for game_id in self.config.recent_ids(limit=8):
            if game_id in by_id:
                return by_id[game_id], "Continue"
        favorites = [item for item in games if self.config.is_favorite(item.id)]
        if favorites:
            return favorites[0], "Favorite"
        added = sorted(
            (item for item in games if item.extra.get("added_at")),
            key=lambda item: item.extra["added_at"],
            reverse=True,
        )
        if added:
            return added[0], "Just added"
        if games:
            return games[0], "Featured"
        return None, ""

    def _rebuild_hero(self, games):
        featured, kicker = self._pick_featured(games)
        self._featured_item = featured
        if not featured:
            self.hero_picture.set_paintable(None)
            self.hero_poster.set_paintable(None)
            if hasattr(self, "hero_section"):
                for css_class in list(self.hero_section.get_css_classes()):
                    if css_class.startswith("kabin-kind-") or css_class == "kabin-hero-quiet":
                        self.hero_section.remove_css_class(css_class)
            return
        kind = kind_for(featured)
        self.hero_kicker.set_label(kicker)
        self.hero_title.set_label(featured.title)
        meta = hero_meta_line(featured) or _tile_subtitle(featured)
        self.hero_meta.set_label(meta)
        self.hero_meta.set_visible(bool(meta))
        ratio = self._item_progress(featured)
        self.hero_progress.set_value(ratio)
        self.hero_progress.set_visible(ratio > 0)
        if hasattr(self, "hero_play"):
            if self._is_playing(featured):
                self.hero_play.set_label("Pause" if self._playback and not self._playback.paused else "Resume")
            elif (plays_in_kabin(featured) and self._can_play_media(featured)) or self._opens_in_reader(featured):
                self.hero_play.set_label(self._play_button_label(featured))
            else:
                self.hero_play.set_label(kind.verb)
        self.hero_poster.set_size_request(kind.tile_width, kind.tile_height)
        self.hero_poster.set_content_fit(_art_fit(kind))
        for css_class in list(self.hero_section.get_css_classes()):
            if css_class.startswith("kabin-kind-") or css_class == "kabin-hero-quiet":
                self.hero_section.remove_css_class(css_class)
        self.hero_section.add_css_class(f"kabin-kind-{kind.id}")
        bleed = hero_uses_bleed(kind)
        if not bleed:
            self.hero_section.add_css_class("kabin-hero-quiet")
        self.hero_picture.set_visible(bleed)
        if featured.icon_path:
            if bleed:
                self.hero_picture.set_filename(featured.icon_path)
            else:
                self.hero_picture.set_paintable(None)
            self.hero_poster.set_filename(featured.icon_path)
        else:
            self.hero_picture.set_paintable(None)
            self.hero_poster.set_paintable(None)
        self.hero_play._kabin_game = featured
        self.hero_open._kabin_game = featured

    def _on_hero_clicked(self, *_args):
        if self._featured_item:
            self._open_details(self._featured_item)

    def _on_hero_play(self, *_args):
        self._start_item(self._featured_item)

    def _start_item(self, game):
        if not game:
            return
        if plays_in_kabin(game) and self._can_play_media(game):
            self._play_media(game)
        elif self._opens_in_reader(game):
            self._open_reader(game)
        elif game.source == "remote":
            self._open_details(game)
        else:
            self._launch_game(game)

    def _continue_caption(self, game) -> str:
        clock = ""
        tracks = 1
        track = 0
        if plays_in_kabin(game):
            tracks = track_count(game)
            track = resume_track(self.config, game.id, tracks)
            start = resume_seconds(self.config, game.id)
            if start:
                clock = format_clock(start)
        elif opens_in_kabin_reader(game):
            page = resume_page(self.config, game.id)
            if page:
                clock = f"p. {page + 1}"
        return continue_caption(
            playing=self._is_playing(game),
            track=track,
            tracks=tracks,
            clock=clock,
            opened_at=self.config.recent.get(game.id) or 0,
            fallback=kind_for(game).last_opened,
        )

    def _is_on_home(self) -> bool:
        filters_active = (
            self._location_filter != "all" or self._favorites_only or self._unplayed_only
        )
        return (
            not self._search_text
            and not filters_active
            and self._category == CATEGORY_HOME
        )

    def _library_nav_target(self) -> str:
        return "home" if self._is_on_home() else "grid"

    def _update_recent_visibility(self):
        filters_active = (
            self._location_filter != "all" or self._favorites_only or self._unplayed_only
        )
        on_home = self._is_on_home()
        self.home_continue_box.set_visible(self._has_recent and on_home)
        self.home_added_box.set_visible(self._has_added and on_home)
        if hasattr(self, "hero_section"):
            self.hero_section.set_visible(bool(self._featured_item) and on_home)
        if hasattr(self, "library_column"):
            self.library_column.set_margin_top(8 if on_home and self._featured_item else 20)
        show_grid = not on_home
        if hasattr(self, "grid_header"):
            self.grid_header.set_visible(False)
        self.game_scroller.set_visible(show_grid)
        self.game_scroller.set_vexpand(show_grid)
        if hasattr(self, "library_header"):
            self.library_header.set_visible(not on_home)
        if on_home:
            self.remove_css_class("kabin-on-library")
            if hasattr(self, "backdrop_scrim"):
                self.backdrop_scrim.remove_css_class("kabin-backdrop-library")
        else:
            self.add_css_class("kabin-on-library")
            if hasattr(self, "backdrop_scrim"):
                self.backdrop_scrim.add_css_class("kabin-backdrop-library")
        if hasattr(self, "sort_dropdown"):
            count = sum(1 for game in self._games if self._matches(game))
            self.sort_dropdown.set_visible(show_grid and show_library_sort(count))
        if hasattr(self, "filter_button"):
            self.filter_button.set_visible(show_grid or filters_active)
        self._sync_library_nav()

    # -- filtering & interaction -------------------------------------------

    def _matches_context(self, game) -> bool:
        return matches_context(game, self._search_text, self._category, self.config)

    def _matches(self, game) -> bool:
        return matches(
            game,
            self._search_text,
            self._category,
            self.config,
            favorites_only=self._favorites_only,
            unplayed_only=self._unplayed_only,
            location_filter=self._location_filter,
        )

    def _filter_item(self, item: GameItem, *_user_data) -> bool:
        return self._matches(item.game)

    def _compare_items(self, item_a: GameItem, item_b: GameItem, *_user_data) -> int:
        return compare_items(item_a.game, item_b.game, self._sort_mode, self.config)

    def _bind_game_tile(self, _factory, list_item):
        game = list_item.get_item().game
        kind, _value = self._category
        caption = None
        if kind in ("system", "source", "host"):
            caption = (game.creators[0] if game.creators else game.series) or ""
        list_item.set_child(
            GameTile(
                game,
                self._tile_kind(),
                self._item_progress(game),
                self._is_playing(game),
                kind not in ("type", "system", "source", "host") or bool(self._search_text),
                caption,
                self._library_tile_scale(),
            )
        )

    def _unbind_game_tile(self, _factory, list_item):
        list_item.set_child(None)

    def _on_sort_changed(self, dropdown, _pspec):
        self._sort_mode = {0: "title", 1: "recent", 2: "added", 3: "opened"}.get(
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

    def _on_unplayed_filter_changed(self, choice):
        self._unplayed_only = choice.get_active()
        self._apply_library_filters()

    def _apply_library_filters(self):
        active = (
            self._location_filter != "all"
            or self._favorites_only
            or self._unplayed_only
        )
        if active:
            self.filter_button.add_css_class("kabin-filter-active")
        else:
            self.filter_button.remove_css_class("kabin-filter-active")
        self._apply_grid_metrics()
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._update_filter_bar()
        self._sync_selection_to_filter()

    def _clear_search(self):
        self.search_entry.set_text("")
        # An explicit "Clear search" click should land immediately rather
        # than after the typing debounce.
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
            self._search_timeout = 0
        self._apply_search()

    def _clear_filters(self):
        self._location_filter = "all"
        if "all" in self.location_filters:
            self.location_filters["all"].set_active(True)
        self.favorites_filter.set_active(False)
        self.unplayed_filter.set_active(False)
        self._favorites_only = False
        self._unplayed_only = False
        self._apply_library_filters()

    def _add_filter_chip(self, label: str, on_remove):
        chip = Gtk.Button(label=label)
        chip.add_css_class("kabin-filter-chip")
        chip.set_tooltip_text(f"Remove {label}")
        chip.connect("clicked", lambda *_: on_remove())
        self.filter_bar.append(chip)

    def _update_filter_bar(self):
        if not hasattr(self, "filter_bar"):
            return
        while (child := self.filter_bar.get_first_child()) is not None:
            self.filter_bar.remove(child)
        if self._search_text:
            self._add_filter_chip(f"“{self.search_entry.get_text().strip()}”", self._clear_search)
        if self._location_filter == "local":
            self._add_filter_chip("This device", self._clear_filters)
        elif self._location_filter == "remote":
            self._add_filter_chip("Kabin hosts", self._clear_filters)
        if self._favorites_only:
            self._add_filter_chip("Favorites", lambda: self.favorites_filter.set_active(False))
        if self._unplayed_only:
            self._add_filter_chip("Not opened yet", lambda: self.unplayed_filter.set_active(False))
        self.filter_bar.set_visible(self.filter_bar.get_first_child() is not None)
        if hasattr(self, "no_matches_clear_search"):
            self.no_matches_clear_search.set_visible(bool(self._search_text))
            filters_active = (
                self._location_filter != "all" or self._favorites_only or self._unplayed_only
            )
            self.no_matches_clear_filters.set_visible(filters_active)
            self.no_matches_actions.set_visible(bool(self._search_text) or filters_active)

    def _update_stack_visibility(self):
        kind, value = self._category
        host_unavailable = (
            kind == "host"
            and self._host_statuses.get(value, {}).get("state") in ("auth", "offline")
        )
        if host_unavailable:
            self.content_stack.set_visible_child_name("no-matches")
        elif not self._games and self._hosts_being_checked():
            # Nothing local yet, but paired hosts haven't answered: don't
            # flash "your library is empty" for the length of a timeout.
            self.loading_status.set_description("Checking Kabin hosts…")
            self.content_stack.set_visible_child_name("loading")
        elif not self._games:
            self.content_stack.set_visible_child_name("empty")
        elif not any(self._matches(g) for g in self._games):
            self.content_stack.set_visible_child_name("no-matches")
        else:
            self.content_stack.set_visible_child_name("games")

    def _hosts_being_checked(self) -> bool:
        return any(
            status.get("state") == "checking" for status in self._host_statuses.values()
        )

    def _tile_kind(self):
        kind, value = self._category
        if kind == "type":
            return get_kind(value)
        group = library_group_for(self._category)
        if group:
            return get_kind(group.tile_kind)
        return CABINET_KIND

    def _visible_count(self) -> int:
        return sum(1 for game in self._games if self._matches(game))

    def _library_tile_scale(self) -> float:
        if self._is_on_home():
            return 1.0
        return library_tile_scale(self._visible_count())

    def _apply_grid_metrics(self):
        kind = self._tile_kind()
        min_cols = 1 if self._visible_count() <= 3 else kind.min_columns
        self.game_grid.set_min_columns(min_cols)
        self.game_grid.set_max_columns(kind.max_columns)
        for name in ("portrait", "square", "landscape"):
            if name == kind.shape:
                self.game_grid.add_css_class(f"kabin-grid-{name}")
            else:
                self.game_grid.remove_css_class(f"kabin-grid-{name}")

    def _update_library_header(self):
        kind, value = self._category
        media = self._tile_kind()
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
            title, context = "Favorites", "Saved from every library"
        elif kind == "preset" and value == "unplayed":
            title, context = "Not opened yet", "Titles you have not launched from Kabin"
        elif kind == "home":
            title, context = "Home", "Continue, or open a library"
        elif library_group_for(self._category):
            title, context = library_group_for(self._category).label, ""
        elif kind == "type":
            title = media.plural
            context = ""
        else:
            title, context = "Library", ""
        count = sum(1 for game in self._games if self._matches(game))
        context_count = sum(1 for game in self._games if self._matches_context(game))
        category_count = sum(
            1 for game in self._games if matches_context(game, "", self._category, self.config)
        )
        noun = count_noun(count, media if kind == "type" else CABINET_KIND)
        if kind != "type":
            noun = "title" if count == 1 else "titles"
        self.library_title.set_label(title)
        for name in KINDS:
            self.library_title.remove_css_class(f"kabin-kind-{name}")
        count_text = (
            f"{count} of {context_count} {noun}"
            if count != context_count
            else f"{count} {noun}"
        )
        self.library_subtitle.set_label(
            f"{context} · {count_text}" if context else count_text
        )
        no_matches_title, no_matches_description = empty_state_message(
            kind, value, title, media, category_count, self._host_statuses.get(value)
        )
        self.no_matches_status.set_title(no_matches_title)
        self.no_matches_status.set_description(no_matches_description)

    def _on_search_changed(self, entry):
        # The text itself has to update now - _matches(), _is_on_home()
        # and the filter chips all read it synchronously - but re-filtering
        # is several full passes over the library (~44 ms at 5000 items),
        # far past a frame budget to spend on every keystroke. Coalesce a
        # burst of typing into one pass, the way the cover picker's search
        # already does.
        self._search_text = entry.get_text().strip().casefold()
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
        self._search_timeout = GLib.timeout_add(SEARCH_DEBOUNCE_MS, self._apply_search)

    def _apply_search(self):
        self._search_timeout = 0
        self._apply_grid_metrics()
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._update_filter_bar()
        self._sync_selection_to_filter()
        return False

    def _apply_category(self, category):
        self._category = category
        self._apply_grid_metrics()
        self._close_details()
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_stack_visibility()
        self._update_recent_visibility()
        self._update_library_header()
        self._update_filter_bar()
        self._update_game_scope()
        self._sync_selection_to_filter()

    def _update_game_scope(self):
        if not hasattr(self, "game_scope"):
            return
        while (child := self.game_scope.get_first_child()) is not None:
            self.game_scope.remove(child)
        filters = library_scope_filters(self._category, self._games)
        visible = len(filters) > 1
        self.game_scope_scroller.set_visible(visible)
        if not visible:
            return
        for category, label, _count in filters:
            button = Gtk.Button(label=label)
            button.add_css_class("kabin-filter-chip")
            if category == self._category:
                button.add_css_class("kabin-filter-active")
            button.connect("clicked", lambda *_args, chosen=category: self._select_category(chosen))
            self.game_scope.append(button)

    def _on_sidebar_selected(self, listbox, row):
        if self._syncing_sidebar:
            return
        category = self._sidebar_rows.get(row, CATEGORY_HOME) if row else CATEGORY_HOME
        self._apply_category(category)

    def _sync_selection_to_filter(self):
        selected = self.game_selection.get_selected_item()
        if selected and self._matches(selected.game):
            return

        if not self.game_selection.get_n_items():
            self.game_selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self._show_details(None)
        elif self.main_stack.get_visible_child_name() == "details":
            self.game_selection.set_selected(0)
        else:
            self.game_selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self._show_details(None)

    def _toast(self, title: str):
        if hasattr(self, "toast_overlay"):
            self.toast_overlay.add_toast(Adw.Toast(title=title, timeout=5))

    def _launch_game(self, game):
        if plays_in_kabin(game):
            self._play_media(game)
            return
        if opens_in_kabin_reader(game):
            self._open_reader(game)
            return
        if not game.launch:
            return
        if self._play_session and self._play_session.game_id == game.id:
            self._toast(f"{game.title} is already running.")
            return
        try:
            process = game.launch()
        except Exception as exc:
            self._toast(f"Could not launch {game.title} · {exc}")
            return
        # Only count it as played once the process actually started; a
        # missing emulator shouldn't put the game on the Continue shelf.
        self.config.record_played(game.id)
        self._rebuild_recent_shelf(self._games)
        if hasattr(process, "poll"):
            self._begin_play_session(game, process)

    # -- launched-process tracking ----------------------------------------

    def _begin_play_session(self, game, process):
        self._end_play_session(record=True)
        self._play_session = PlaySession(game.id, game.title, process)
        self._play_session_source = GLib.timeout_add(1000, self._poll_play_session)
        self._sync_play_button(game)
        # Get out of the way of a fullscreen emulator; restore in
        # _finish_play_session when the process exits.
        self._play_session_minimized = True
        self.minimize()

    def _poll_play_session(self):
        session = self._play_session
        if session is None:
            self._play_session_source = None
            return False
        returncode = session.returncode()
        if returncode is None:
            return True
        self._play_session_source = None
        self._finish_play_session(session, returncode)
        return False

    def _finish_play_session(self, session, returncode):
        elapsed = session.elapsed()
        self._play_session = None
        was_minimized = getattr(self, "_play_session_minimized", False)
        self._play_session_minimized = False
        self.config.record_play_time(session.game_id, recordable_seconds(elapsed))
        game = self._selected_game
        if game is not None and game.id == session.game_id:
            self._show_details(game)
        message = quick_failure_message(session.title, returncode, elapsed)
        if message:
            self._toast(message)
        if not self._closing and was_minimized:
            # The emulator just went away; put the cabinet back in front so
            # the controller lands on the library, not the desktop.
            self.present()

    def _end_play_session(self, *, record: bool):
        """Stop following the current process without killing it."""
        if self._play_session_source is not None:
            GLib.source_remove(self._play_session_source)
            self._play_session_source = None
        session = self._play_session
        self._play_session = None
        self._play_session_minimized = False
        if session is not None and record:
            self.config.record_play_time(session.game_id, recordable_seconds(session.elapsed()))

    def _can_play_media(self, game) -> bool:
        return can_play_media(game)

    def _is_playing(self, game) -> bool:
        return is_playing(game, self._playback_item)

    def _item_progress(self, game) -> float:
        return item_progress(
            game,
            self.config,
            is_current=self._is_playing(game),
            playback=self._playback,
            playback_index=self._playback_index,
            queue_length=len(self._playback_queue),
        )

    def _rebuild_track_list(self, game):
        if not hasattr(self, "details_tracks"):
            return
        while (child := self.details_tracks.get_first_child()) is not None:
            self.details_tracks.remove(child)
        queue = self._queue_for(game) if game and self._can_play_media(game) else []
        if len(queue) < 2:
            self.details_tracks.set_visible(False)
            return
        heading = Gtk.Label(label="Tracks", xalign=0)
        heading.add_css_class("heading")
        heading.add_css_class("kabin-track-heading")
        self.details_tracks.append(heading)
        for entry in queue:
            row = Gtk.Button()
            row.add_css_class("flat")
            row.add_css_class("kabin-track")
            inner = Gtk.Box(spacing=12)
            number = Gtk.Label(label=str(entry["track"] + 1), xalign=1)
            number.add_css_class("caption")
            number.add_css_class("kabin-track-number")
            number.set_width_chars(2)
            title = Gtk.Label(label=entry["title"], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            title.set_hexpand(True)
            inner.append(number)
            inner.append(title)
            row.set_child(inner)
            row.connect("clicked", lambda _btn, item=game, index=entry["track"]: self._play_media(item, index))
            self.details_tracks.append(row)
        self.details_tracks.set_visible(True)
        self._highlight_current_track()

    def _highlight_current_track(self):
        if not hasattr(self, "details_tracks"):
            return
        child = self.details_tracks.get_first_child()
        index = 0
        while child:
            if isinstance(child, Gtk.Button):
                if self._is_playing(self._selected_game) and index == self._playback_index:
                    child.add_css_class("kabin-track-current")
                else:
                    child.remove_css_class("kabin-track-current")
                index += 1
            child = child.get_next_sibling()

    def _open_playing_details(self, *_args):
        if self._playback_item:
            self._open_details(self._playback_item)

    def _sync_media_chrome(self, game=None):
        game = game or self._selected_game
        playing = self._is_playing(game)
        if hasattr(self, "details_now_chip"):
            self.details_now_chip.set_visible(playing)
        ratio = self._item_progress(game) if game else 0
        if hasattr(self, "details_progress"):
            self.details_progress.set_value(ratio)
            self.details_progress.set_visible(ratio > 0)
        if hasattr(self, "now_playing_button"):
            self.now_playing_button.set_visible(False)
        if hasattr(self, "details_tracks"):
            self._highlight_current_track()

    def _resume_hint(self, game) -> str:
        return resume_hint(game, self.config)

    def _queue_for(self, game) -> list[dict]:
        return queue_for(game)

    def _play_button_label(self, game) -> str:
        if self._is_running(game):
            return "Playing"
        return play_button_label(
            game,
            self.config,
            is_current=self._playback_item is game,
            playback=self._playback,
        )

    def _is_running(self, game) -> bool:
        return self._play_session is not None and self._play_session.game_id == game.id

    def _sync_play_button(self, game):
        if self._selected_game is not game:
            return
        self.details_play_button.set_label(self._play_button_label(game))
        self.details_play_button.set_sensitive(
            not self._is_running(game)
            and (
                bool(game.launch)
                or self._can_play_media(game)
                or self._opens_in_reader(game)
                or (game.source == "remote" and kind_for(game).id == "game")
            )
        )

    def _show_player_bar(self, visible: bool):
        if not hasattr(self, "bottom_stack"):
            return
        self.bottom_stack.set_visible(visible)

    def _persist_progress(self, item, session):
        if not item or not session:
            return
        track = self._playback_index
        save_progress(self.config, item.id, session.position, session.duration, track)
        self._last_progress_save = time.time()
        if item.source != "remote":
            return
        host = item.extra.get("host") or {}
        token = host.get("token", "")
        remote_id = item.extra.get("remote_id", "")
        if not token or not remote_id:
            return

        def worker():
            try:
                push_remote_progress(
                    host, token, remote_id, session.position, session.duration, track
                )
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_playback_poll(self):
        if self._playback_poll_source is not None:
            GLib.source_remove(self._playback_poll_source)
            self._playback_poll_source = None

    def _schedule_playback_poll(self):
        # _on_playback_ready runs once per successful session start, and
        # without cancelling any previous timer first, rapid track/session
        # switching (Next/Prev, or Play on a different item while one is
        # already going) can leave more than one 250ms poller alive at
        # once, all polling whatever self._playback currently is.
        self._cancel_playback_poll()
        self._playback_poll_source = GLib.timeout_add(250, self._poll_playback)

    def _stop_playback(self):
        session = self._playback
        item = self._playback_item
        self._playback = None
        self._playback_item = None
        self._playback_queue = []
        self._playback_index = 0
        self._playback_auth = None
        self._cancel_playback_poll()
        self._seeking = False
        if session and item:
            self._persist_progress(item, session)
        if session:
            session.close()
        self._show_player_bar(False)
        self._sync_media_chrome(item)
        if item:
            self._sync_play_button(item)
        if hasattr(self, "home_continue_box"):
            self._rebuild_recent_shelf(self._games)

    def _refresh_player_bar(self):
        game = self._playback_item
        session = self._playback
        if not game or not session:
            return
        entry = {}
        if 0 <= self._playback_index < len(self._playback_queue):
            entry = self._playback_queue[self._playback_index]
        self.player_title.set_label(game.title)
        suffix = ""
        if len(self._playback_queue) > 1:
            suffix = f" · {self._playback_index + 1}/{len(self._playback_queue)}"
        self.player_track.set_label((entry.get("title") or kind_for(game).verb) + suffix)
        if game.icon_path != self._player_art_path:
            self._player_art_path = game.icon_path
            if game.icon_path:
                self.player_art.set_filename(game.icon_path)
            else:
                self.player_art.set_paintable(None)
        self.player_prev.set_sensitive(self._playback_index > 0)
        self.player_next.set_sensitive(self._playback_index + 1 < len(self._playback_queue))
        self.player_pause.set_icon_name(
            "media-playback-start-symbolic" if session.paused else "media-playback-pause-symbolic"
        )
        self.player_pause.set_tooltip_text("Resume" if session.paused else "Pause")
        duration = session.duration or 0
        position = session.position or 0
        self.player_elapsed.set_label(format_clock(position))
        remaining = max(0.0, duration - position) if duration else 0
        self.player_remaining.set_label(f"-{format_clock(remaining)}" if duration else "0:00")
        if duration and not self._seeking:
            self.player_seek.set_value(min(1.0, position / duration))
        self._sync_media_chrome(game)

    def _toggle_playback_pause(self):
        session = self._playback
        if not session:
            return
        session.toggle_pause()
        if self._playback_item:
            self._sync_play_button(self._playback_item)
        self._refresh_player_bar()

    def _on_seek_change(self, _scale, _scroll, value):
        session = self._playback
        if not session:
            return False
        self._seeking = True
        duration = session.duration or 0
        if duration:
            session.seek(value * duration)
            self.player_elapsed.set_label(format_clock(value * duration))
        return False

    def _finish_seek(self):
        self._seeking = False
        if self._playback and self._playback_item:
            self._persist_progress(self._playback_item, self._playback)

    def _skip_playback(self, delta: int):
        next_index = next_queue_index(self._playback_index, len(self._playback_queue), delta)
        if next_index is None:
            if delta > 0:
                self._stop_playback()
            return
        self._start_queue_index(next_index, 0)

    def _poll_playback(self):
        session = self._playback
        if session is None:
            self._playback_poll_source = None
            return False
        if session.ended or session.process.poll() is not None:
            # Clear this before _start_queue_index/_stop_playback rather
            # than after: both eventually reach _schedule_playback_poll or
            # _cancel_playback_poll, and this source is already being
            # torn down by returning False below, so it must not be
            # GLib.source_remove()'d a second time as if it were still
            # live.
            self._playback_poll_source = None
            next_index = next_queue_index(self._playback_index, len(self._playback_queue))
            if next_index is not None:
                self._start_queue_index(next_index, 0)
                return False
            self._stop_playback()
            return False
        self._refresh_player_bar()
        if time.time() - self._last_progress_save >= 15 and self._playback_item:
            self._persist_progress(self._playback_item, session)
        return True

    def _nudge_playback(self, delta: float):
        session = self._playback
        if not session:
            return
        session.seek(max(0.0, session.position + delta))
        self._refresh_player_bar()

    def _play_media(self, game, track=None):
        if self._playback_item is game and track is None:
            self._toggle_playback_pause()
            return
        if not helper_ready():
            if game.source != "remote" and game.launch:
                self.config.record_played(game.id)
                game.launch()
                return
            self._toast("Build kabin-media-helper to play media in Kabin")
            return
        queue = self._queue_for(game)
        if not queue:
            self._toast(f"Could not play {game.title}")
            return
        if track is None:
            index = resume_track(self.config, game.id, len(queue))
            start = resume_seconds(self.config, game.id)
        else:
            index = max(0, min(int(track), len(queue) - 1))
            start = 0
        authorization = None
        if game.source == "remote" and game.extra.get("playable"):
            token = (game.extra.get("host") or {}).get("token", "")
            authorization = f"Bearer {token}" if token else None
        self._playback_queue = queue
        self._playback_auth = authorization
        self.details_play_button.set_label("Opening…")
        self.details_play_button.set_sensitive(False)
        self._start_queue_index(index, start, game)

    def _start_queue_index(self, index: int, start: float, game=None):
        game = game or self._playback_item
        if not game or not (0 <= index < len(self._playback_queue)):
            return
        entry = self._playback_queue[index]
        previous = self._playback
        previous_item = self._playback_item
        if previous and previous_item:
            self._persist_progress(previous_item, previous)
            previous.close()
        self._playback = None
        self._playback_item = game
        self._playback_index = index

        def worker():
            session = None
            error = None
            try:
                session = PlaybackSession(
                    entry["uri"], start=start, authorization=self._playback_auth
                )
                session.wait("ready", timeout=8)
            except Exception as exc:
                error = exc
                if session:
                    session.close()
                    session = None
            GLib.idle_add(self._on_playback_ready, game, session, error, index)

        threading.Thread(target=worker, daemon=True).start()

    def _on_playback_ready(self, game, session, error, index=0):
        if self._closing:
            if session:
                session.close()
            return False
        if error or session is None:
            if self._selected_game is game:
                self._sync_play_button(game)
            if not self._playback:
                self._show_player_bar(False)
            self._toast(f"Could not play {game.title} · {error or 'helper failed'}")
            return False
        if self._playback_item is not game or self._playback_index != index:
            session.close()
            return False
        self._playback = session
        self._playback_item = game
        self._playback_index = index
        self.config.record_played(game.id)
        self._rebuild_recent_shelf(self._games)
        self._sync_play_button(game)
        self._show_player_bar(True)
        self._refresh_player_bar()
        self._rebuild_hero(self._games)
        self._last_progress_save = time.time()
        kind = kind_for(game)
        watching = kind.verb == "Watch"
        self._toast(f"Watching {game.title}" if watching else f"{kind.verb}ing {game.title}")
        self._schedule_playback_poll()
        return False

    def _on_tile_activated(self, _grid, position):
        item = self.game_selection.get_item(position)
        if item:
            self._open_details(item.game)

    def _on_tile_selected(self, _selection, _pspec):
        item = self.game_selection.get_selected_item()
        self._show_details(item.game if item else None)

    def _launch_selected(self):
        game = self._selected_game
        if not game:
            return
        if plays_in_kabin(game):
            self._play_media(game)
            return
        if self._opens_in_reader(game):
            self._open_reader(game)
            return
        if game.source == "remote" and kind_for(game).id == "game":
            self._prepare_remote_selected()
            return
        self._launch_game(game)

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
            session, error, helper = None, None, None
            try:
                session = prepare_remote_session(host, token, remote_id)
                media = session.get("media") or {}
                if media.get("status") == "unavailable":
                    raise MediaHelperError(
                        media.get("error") or "The host media helper is not ready"
                    )
                helper = MediaHelperSession("client")
                offer = create_client_offer(helper)
                answer = signal_remote_session(host, token, session["id"], offer)
                sdp = answer.get("sdp")
                if not sdp:
                    raise MediaHelperError("The host did not return a stream answer")
                helper.send({"type": "answer", "sdp": sdp})
                helper.wait("ready")
            except Exception as exc:
                if helper:
                    helper.close()
                    helper = None
                error = str(exc)
            GLib.idle_add(self._on_remote_session_prepared, game, session, error, helper)

        threading.Thread(target=worker, daemon=True).start()

    def _replace_stream_helper(self, helper):
        previous = self._stream_helper
        self._stream_helper = helper
        if previous and previous is not helper:
            previous.close()

    def _on_remote_session_prepared(self, game, session, error, helper=None):
        if self._selected_game is not game:
            if helper:
                helper.close()
            return False
        if error:
            self._replace_stream_helper(None)
            self.details_play_button.set_label("Retry Stream")
            self.details_play_button.set_sensitive(True)
            self.details_description.set_label(f"Could not start the stream · {error}")
            return False
        game.extra["session"] = session
        self.config.record_played(game.id)
        self._rebuild_recent_shelf(self._games)
        self._replace_stream_helper(helper)
        self.details_play_button.set_label("Streaming")
        self.details_play_button.set_sensitive(True)
        self.details_description.set_label(
            "Kabin is streaming this host. The picture opens in Kabin's media window."
        )
        self._toast(f"Streaming {game.title}")
        return False

    def _open_details(self, game):
        self._show_details(game)
        self.main_stack.set_visible_child_name("details")
        self.details_play_button.grab_focus()

    def _close_details(self):
        if hasattr(self, "main_stack"):
            self.main_stack.set_visible_child_name("library")

    def _opens_in_reader(self, game) -> bool:
        return opens_in_kabin_reader(game) or can_read_remote(game)

    def _open_reader(self, item):
        current = self.main_stack.get_visible_child_name()
        if current != "reader":
            self._reader_return_stack = current
        if self._reader_item is item and self._reader_pages:
            self.main_stack.set_visible_child_name("reader")
            return
        if can_read_remote(item) and playable_file(item) is None:
            self._fetch_remote_reader(item)
            return
        backend = reader_backend_for(item)
        path = playable_file(item)
        if backend is None or path is None:
            self._toast(f"Could not open {item.title}")
            return
        self._close_reader_resources()
        self._reader_item = item
        self._reader_backend = backend
        self._sync_reader_zones()
        self.reader_title.set_label(item.title)
        self.reader_page_label.set_label("")
        self.reader_toc_button.set_visible(False)
        self.reader_status.set_title("Opening…")
        self.reader_status.set_description("")
        self.reader_content_stack.set_visible_child_name("status")
        self.main_stack.set_visible_child_name("reader")
        # Goes through the same single render-thread queue as page turns —
        # see _reader_render_loop for why (concurrent Poppler/cairo calls
        # from different threads are not safe).
        self._reader_render_queue.put(("open", path, backend, item))

    def _fetch_remote_reader(self, item):
        host = (item.extra or {}).get("host") or {}
        token = host.get("token", "")
        remote_id = (item.extra or {}).get("remote_id") or ""
        if not token or not remote_id:
            self._toast(f"Could not open {item.title}")
            return
        host_key = f"{host.get('address', '')}:{host.get('port', '')}"
        dest = remote_read_cache_path(
            host_key, remote_id, int((item.extra or {}).get("size") or 0), remote_read_suffix(item)
        )
        try:
            if dest.is_file() and (
                not item.extra.get("size") or dest.stat().st_size == int(item.extra.get("size") or 0)
            ):
                item.extra["path"] = str(dest)
                self._open_reader(item)
                return
        except OSError:
            pass
        self._close_reader_resources()
        self._reader_item = item
        self.reader_title.set_label(item.title)
        self.reader_page_label.set_label("")
        self.reader_toc_button.set_visible(False)
        self.reader_status.set_title("Opening…")
        self.reader_status.set_description("Fetching this title from the host…")
        self.reader_content_stack.set_visible_child_name("status")
        self.main_stack.set_visible_child_name("reader")

        def worker():
            try:
                fetch_remote_media(host, token, remote_id, dest)
                error = None
            except Exception as exc:
                error = exc
            GLib.idle_add(self._on_remote_reader_fetched, item, dest, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_remote_reader_fetched(self, item, dest, error):
        if self._closing or self._reader_item is not item:
            return False
        if error:
            self.reader_status.set_title("Could not open this file")
            self.reader_status.set_description(str(error))
            self.reader_content_stack.set_visible_child_name("status")
            self._toast(f"Could not open {item.title} · {error}")
            return False
        item.extra["path"] = str(dest)
        try:
            # Touch first so prune's mtime ranking keeps the book we just
            # fetched instead of deleting it as the oldest entry.
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.touch()
            prune_remote_read_cache()
        except OSError:
            pass
        self._open_reader(item)
        return False

    def _sync_reader_zones(self):
        visible = uses_tap_zones(self._reader_backend)
        if hasattr(self, "reader_zones"):
            self.reader_zones.set_can_target(visible)
            self.reader_prev_zone.set_visible(visible)
            self.reader_next_zone.set_visible(visible)

    def _on_reader_opened(self, item, pages, count, error):
        if self._closing or self._reader_item is not item:
            if pages:
                pages.close()
            return False
        if error or not pages:
            self.reader_status.set_title("Could not open this file")
            self.reader_status.set_description(str(error) if error else "")
            self.reader_content_stack.set_visible_child_name("status")
            self._toast(f"Could not open {item.title} · {error or 'unknown error'}")
            return False
        self._reader_pages = pages
        self._reader_page_count = count
        self.reader_seek.set_range(0, max(0, count - 1))
        self._update_reader_toc(pages)
        self.config.record_played(item.id)
        self._rebuild_recent_shelf(self._games)
        start = max(0, min(count - 1, resume_page(self.config, item.id)))
        self._reader_show_page(start)
        return False

    def _update_reader_toc(self, pages):
        toc = getattr(pages, "toc", None)
        if not toc:
            self.reader_toc_button.set_visible(False)
            self.reader_toc_button.set_popover(None)
            return
        popover = Gtk.Popover()
        popover.add_css_class("kabin-reader-toc")
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(360)
        scroller.set_propagate_natural_height(True)
        scroller.set_propagate_natural_width(True)
        scroller.set_min_content_width(260)
        listbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for entry in toc:
            row = Gtk.Button()
            row.add_css_class("flat")
            row.add_css_class("kabin-reader-toc-entry")
            label = Gtk.Label(label=entry["title"], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            label.set_max_width_chars(36)
            label.set_hexpand(True)
            row.set_child(label)
            row.connect(
                "clicked",
                lambda _btn, index=entry["index"], fragment=entry.get("fragment", ""): (
                    self._reader_jump_to(index, fragment),
                    self.reader_toc_button.popdown(),
                ),
            )
            listbox.append(row)
        scroller.set_child(listbox)
        popover.set_child(scroller)
        self.reader_toc_button.set_popover(popover)
        self.reader_toc_button.set_visible(True)

    def _ensure_reader_webview(self):
        if self.reader_webview is not None:
            return self.reader_webview
        import gi

        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit

        webview = WebKit.WebView()
        webview.set_hexpand(True)
        webview.set_vexpand(True)
        apply_reader_webview_settings(webview.get_settings())
        webview.connect("decide-policy", self._on_reader_decide_policy)
        self.reader_content_stack.add_named(webview, "html")
        self.reader_webview = webview
        return webview


    def _reader_scroll_to_fragment(self, webview, fragment: str):
        """Scroll to a TOC #fragment after load. Briefly enables JS for one
        host-initiated evaluate — page scripts stay off via settings."""
        import json

        frag = (fragment or "").lstrip("#")
        if not frag or webview is None:
            return
        script = (
            "(() => { const id = %s;"
            " const el = document.getElementById(id)"
            " || document.getElementsByName(id)[0];"
            " if (el) el.scrollIntoView(); })();" % json.dumps(frag)
        )
        settings = webview.get_settings()
        was_js = False
        try:
            was_js = bool(settings.get_enable_javascript())
            settings.set_enable_javascript(True)
        except Exception:
            pass

        def _restore(*_args):
            try:
                settings.set_enable_javascript(was_js)
            except Exception:
                pass
            return False

        def _run(_webview, result, _data=None):
            try:
                _webview.evaluate_javascript_finish(result)
            except Exception:
                pass
            GLib.idle_add(_restore)

        def _on_load(webview, event):
            try:
                from gi.repository import WebKit
                if event != WebKit.LoadEvent.FINISHED:
                    return
            except Exception:
                return
            try:
                webview.disconnect_by_func(_on_load)
            except Exception:
                pass
            try:
                webview.evaluate_javascript(script, -1, None, None, None, _run, None)
            except Exception:
                _restore()

        try:
            webview.connect("load-changed", _on_load)
        except Exception:
            _restore()

    def _reader_allowed_roots(self) -> list:
        root = reader_cache_root(self._reader_pages)
        return [root] if root else []

    def _on_reader_decide_policy(self, _webview, decision, decision_type):
        from gi.repository import WebKit

        roots = self._reader_allowed_roots()
        if decision_type == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            uri = decision.get_navigation_action().get_request().get_uri()
            if reader_uri_allowed(uri, roots):
                decision.use()
            else:
                decision.ignore()
            return True
        if decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
            decision.ignore()
            return True
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            uri = decision.get_request().get_uri()
            if reader_uri_allowed(uri, roots):
                decision.use()
            else:
                decision.ignore()
            return True
        return False



    def _on_reader_pdf_size(self, *_args):
        if self._closing or self._reader_backend != "pdf" or not self._reader_pages:
            return
        if self.main_stack.get_visible_child_name() != "reader":
            return
        width = self._reader_target_width()
        if abs(width - (self._reader_pdf_width or 0)) < 64:
            return
        self._reader_pdf_width = width
        self._reader_show_page(self._reader_page_index)

    def _reader_target_width(self) -> int:
        """Pixel width to rasterize PDF pages at, matching the reader pane."""
        widget = getattr(self, "reader_picture", None)
        width = widget.get_width() if widget is not None else 0
        if width <= 1:
            width = PDF_RENDER_WIDTH
        scale = self.get_scale_factor() if hasattr(self, "get_scale_factor") else 1.0
        return max(320, int(width * max(1.0, float(scale))))

    def _reader_jump_to(self, index: int, fragment: str = ""):
        self._reader_pending_fragment = fragment or ""
        self._reader_show_page(index)

    def _reader_show_page(self, index: int):
        pages = self._reader_pages
        total = self._reader_page_count
        item = self._reader_item
        if not pages or not total or not item:
            return
        index = max(0, min(total - 1, index))
        backend = self._reader_backend
        self._reader_request += 1
        request_id = self._reader_request
        # Rendering (rasterizing a PDF page, reading a comic-archive/EPUB
        # member) is I/O/CPU work best kept off the main thread so page
        # turns and slider drags don't stall the UI. It's queued onto a
        # single persistent render thread rather than a thread per
        # request: Poppler/cairo segfault if two renders run concurrently
        # (confirmed by crashing them that way), so every reader render —
        # opening a file or turning a page, PDF or not — is serialized
        # through one worker to rule that out.
        target_width = self._reader_target_width() if backend == "pdf" else None
        if backend == "pdf":
            self._reader_pdf_width = target_width or 0
        self._reader_render_queue.put(("page", request_id, pages, backend, item, index, total, target_width))

    def _reader_render_loop(self):
        while True:
            job = self._reader_render_queue.get()
            # Coalesce a burst of requests (rapid page-turns, a slider
            # drag) down to only the most recent one.
            while True:
                try:
                    job = self._reader_render_queue.get_nowait()
                except queue.Empty:
                    break
            if job[0] == "open":
                _, path, backend, item = job
                try:
                    pages = open_reader_pages(path, backend)
                    count = len(pages)
                    if count <= 0:
                        raise ValueError("This file has no readable pages")
                    open_result = (pages, count, None)
                except Exception as exc:
                    open_result = (None, 0, exc)
                GLib.idle_add(self._on_reader_opened, item, *open_result)
                continue
            _, request_id, pages, backend, item, index, total, target_width = job
            try:
                if backend == "pdf":
                    data = pages.page_bytes(index, target_width=target_width or PDF_RENDER_WIDTH)
                else:
                    data = pages.page_bytes(index)
                base_uri = pages.page_base_uri(index) if backend in HTML_READER_BACKENDS else None
                result = (data, base_uri, None)
            except Exception as exc:
                result = (None, None, exc)
            GLib.idle_add(self._on_reader_page_ready, request_id, item, index, total, result)
            # Warm the next page while the current one paints. Back-flips
            # already hit the LRU; forward on CBR/CB7 used to cold-extract
            # every time. Same thread as the render (Poppler isn't reentrant).
            if result[2] is None and index + 1 < total and backend in {
                "comic-7z",
                "comic-rar",
                "pdf",
            }:
                try:
                    if backend == "pdf":
                        pages.page_bytes(index + 1, target_width=target_width or PDF_RENDER_WIDTH)
                    else:
                        pages.page_bytes(index + 1)
                except Exception:
                    pass

    def _on_reader_page_ready(self, request_id, item, index, total, result):
        if self._closing or request_id != self._reader_request or self._reader_item is not item:
            return False
        data, base_uri, error = result
        if error is not None:
            self._toast(f"Could not render this page · {error}")
            return False
        backend = self._reader_backend
        if backend in HTML_READER_BACKENDS:
            try:
                webview = self._ensure_reader_webview()
                # Force the HTML5 parser (not strict application/xhtml+xml
                # XML parsing) so EPUB spine documents that aren't
                # perfectly namespaced XHTML — common from less careful
                # sources — still render styled instead of dumping as raw
                # text. FB2 pages are plain HTML Kabin generated itself,
                # so this is just consistent, not load-bearing for them.
                webview.load_bytes(GLib.Bytes.new(data), "text/html", "utf-8", base_uri)
                fragment = self._reader_pending_fragment
                self._reader_pending_fragment = ""
                if fragment:
                    self._reader_scroll_to_fragment(webview, fragment)
            except Exception as exc:
                self._toast(f"Could not render this page · {exc}")
                return False
            self.reader_content_stack.set_visible_child_name("html")
        elif backend == "text":
            self.reader_text_view.get_buffer().set_text(data.decode("utf-8", errors="replace"))
            self.reader_content_stack.set_visible_child_name("text")
            self._reader_page_index = index
            self.reader_page_label.set_label(f"{index + 1} / {total}")
            self.reader_seek.set_value(index)
            # Keep any saved mid-page scroll; restoring happens after GTK
            # has laid out the text so the adjustment has a real upper.
            self._persist_reader_progress(item)
            saved_scroll = resume_scroll(self.config, item.id)
            if saved_scroll > 0:
                GLib.idle_add(self._restore_reader_scroll, saved_scroll)
            return False
        else:
            try:
                texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            except GLib.Error:
                self._toast("Could not render this page")
                return False
            self.reader_picture.set_paintable(texture)
            self.reader_content_stack.set_visible_child_name("page")
        self._reader_page_index = index
        self.reader_page_label.set_label(f"{index + 1} / {total}")
        self.reader_seek.set_value(index)
        self._persist_reader_progress(item)
        return False

    def _reader_scroll_fraction(self) -> float:
        adj = scroll_adjustment(getattr(self, "reader_text_scroller", None))
        if adj is None:
            return 0.0
        span = adj.get_upper() - adj.get_page_size()
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, adj.get_value() / span))

    def _restore_reader_scroll(self, fraction: float):
        adj = scroll_adjustment(getattr(self, "reader_text_scroller", None))
        if adj is None:
            return False
        span = adj.get_upper() - adj.get_page_size()
        if span > 0:
            adj.set_value(fraction * span)
        return False

    def _persist_reader_progress(self, item, *, write_scroll: bool = False):
        if not item or not self._reader_pages or not self._reader_page_count:
            return
        scroll = None
        if self._reader_backend == "text":
            fraction = self._reader_scroll_fraction()
            # Opening a TXT lays out at scroll 0; writing that would wipe the
            # saved place before the idle restore runs. Only commit scroll
            # when the reader is leaving or the user has moved.
            if write_scroll or fraction > 0:
                scroll = fraction
        save_page_progress(
            self.config,
            item.id,
            self._reader_page_index,
            self._reader_page_count,
            scroll=scroll,
        )
        page = self._reader_page_index
        total = self._reader_page_count
        for host, item_id in reader_progress_targets(item, getattr(self, "_games", [])):
            token = host.get("token", "")

            def worker(target_host=host, target_token=token, target_id=item_id):
                try:
                    push_remote_progress(target_host, target_token, target_id, page, total, 0)
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

    def _reader_scroll(self, direction: int) -> bool:
        if uses_tap_zones(self._reader_backend):
            return False
        widget = None
        if self._reader_backend == "text":
            widget = getattr(self, "reader_text_scroller", None)
        elif self._reader_backend in HTML_READER_BACKENDS:
            widget = self.reader_webview
        return step_adjustment(scroll_adjustment(widget), direction)

    def _reader_step(self, direction: int):
        """Scroll within the current page when possible; otherwise turn.

        Used by Space / Page Up / Page Down on EPUB, FB2, and TXT so they
        match pad up/down instead of skipping unread text.
        """
        if uses_tap_zones(self._reader_backend):
            self._reader_turn(direction)
            return
        if not self._reader_scroll(direction):
            self._reader_turn(direction)

    def _reader_turn(self, delta: int):
        if not self._reader_pages:
            return
        self._reader_show_page(self._reader_page_index + delta)

    def _on_reader_seek_change(self, _scale, _scroll, value):
        if not self._reader_pages:
            return False
        self._reader_show_page(round(value))
        return False

    def _close_reader_resources(self):
        if self._reader_pages:
            self._reader_pages.close()
        if self._reader_backend in HTML_READER_BACKENDS and self.reader_webview is not None:
            self.reader_webview.load_uri("about:blank")
        self._reader_pages = None
        self._reader_backend = None
        self._reader_page_count = 0
        self._reader_page_index = 0
        self._sync_reader_zones()

    def _close_reader(self):
        item = self._reader_item
        if item and self._reader_pages and self._reader_page_count:
            self._persist_reader_progress(item, write_scroll=True)
            self._sync_play_button(item)
            self._rebuild_recent_shelf(self._games)
        self._close_reader_resources()
        self._reader_item = None
        if hasattr(self, "main_stack"):
            self.main_stack.set_visible_child_name(getattr(self, "_reader_return_stack", "library"))

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
        self._toggle_favorite_item(self._selected_game)

    def _toggle_favorite_item(self, game):
        if not game:
            return
        self.config.toggle_favorite(game.id)
        self._selected_game = game
        self._update_favorite_button()
        self._rebuild_sidebar(self._games, preserve_category=self._category)
        self._rebuild_recent_shelf(self._games)
        if not self._matches(game):
            self._close_details()
        self._apply_library_filters()

    def _change_selected_cover(self, _button):
        game = self._selected_game
        if not game:
            return
        self.details_more_button.popdown()
        picker = CoverPicker(
            game,
            self.config,
            on_chosen=lambda path: self._apply_chosen_cover(game, path),
            transient_for=self,
        )
        picker.present()

    def _apply_chosen_cover(self, game, path):
        if not game or not path:
            return
        game.icon_path = str(path)
        game.extra["needs_artwork"] = False
        if self._selected_game is game:
            self.details_picture.set_filename(str(path))
            self._update_backdrop(path)
        self.game_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._rebuild_recent_shelf(self._games)

    def _open_selected_folder(self, _button):
        game = self._selected_game
        self.details_more_button.popdown()
        path = local_path(game) if game else None
        if path is None:
            return
        folder = path if path.is_dir() else path.parent
        try:
            Gio.AppInfo.launch_default_for_uri(folder.as_uri(), None)
        except GLib.Error as exc:
            self._toast(f"Could not open {folder.name} · {exc.message}")

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

    def _library_backdrop_item(self):
        selected = (
            self.game_selection.get_selected_item() if hasattr(self, "game_selection") else None
        )
        if selected and self._matches(selected.game) and selected.game.icon_path:
            return selected.game
        if self._playback_item and self._matches(self._playback_item) and self._playback_item.icon_path:
            return self._playback_item
        for game in self._games:
            if self._matches(game) and game.icon_path:
                return game
        return None

    def _refresh_library_backdrop(self):
        item = self._library_backdrop_item()
        self._update_backdrop(item.icon_path if item else None)

    def _show_details(self, game):
        self._selected_game = game
        if game is None:
            self._refresh_library_backdrop()
            return

        kind = kind_for(game)
        self.details_kind_chip.set_label(kind.label)
        for name in KINDS:
            if name == kind.id:
                self.details_kind_chip.add_css_class(f"kabin-kind-{name}")
            else:
                self.details_kind_chip.remove_css_class(f"kabin-kind-{name}")
        self.details_art_frame.set_size_request(kind.details_width, kind.details_height)
        self.details_art_plate.set_size_request(kind.details_width, kind.details_height)
        self.details_picture.set_content_fit(_art_fit(kind))
        for name in ("portrait", "square", "landscape"):
            if name == kind.shape:
                self.details_art_frame.add_css_class(f"kabin-art-{name}")
            else:
                self.details_art_frame.remove_css_class(f"kabin-art-{name}")
        self.details_title.set_label(game.title)
        self.details_description.set_label("")
        self._sync_play_button(game)
        self._sync_media_chrome(game)
        self.details_picture.set_paintable(None)
        self._update_backdrop(None)

        source_labels = {"steam": "Steam", "desktop": "Installed App", "remote": "Kabin Host"}
        meta_parts = []
        if game.creators:
            meta_parts.append(", ".join(game.creators[:3]))
        if game.series:
            index = f" #{int(game.series_index)}" if game.series_index else ""
            meta_parts.append(f"{game.series}{index}")
        if game.source == "remote":
            meta_parts.append("Kabin Host")
        elif kind.id == "game":
            meta_parts.append(source_labels.get(game.source, game.subtitle or kind.plural))
        if game.media_format and game.media_format not in {"", "album"}:
            meta_parts.append(game.media_format.upper())
        last_played = self.config.recent.get(game.id)
        if last_played:
            played_date = time.strftime("%b %d, %Y", time.localtime(last_played)).replace(" 0", " ")
            meta_parts.append(f"{kind.last_opened} {played_date}")
        if kind.id == "game":
            played_for = format_play_time(self.config.play_seconds(game.id))
            if played_for:
                meta_parts.append(f"Played {played_for}")
            plays = play_count_label(self.config.play_count(game.id))
            if plays:
                meta_parts.append(plays)
        meta_parts.extend(file_details(game))
        self.details_open_folder_button.set_visible(local_path(game) is not None)

        if game.source == "remote" and kind.id == "game":
            remote_system = game.extra.get("remote_system")
            if remote_system:
                meta_parts.append(remote_system)
            self.details_description.set_label(
                "Stream with Kabin. This device decodes the host picture; no extra app is launched."
            )
        elif game.source == "remote" and self._can_play_media(game):
            self.details_description.set_label(
                "Play in Kabin. The host streams the file; this device decodes it."
                + self._resume_hint(game)
            )
        elif self._opens_in_reader(game):
            if game.source == "remote":
                self.details_description.set_label(
                    "Kabin fetches this from the host and reads it here."
                    + self._resume_hint(game)
                )
            else:
                self.details_description.set_label(
                    "Kabin reads this here and remembers your place." + self._resume_hint(game)
                )
        elif game.source == "remote":
            self.details_play_button.set_sensitive(False)
            self.details_description.set_label(
                f"This {kind.label.lower()} lives on the host. Open it there for now."
            )
        elif self._can_play_media(game):
            self.details_description.set_label(
                "Kabin plays this here and remembers your place." + self._resume_hint(game)
            )
        elif game.source == "roms":
            self.details_description.set_label(rom_launch_summary(game, self.config.rom_dirs))
        if game.source == "remote" and game.extra.get("has_artwork") and not game.extra.get("appid"):
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
        elif game.extra.get("appid"):
            appid = game.extra.get("appid")
            cached = icons.cached_path(appid)
            if cached:
                self.details_picture.set_filename(str(cached))
                self._update_backdrop(cached)
            else:
                icons.fetch_async(
                    appid, lambda path: self._on_remote_details_art_ready(game, path)
                )
            if game.source == "steam":
                metadata = steam_source.load_local_metadata(appid, self.config.data.get("steam_root"))
                if metadata.get("developers"):
                    meta_parts.append(", ".join(metadata["developers"][:2]))
                if metadata.get("description"):
                    self.details_description.set_label(metadata["description"])
        elif kind_for(game).id == "book" and game.extra.get("needs_artwork"):
            _queue_book_cover(
                game, lambda path: self._on_remote_details_art_ready(game, path)
            )
        elif game.extra.get("needs_artwork") and _artwork_api_key:
            _sgdb_artwork.request_job(
                ("sgdb", game.id),
                (game.title, game.id, _artwork_api_key),
                lambda path: self._on_remote_details_art_ready(game, path),
            )

        self.details_meta.set_label(" · ".join(meta_parts))
        self._update_favorite_button()
        self._rebuild_track_list(game)
        self._rebuild_related_shelf(game)

    def _rebuild_related_shelf(self, game):
        if not hasattr(self, "details_related_shelf"):
            return
        self._clear_box(self.details_related_shelf)
        related = related_items(game, getattr(self, "_games", []))
        if not related:
            self.details_related_section.set_visible(False)
            return
        series = (getattr(game, "series", None) or "").strip()
        if self.details_related_header is not None:
            self.details_related_header.set_label(
                f"More in {series}" if series else "More in this series"
            )
        for item in related:
            button = _build_shelf_button(
                item,
                self._open_details,
                self._item_progress(item),
                self._is_playing(item),
                show_badge=False,
            )
            self.details_related_shelf.append(button)
        self.details_related_section.set_visible(True)

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
        before = self.config.library_fingerprint()

        def on_close(*_args):
            # Only rescan when something that feeds the scan changed;
            # glancing at Settings and backing out shouldn't drop the
            # user on "Updating your library…" and lose their place.
            if self.config.library_fingerprint() != before:
                self.refresh()
            return False

        settings_window.connect("close-request", on_close)
        settings_window.present()

    def _on_close_request(self, *_args):
        self._closing = True
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
            self._search_timeout = 0
        self.config.save_window_state(self.get_width(), self.get_height(), self.is_maximized())
        self._end_play_session(record=True)
        self._stop_playback()
        self._close_reader_resources()
        self._replace_stream_helper(None)
        if self._gamepad:
            self._gamepad.close()
        self.host_service.stop()
        _remote_artwork.close()
        _sgdb_artwork.close()
        _book_artwork.close()
        icons.close()
        return False

    def _queue_cabinet_action(self, action: str):
        GLib.idle_add(self._on_cabinet_action, action)

    def _cabinet_chrome_focused(self) -> bool:
        focused = self.get_focus()
        return isinstance(focused, (Gtk.Editable, Gtk.Entry, Gtk.SearchEntry, Gtk.DropDown, Gtk.TextView))

    def _set_nav_target(self, target: str, *, show_focus: bool = True):
        self._nav_target = target
        self.sidebar_list.remove_css_class("kabin-nav-focus")
        self.game_grid.remove_css_class("kabin-nav-focus")
        if not show_focus:
            return
        if target == "sidebar":
            self.sidebar_list.add_css_class("kabin-nav-focus")
            self.sidebar_list.grab_focus()
        elif target == "home":
            self._restore_home_focus()
        else:
            self.game_grid.add_css_class("kabin-nav-focus")
            self.game_grid.grab_focus()

    def _sync_library_nav(self):
        if self._nav_target == "sidebar":
            return
        wanted = self._library_nav_target()
        if self._nav_target != wanted:
            if self._cabinet_chrome_focused():
                self._nav_target = wanted
                return
            self._set_nav_target(wanted, show_focus=False)

    def _restore_home_focus(self):
        rows = self._home_focus_rows
        if not rows:
            if hasattr(self, "hero_play"):
                self.hero_play.grab_focus()
            return
        row, col = self._home_focus_pos
        row = max(0, min(row, len(rows) - 1))
        col = max(0, min(col, len(rows[row]) - 1))
        self._home_focus_pos = (row, col)
        widget = rows[row][col]
        widget.grab_focus()
        game = getattr(widget, "_kabin_game", None)
        if game:
            self._selected_game = game

    def _focused_home_game(self):
        if self._nav_target != "home":
            return self._featured_item
        rows = self._home_focus_rows
        if not rows:
            return self._featured_item
        row, col = self._home_focus_pos
        if row >= len(rows) or col >= len(rows[row]):
            return self._featured_item
        return getattr(rows[row][col], "_kabin_game", None) or self._featured_item

    def _sidebar_categories(self) -> list:
        return [category for category in self._sidebar_rows.values() if category[0] != "action"]

    def _select_category(self, category):
        self._apply_category(category)
        highlight = sidebar_highlight_category(category)
        row = next((item for item, value in self._sidebar_rows.items() if value == highlight), None)
        if row:
            self._syncing_sidebar = True
            self.sidebar_list.select_row(row)
            self._syncing_sidebar = False

    def _cycle_category(self, delta: int):
        categories = self._sidebar_categories()
        if not categories:
            return
        current = sidebar_highlight_category(self._category)
        try:
            index = categories.index(current)
        except ValueError:
            index = 0
        self._select_category(categories[cycle_index(index, len(categories), delta)])

    def _grid_column_count(self) -> int:
        width = max(1, self.game_grid.get_width())
        tile = int(self._tile_kind().tile_width * self._library_tile_scale()) + 20
        return max(1, min(self._tile_kind().max_columns, width // tile))

    def _selected_index(self) -> int:
        selected = self.game_selection.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return 0
        return int(selected)

    def _select_index(self, index: int):
        count = self.game_selection.get_n_items()
        if not count:
            return
        index = max(0, min(count - 1, index))
        self.game_selection.set_selected(index)
        if hasattr(self.game_grid, "scroll_to"):
            try:
                self.game_grid.scroll_to(index, Gtk.ListScrollFlags.SELECT, None)
            except (TypeError, AttributeError):
                pass
        item = self.game_selection.get_selected_item()
        if item and self.main_stack.get_visible_child_name() == "details":
            self._show_details(item.game)

    def _open_details_selected(self):
        item = self.game_selection.get_selected_item()
        if item:
            self._open_details(item.game)

    def _on_cabinet_action(self, action: str):
        if action == "options":
            self._open_settings()
            return False
        if action == "refresh":
            self.refresh()
            return False
        if action == "random":
            self._surprise_selected()
            return False
        if action == "search":
            self.search_entry.grab_focus()
            return False

        on_reader = self.main_stack.get_visible_child_name() == "reader"
        if on_reader:
            if action == "back":
                self._close_reader()
            elif action in ("left", "right"):
                self._reader_turn(-1 if action == "left" else 1)
            elif action in ("prev", "next"):
                self._reader_step(-1 if action == "prev" else 1)
            elif action in ("up", "down"):
                self._reader_step(-1 if action == "up" else 1)
            return False

        on_details = self.main_stack.get_visible_child_name() == "details"
        if on_details:
            if action == "confirm":
                if self._playback_item is self._selected_game:
                    self._toggle_playback_pause()
                else:
                    self._launch_selected()
            elif action == "back":
                self._close_details()
            elif action == "extra":
                self._toggle_favorite_selected()
            elif action in ("left", "right"):
                self._select_index(self._selected_index() + (-1 if action == "left" else 1))
            elif action in ("prev", "next"):
                self._cycle_category(-1 if action == "prev" else 1)
            return False

        if self.search_entry.has_focus():
            if action == "back":
                if self.search_entry.get_text():
                    self.search_entry.set_text("")
                else:
                    self._set_nav_target(self._library_nav_target())
            elif action == "confirm":
                self._set_nav_target(self._library_nav_target())
            return False

        if action == "back":
            if self.search_entry.get_text():
                self.search_entry.set_text("")
            elif self._nav_target == "sidebar":
                self._set_nav_target(self._library_nav_target())
            elif self._category != CATEGORY_HOME:
                self._select_category(CATEGORY_HOME)
            elif self.is_fullscreen():
                self.unfullscreen()
            return False

        if action == "confirm":
            if self._nav_target == "sidebar":
                self._set_nav_target(self._library_nav_target())
            elif self._nav_target == "home":
                self._activate_home_focus()
            else:
                self._open_details_selected()
            return False

        if action == "extra":
            if self._nav_target == "home":
                self._toggle_favorite_item(self._focused_home_game())
            else:
                self._toggle_favorite_selected()
            return False

        if action in ("prev", "next"):
            self._cycle_category(-1 if action == "prev" else 1)
            return False

        if action in ("left", "right", "up", "down"):
            self._move_cabinet(action)
        return False

    def _activate_home_focus(self):
        rows = self._home_focus_rows
        if not rows:
            self._on_hero_play()
            return
        row, col = self._home_focus_pos
        if row >= len(rows) or col >= len(rows[row]):
            self._on_hero_play()
            return
        rows[row][col].activate()

    def _move_cabinet(self, action: str):
        if self._nav_target == "sidebar":
            if action == "right":
                self._set_nav_target(self._library_nav_target())
            elif action in ("up", "down"):
                self._cycle_category(-1 if action == "up" else 1)
            return

        if self._nav_target == "home":
            lengths = [len(row) for row in self._home_focus_rows if row]
            next_pos = move_home_focus(
                lengths, self._home_focus_pos[0], self._home_focus_pos[1], action
            )
            if next_pos is None:
                self._set_nav_target("sidebar")
                return
            self._home_focus_pos = next_pos
            self._restore_home_focus()
            return

        if "kabin-nav-focus" not in self.game_grid.get_css_classes():
            self.game_grid.add_css_class("kabin-nav-focus")
        count = self.game_selection.get_n_items()
        if not count:
            if action == "left":
                self._set_nav_target("sidebar")
            return
        next_index = move_grid_index(
            self._selected_index(), count, self._grid_column_count(), action
        )
        if next_index is None:
            self._set_nav_target("sidebar")
            return
        self._select_index(next_index)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        control = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if (control and keyval in (Gdk.KEY_f, Gdk.KEY_F)) or keyval == Gdk.KEY_slash:
            self.search_entry.grab_focus()
            return True
        if control and keyval == Gdk.KEY_comma:
            self._open_settings()
            return True
        if keyval == Gdk.KEY_BackSpace and self.main_stack.get_visible_child_name() in ("details", "reader"):
            self._on_cabinet_action("back")
            return True
        if (
            self._reader_pages
            and self.main_stack.get_visible_child_name() == "reader"
            and not self._cabinet_chrome_focused()
            and keyval == Gdk.KEY_space
        ):
            self._reader_step(1)
            return True
        if self._playback and not self._cabinet_chrome_focused():
            if keyval in (Gdk.KEY_space, Gdk.KEY_AudioPlay, Gdk.KEY_AudioPause):
                self._toggle_playback_pause()
                return True
            if keyval == Gdk.KEY_AudioStop:
                self._stop_playback()
                return True
            if keyval == Gdk.KEY_AudioNext:
                self._skip_playback(1)
                return True
            if keyval == Gdk.KEY_AudioPrev:
                self._skip_playback(-1)
                return True
        if keyval == Gdk.KEY_F11:
            if self.is_fullscreen():
                self.unfullscreen()
            else:
                self.fullscreen()
            return True
        action = _KEY_ACTIONS.get(keyval)
        if action and (not self._cabinet_chrome_focused() or keyval == Gdk.KEY_Escape):
            self._on_cabinet_action(action)
            return True
        if (
            not self._cabinet_chrome_focused()
            and self.main_stack.get_visible_child_name() not in ("details", "reader")
        ):
            letter = Gdk.keyval_to_unicode(keyval)
            if letter:
                character = chr(letter)
                if character.isalnum() and not self._is_on_home():
                    self._jump_to_letter(character)
                    return True
        return False

    def _visible_titles(self) -> list[str]:
        titles = []
        for index in range(self.game_selection.get_n_items()):
            item = self.game_selection.get_item(index)
            titles.append(item.game.title if item else "")
        return titles

    def _jump_to_letter(self, prefix: str):
        index = first_index_for_prefix(self._visible_titles(), prefix)
        if index is None:
            self._toast(f"No titles start with {prefix.upper()}")
            return
        self._set_nav_target("grid")
        self._select_index(index)

    def _surprise_selected(self):
        index = pick_random_index(self.game_selection.get_n_items())
        if index is None:
            self._toast("Nothing here to surprise you with")
            return
        self._set_nav_target(self._library_nav_target() if not self._is_on_home() else "grid")
        self._select_index(index)
        item = self.game_selection.get_selected_item()
        if item:
            self._open_details(item.game)
            self._toast(f"Surprise · {item.game.title}")
