from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

from .artwork import (
    CoverCandidate,
    install_cover_from_file,
    install_cover_from_url,
    search_cover_candidates,
)
from .kinds import kind_for


class CoverPicker(Adw.Window):
    def __init__(self, game, config, on_chosen, transient_for=None):
        super().__init__(transient_for=transient_for, modal=True, title="Change cover")
        self.set_default_size(720, 560)
        self.add_css_class("kabin-window")
        self.add_css_class("kabin-cover-picker")
        self._game = game
        self._config = config
        self._on_chosen = on_chosen
        self._search_generation = 0
        self._search_timeout = 0
        kind = kind_for(game)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(8)
        page.set_margin_bottom(16)
        page.set_margin_start(16)
        page.set_margin_end(16)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_text(game.title)
        self.search_entry.set_placeholder_text("Search covers…")
        self.search_entry.connect("activate", lambda *_: self._search())
        self.search_entry.connect("search-changed", self._on_search_changed)
        page.append(self.search_entry)

        self.status = Gtk.Label(xalign=0)
        self.status.add_css_class("dim-label")
        self.status.set_wrap(True)
        page.append(self.status)

        self.grid = Gtk.FlowBox()
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_max_children_per_line(4)
        self.grid.set_min_children_per_line(2)
        self.grid.set_column_spacing(10)
        self.grid.set_row_spacing(10)
        self.grid.set_homogeneous(True)
        scroller = Gtk.ScrolledWindow(child=self.grid)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_min_content_height(280)
        page.append(scroller)

        actions = Gtk.Box(spacing=8)
        file_button = Gtk.Button(label="Choose image…")
        file_button.connect("clicked", self._choose_file)
        actions.append(file_button)
        page.append(actions)

        catalog = {
            "book": "Open Library",
            "comic": "Open Library",
            "music": "Cover Art Archive",
        }.get(kind.id, "SteamGridDB")
        if kind.id not in {"book", "comic", "music"} and not config.artwork.get("steamgriddb_api_key"):
            self.status.set_label(
                f"Add a SteamGridDB key in Settings to search {catalog}, or choose an image from this device."
            )
        else:
            self.status.set_label(f"Results from {catalog}. Pick one, or choose an image from this device.")

        toolbar.set_content(page)
        self.set_content(toolbar)
        if kind.id in {"book", "comic", "music"} or config.artwork.get("steamgriddb_api_key"):
            GLib.idle_add(self._search)

    def _on_search_changed(self, *_args):
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
        self._search_timeout = GLib.timeout_add(400, self._run_delayed_search)

    def _run_delayed_search(self):
        self._search_timeout = 0
        self._search()
        return False

    def _clear_grid(self):
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)

    def _search(self):
        title = self.search_entry.get_text().strip() or self._game.title
        kind = kind_for(self._game)
        creator = (self._game.creators[0] if self._game.creators else "") or ""
        api_key = self._config.artwork.get("steamgriddb_api_key", "")
        if kind.id not in {"book", "comic", "music"} and not api_key:
            return False
        self._search_generation += 1
        generation = self._search_generation
        self.status.set_label("Searching…")
        self._clear_grid()

        def worker():
            try:
                candidates = search_cover_candidates(
                    title,
                    kind.id,
                    creator=creator,
                    api_key=api_key,
                )
            except (OSError, ValueError, KeyError):
                candidates = []
            GLib.idle_add(self._show_candidates, generation, candidates)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _show_candidates(self, generation, candidates: list[CoverCandidate]):
        if generation != self._search_generation:
            return False
        self._clear_grid()
        if not candidates:
            self.status.set_label("No covers found. Try another search, or choose an image from this device.")
            return False
        self.status.set_label("Choose a cover.")
        for candidate in candidates:
            self.grid.append(self._candidate_button(candidate))
        return False

    def _candidate_button(self, candidate: CoverCandidate) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("flat")
        button.add_css_class("kabin-cover-choice")
        button.set_tooltip_text(candidate.caption)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        picture = Gtk.Picture()
        picture.set_can_shrink(True)
        picture.set_content_fit(Gtk.ContentFit.COVER)
        picture.set_size_request(120, 168)
        picture.add_css_class("kabin-cover-choice-art")
        if candidate.thumb_url:
            picture.set_file(Gio.File.new_for_uri(candidate.thumb_url))
        caption = Gtk.Label(label=candidate.caption, xalign=0)
        caption.set_ellipsize(Pango.EllipsizeMode.END)
        caption.add_css_class("caption")
        caption.add_css_class("dim-label")
        box.append(picture)
        box.append(caption)
        button.set_child(box)
        button.connect("clicked", lambda *_: self._pick_candidate(candidate))
        return button

    def _pick_candidate(self, candidate: CoverCandidate):
        self.status.set_label("Saving cover…")
        item_id = self._game.id

        def worker():
            try:
                path = install_cover_from_url(item_id, candidate.image_url)
            except (OSError, ValueError):
                path = None
            GLib.idle_add(self._finish_choice, path, "Could not download that cover.")

        threading.Thread(target=worker, daemon=True).start()

    def _choose_file(self, *_args):
        dialog = Gtk.FileDialog(title="Choose cover")
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_mime_type("image/jpeg")
        image_filter.add_mime_type("image/png")
        image_filter.add_mime_type("image/webp")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_file_chosen)

    def _on_file_chosen(self, dialog, result):
        try:
            chosen = dialog.open_finish(result)
        except Exception:
            return
        if not chosen:
            return
        path = install_cover_from_file(self._game.id, Path(chosen.get_path()))
        self._finish_choice(path, "That file is not a usable image.")

    def _finish_choice(self, path, error: str):
        if not path:
            self.status.set_label(error)
            return False
        self._config.set_cover(self._game.id, str(path))
        self._on_chosen(path)
        self.close()
        return False
