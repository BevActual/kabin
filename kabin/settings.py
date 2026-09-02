import shlex
import threading
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .emulation import PRESETS, connected_controllers, settings_for_preset, system_readiness
from .emulators import detect_emulators, emulator_command, launch_environment
from .managed import ManagedRuntimeError, install_runtime, recommended_runtime
from .network import discover_hosts, fetch_remote_library, pair_with_host
from .systems import SYSTEMS, firmware_files, get_system
from .kinds import FOLDER_KINDS, get_kind
from .streaming import media_capabilities


# Text rows emit "changed" per keystroke; wait for a pause before acting
# on edits that cost more than a repaint.
TEXT_EDIT_DEBOUNCE_MS = 500


def custom_emulator_command_error(text: str) -> str | None:
    """None if `text` is a usable custom emulator command, else a short
    reason it isn't. Checked here (before saving) rather than only at
    launch time (`sources.roms.custom_command`'s `shlex.split`, run
    lazily inside the launch closure) so a quoting mistake gets caught
    where it was made instead of surfacing as a confusing toast far
    later, the next time that ROM is played."""
    if "{rom}" not in text:
        return "Must include {rom}"
    try:
        shlex.split(text)
    except ValueError as exc:
        return str(exc)
    return None


class AddRomDirDialog(Adw.Window):
    def __init__(self, transient_for, on_added, initial_system=None):
        super().__init__(transient_for=transient_for, modal=True, title="Add Game Library")
        self.set_default_size(520, -1)
        self._on_added = on_added
        self._systems = SYSTEMS
        self._emulator_choices = []

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()

        group = Adw.PreferencesGroup(
            title="Library",
            description="Choose a system and Kabin will find a compatible emulator.",
        )

        self.system_row = Adw.ComboRow(
            title="System",
            model=Gtk.StringList.new([system.name for system in self._systems]),
        )
        self.system_row.connect("notify::selected", self._on_system_changed)
        group.add(self.system_row)

        self.path_row = Adw.ActionRow(title="Folder", subtitle="Not selected")
        choose_button = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose_button.connect("clicked", self._on_choose_folder)
        self.path_row.add_suffix(choose_button)
        group.add(self.path_row)

        self.extensions_row = Adw.ActionRow(title="Recognized files")
        group.add(self.extensions_row)

        self.emulator_row = Adw.ComboRow(title="Emulator")
        self.emulator_row.connect("notify::selected", self._on_emulator_changed)
        group.add(self.emulator_row)

        self.detection_row = Adw.ActionRow()
        self.install_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.install_button.add_css_class("suggested-action")
        self.install_button.connect("clicked", self._on_install_emulator)
        self.install_button.set_visible(False)
        self.detection_row.add_suffix(self.install_button)
        group.add(self.detection_row)

        self.bios_row = Adw.ActionRow(title="Console firmware")
        self.bios_button = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        self.bios_button.connect("clicked", self._on_choose_bios_folder)
        self.bios_row.add_suffix(self.bios_button)
        self.bios_row.set_visible(False)
        group.add(self.bios_row)

        self.custom_emulator_entry = Adw.EntryRow(
            title="Custom command — use {rom} for the game path"
        )
        self.custom_emulator_entry.set_visible(False)
        self.custom_emulator_entry.connect("changed", lambda *_: self._update_add_button())
        group.add(self.custom_emulator_entry)

        page.add(group)

        add_button = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_button.add_css_class("suggested-action")
        add_button.connect("clicked", self._on_add_clicked)
        add_button.set_sensitive(False)
        self.add_button = add_button

        action_group = Adw.PreferencesGroup()
        action_group.add(add_button)
        page.add(action_group)

        toolbar_view.set_content(page)
        self._selected_path = None
        self._bios_path = None
        self._install_spec = None
        self.set_content(toolbar_view)
        if initial_system:
            selected = next(
                (index for index, system in enumerate(self._systems) if system.id == initial_system),
                0,
            )
            self.system_row.set_selected(selected)
        self._on_system_changed(self.system_row, None)

    def _on_choose_folder(self, button):
        dialog = Gtk.FileDialog(title="Select ROM Folder")
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder:
            self._selected_path = folder.get_path()
            self.path_row.set_subtitle(self._selected_path)
            self._update_add_button()

    def _on_system_changed(self, _row, _pspec):
        system = self._systems[self.system_row.get_selected()]
        self.extensions_row.set_subtitle(", ".join(f".{ext}" for ext in system.extensions))
        self._bios_path = None
        self.bios_row.set_visible(system.firmware_required)
        self.bios_row.set_subtitle(system.firmware_hint if system.firmware_required else "")
        self._emulator_choices = detect_emulators(system)
        labels = [choice.name for choice in self._emulator_choices] + ["Custom command…"]
        self.emulator_row.set_model(Gtk.StringList.new(labels))
        if self._emulator_choices:
            names = ", ".join(choice.name for choice in self._emulator_choices)
            self.detection_row.set_title("Ready")
            self.detection_row.set_subtitle(f"Detected {names}")
            self._install_spec = None
            self.install_button.set_visible(False)
        else:
            self._install_spec = recommended_runtime(system.id)
            self.detection_row.set_title("No supported emulator detected")
            if self._install_spec:
                self.detection_row.set_subtitle(
                    f"Kabin can securely download and manage {self._install_spec.name}."
                )
                self.install_button.set_label(f"Install {self._install_spec.name}")
                self.install_button.set_sensitive(True)
                self.install_button.set_visible(True)
            else:
                self.detection_row.set_subtitle(
                    "Install a supported standalone emulator, or use a custom command."
                )
                self.install_button.set_visible(False)
        self._on_emulator_changed(self.emulator_row, None)

    def _on_choose_bios_folder(self, _button):
        dialog = Gtk.FileDialog(title="Select Console Firmware Folder")
        dialog.select_folder(self, None, self._on_bios_folder_selected)

    def _on_bios_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if not folder:
            return
        path = folder.get_path()
        found = firmware_files(path)
        if found:
            self._bios_path = path
            noun = "file" if len(found) == 1 else "files"
            self.bios_row.set_subtitle(f"Ready · {len(found)} firmware {noun} found")
            self.bios_row.remove_css_class("error")
        else:
            self._bios_path = None
            self.bios_row.set_subtitle("No .bin or .rom firmware files found in that folder")
            self.bios_row.add_css_class("error")
        self._update_add_button()

    def _on_install_emulator(self, _button):
        if not self._install_spec:
            return
        spec = self._install_spec
        self.install_button.set_sensitive(False)
        self.install_button.set_label("Downloading…")
        self.detection_row.set_subtitle(
            f"Downloading {spec.name} from its official release repository."
        )

        def worker():
            error = None
            try:
                install_runtime(spec)
            except (ManagedRuntimeError, OSError, ValueError) as exc:
                error = str(exc)
            GLib.idle_add(self._on_runtime_install_finished, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_runtime_install_finished(self, error):
        if error:
            self.detection_row.set_title("Installation failed")
            self.detection_row.set_subtitle(error)
            if self._install_spec:
                self.install_button.set_label(f"Retry {self._install_spec.name}")
                self.install_button.set_sensitive(True)
        else:
            self._on_system_changed(self.system_row, None)
        return False

    def _on_emulator_changed(self, _row, _pspec):
        custom = self.emulator_row.get_selected() >= len(self._emulator_choices)
        self.custom_emulator_entry.set_visible(custom)
        self._update_add_button()

    def _update_add_button(self):
        system = self._systems[self.system_row.get_selected()]
        custom = self.emulator_row.get_selected() >= len(self._emulator_choices)
        custom_valid = (
            custom_emulator_command_error(self.custom_emulator_entry.get_text()) is None
            if custom
            else True
        )
        firmware_valid = not system.firmware_required or bool(self._bios_path)
        self.add_button.set_sensitive(bool(self._selected_path and custom_valid and firmware_valid))

    def _on_add_clicked(self, button):
        if not self._selected_path:
            return
        system = self._systems[self.system_row.get_selected()]
        selected = self.emulator_row.get_selected()
        if selected < len(self._emulator_choices):
            emulator = self._emulator_choices[selected].to_config()
        else:
            emulator = self.custom_emulator_entry.get_text().strip()
            if custom_emulator_command_error(emulator) is not None:
                self.custom_emulator_entry.add_css_class("error")
                return
        self._on_added(
            self._selected_path,
            system.id,
            list(system.extensions),
            emulator,
            self._bios_path,
        )
        self.close()


class AddMediaDirDialog(Adw.Window):
    def __init__(self, transient_for, on_added):
        super().__init__(transient_for=transient_for, modal=True, title="Add Media Folder")
        self.set_default_size(480, -1)
        self._on_added = on_added
        self._kinds = list(FOLDER_KINDS)
        self._selected_path = None

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Library",
            description="Kabin plays music and movies and reads PDF, EPUB, FB2, TXT, CBZ, CBR, CBT, and CB7 itself; MOBI and AZW3 books open in your reader.",
        )
        self.kind_row = Adw.ComboRow(
            title="Media type",
            model=Gtk.StringList.new([kind.plural for kind in self._kinds]),
        )
        self.kind_row.connect("notify::selected", self._on_kind_changed)
        group.add(self.kind_row)

        self.path_row = Adw.ActionRow(title="Folder", subtitle="Not selected")
        choose_button = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose_button.connect("clicked", self._on_choose_folder)
        self.path_row.add_suffix(choose_button)
        group.add(self.path_row)

        self.files_row = Adw.ActionRow(title="Recognized files")
        group.add(self.files_row)
        page.add(group)

        add_button = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_button.add_css_class("suggested-action")
        add_button.connect("clicked", self._on_add_clicked)
        add_button.set_sensitive(False)
        self.add_button = add_button
        action_group = Adw.PreferencesGroup()
        action_group.add(add_button)
        page.add(action_group)
        toolbar_view.set_content(page)
        self.set_content(toolbar_view)
        self._on_kind_changed(self.kind_row, None)

    def _on_kind_changed(self, _row, _pspec):
        kind = self._kinds[self.kind_row.get_selected()]
        self.files_row.set_subtitle(", ".join(sorted(ext.lstrip(".") for ext in kind.extensions)))

    def _on_choose_folder(self, _button):
        dialog = Gtk.FileDialog(title="Select Media Folder")
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:
            return
        if folder:
            self._selected_path = folder.get_path()
            self.path_row.set_subtitle(self._selected_path)
            self.add_button.set_sensitive(True)

    def _on_add_clicked(self, _button):
        if not self._selected_path:
            return
        kind = self._kinds[self.kind_row.get_selected()]
        self._on_added(self._selected_path, kind.id)
        self.close()


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, config, host_service=None, initial_page=None, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.host_service = host_service
        self._pending_edits: dict = {}
        self.connect("close-request", self._on_close_request)
        self.set_title("Kabin Settings")
        self.set_default_size(820, 720)
        self.set_search_enabled(True)
        self.add_css_class("kabin-settings")

        self.network_page = Adw.PreferencesPage(
            title="Network", icon_name="network-workgroup-symbolic"
        )
        self.emulation_page = Adw.PreferencesPage(
            title="Emulation", icon_name="input-gaming-symbolic"
        )
        self.library_page = Adw.PreferencesPage(
            title="Library", icon_name="view-grid-symbolic"
        )
        self.artwork_page = Adw.PreferencesPage(
            title="Artwork", icon_name="image-x-generic-symbolic"
        )
        for page in (
            self.network_page,
            self.emulation_page,
            self.library_page,
            self.artwork_page,
        ):
            self.add(page)
        page_by_name = {
            "network": self.network_page,
            "emulation": self.emulation_page,
            "library": self.library_page,
            "artwork": self.artwork_page,
        }
        if initial_page in page_by_name:
            self.set_visible_page(page_by_name[initial_page])

        network_group = Adw.PreferencesGroup(
            title="Network",
            description="Host your Kabin library or discover another Kabin on this network.",
        )
        self.host_switch = Adw.SwitchRow(
            title="Kabin Host",
            subtitle="Share this library with paired Kabin devices on your local network.",
        )
        self.host_switch.set_active(bool(self.config.network["host_enabled"]))
        self.host_switch.connect("notify::active", self._on_host_toggled)
        network_group.add(self.host_switch)

        self.host_name_row = Adw.EntryRow(title="Host name")
        self.host_name_row.set_text(self.config.network["host_name"])
        self.host_name_row.connect("changed", self._on_host_name_changed)
        network_group.add(self.host_name_row)

        self.host_status_row = Adw.ActionRow(title="Host status")
        self._update_host_status()
        network_group.add(self.host_status_row)

        capabilities = media_capabilities()
        helper = capabilities.get("native_helper") or {}
        encoder_names = ", ".join(item["encoder"] for item in capabilities.get("encoders") or [])
        capture_names = ", ".join(capabilities.get("captures") or [])
        if capabilities.get("ready"):
            media_subtitle = (
                f"Ready · {capture_names or 'test pattern'} · {encoder_names}"
            )
        else:
            media_subtitle = helper.get("error") or (
                "Build kabin-media-helper to play media and stream this library from Kabin"
            )
        self.media_status_row = Adw.ActionRow(
            title="Kabin player",
            subtitle=media_subtitle,
        )
        self.media_status_row.set_icon_name(
            "emblem-ok-symbolic" if capabilities.get("ready") else "dialog-warning-symbolic"
        )
        network_group.add(self.media_status_row)

        pairing_row = Adw.ButtonRow(title="Create Pairing Code")
        pairing_row.add_css_class("suggested-action")
        pairing_row.connect("activated", self._on_create_pairing_code)
        network_group.add(pairing_row)
        self.pairing_status_row = Adw.ActionRow(
            title="Pairing", subtitle="Create a one-time code on the host, then enter it on the client."
        )
        network_group.add(self.pairing_status_row)

        discover_row = Adw.ButtonRow(title="Find Kabin Hosts")
        discover_row.add_css_class("suggested-action")
        discover_row.connect("activated", self._on_discover_hosts)
        network_group.add(discover_row)
        self.remote_code_row = Adw.EntryRow(title="Pairing code from host")
        network_group.add(self.remote_code_row)
        self.network_page.add(network_group)

        self.discovered_group = Adw.PreferencesGroup(title="Available Hosts")
        self.network_page.add(self.discovered_group)
        self._discovered_rows = []
        self._show_saved_remote_hosts()

        self.devices_group = Adw.PreferencesGroup(
            title="Paired Devices",
            description="Devices allowed to browse this host and create streaming sessions.",
        )
        self.network_page.add(self.devices_group)
        self._device_rows = []
        self._refresh_paired_devices()

        play_group = Adw.PreferencesGroup(
            title="Play Defaults",
            description="Fullscreen is applied at launch. VSync and integer scaling are passed to MAME and Mupen64Plus. BIOS folders are linked into DuckStation and PCSX2 data directories.",
        )
        self._preset_ids = list(PRESETS)
        current_preset = self.config.emulation.get("preset", "balanced")
        self.preset_row = Adw.ComboRow(
            title="Profile",
            subtitle=PRESETS.get(current_preset, PRESETS["balanced"])["description"],
            model=Gtk.StringList.new([PRESETS[key]["name"] for key in self._preset_ids]),
        )
        self.preset_row.set_selected(
            self._preset_ids.index(current_preset) if current_preset in self._preset_ids else 0
        )
        self.preset_row.connect("notify::selected", self._on_preset_changed)
        play_group.add(self.preset_row)

        self._play_switches = {}
        # Rewind stays in the preset/config dict for forward compatibility,
        # but no adapter reads it yet — keep it out of the UI so Settings
        # only shows switches that actually change a launch.
        for key, title, subtitle in (
            ("fullscreen", "Start fullscreen", "Launch games directly into fullscreen mode."),
            ("vsync", "Vertical sync", "Reduce tearing by synchronizing frames with the display."),
            ("integer_scaling", "Integer scaling", "Keep classic pixels evenly sized."),
        ):
            row = Adw.SwitchRow(title=title, subtitle=subtitle)
            row.set_active(bool(self.config.emulation.get(key, False)))
            row.connect("notify::active", self._make_emulation_toggle_handler(key))
            play_group.add(row)
            self._play_switches[key] = row

        controllers = connected_controllers()
        controller_row = Adw.ActionRow(
            title="Controllers",
            subtitle=(
                f"{', '.join(controllers)} · D-pad moves, A opens, B goes back, Y favorites"
                if controllers
                else "No game controller detected · keyboard arrows still browse the library"
            ),
        )
        controller_row.set_icon_name(
            "input-gaming-symbolic" if controllers else "dialog-warning-symbolic"
        )
        play_group.add(controller_row)
        self.emulation_page.add(play_group)

        artwork_group = Adw.PreferencesGroup(
            title="Game Artwork",
            description="Kabin sends normalized game titles to SteamGridDB only when an API key is configured.",
        )
        artwork_key_row = Adw.ActionRow(
            title="SteamGridDB API key",
            subtitle="Stored locally with owner-only permissions",
        )
        self.artwork_key_entry = Gtk.PasswordEntry(
            show_peek_icon=True,
            valign=Gtk.Align.CENTER,
        )
        self.artwork_key_entry.set_size_request(280, -1)
        self.artwork_key_entry.set_text(self.config.artwork.get("steamgriddb_api_key", ""))
        self.artwork_key_entry.connect("changed", self._on_artwork_key_changed)
        artwork_key_row.add_suffix(self.artwork_key_entry)
        artwork_key_row.set_activatable_widget(self.artwork_key_entry)
        artwork_group.add(artwork_key_row)
        key_link = Gtk.LinkButton.new_with_label(
            "https://www.steamgriddb.com/profile/preferences",
            "Get an API key",
        )
        key_link_row = Adw.ActionRow(
            title="SteamGridDB account",
            subtitle="Generate or manage your personal API key",
        )
        key_link_row.add_suffix(key_link)
        key_link_row.set_activatable_widget(key_link)
        artwork_group.add(key_link_row)
        self.artwork_page.add(artwork_group)

        book_art_group = Adw.PreferencesGroup(
            title="Book Artwork",
            description="Missing book jackets are fetched from Open Library after the library is on screen. No API key.",
        )
        self.openlibrary_switch = Adw.SwitchRow(
            title="Open Library covers",
            subtitle="Search by title and author, then cache the jacket locally",
        )
        self.openlibrary_switch.set_active(bool(self.config.artwork.get("openlibrary_covers", True)))
        self.openlibrary_switch.connect("notify::active", self._on_openlibrary_changed)
        book_art_group.add(self.openlibrary_switch)
        ol_link = Gtk.LinkButton.new_with_label(
            "https://openlibrary.org",
            "Open Library",
        )
        ol_link_row = Adw.ActionRow(
            title="Cover source",
            subtitle="Internet Archive's public book catalog",
        )
        ol_link_row.add_suffix(ol_link)
        ol_link_row.set_activatable_widget(ol_link)
        book_art_group.add(ol_link_row)
        self.artwork_page.add(book_art_group)

        sources_group = Adw.PreferencesGroup(title="Sources")
        for source_id, label in (
            ("steam", "Steam"),
            ("desktop", "Other installed apps categorized as Games"),
            ("roms", "ROM directories"),
            ("remote", "Paired Kabin hosts"),
            ("book", "Books"),
            ("comic", "Comics"),
            ("music", "Music"),
            ("video", "Movies"),
        ):
            row = Adw.SwitchRow(title=label)
            row.set_active(self.config.sources.get(source_id, True))
            row.connect("notify::active", self._make_source_toggle_handler(source_id))
            sources_group.add(row)
        self.library_page.add(sources_group)

        self.hidden_group = Adw.PreferencesGroup(
            title="Hidden Titles",
            description="Restore titles that were hidden from their detail page.",
        )
        self.library_page.add(self.hidden_group)
        self._hidden_rows = []
        self._refresh_hidden_games()

        self.readiness_group = Adw.PreferencesGroup(
            title="Emulation Center",
            description="Every console's library, standalone emulator, and firmware status at a glance.",
        )
        self.emulation_page.add(self.readiness_group)

        self.roms_group = Adw.PreferencesGroup(
            title="Game Libraries",
            description="Add or remove the folders Kabin scans for games.",
        )
        add_row = Adw.ButtonRow(title="Add Game Library")
        add_row.add_css_class("suggested-action")
        add_row.connect("activated", self._on_add_rom_dir)
        self.roms_group.add(add_row)
        self.library_page.add(self.roms_group)

        self.media_group = Adw.PreferencesGroup(
            title="Media Folders",
            description="Books, comics, music, and movies. Kabin hosts and plays music and video, queues albums, and syncs resume to the host. Kabin also reads PDF, EPUB, FB2, TXT, CBZ, CBR, CBT, and CB7 itself; MOBI and AZW3 books still open in your reader.",
        )
        add_media = Adw.ButtonRow(title="Add Media Folder")
        add_media.add_css_class("suggested-action")
        add_media.connect("activated", self._on_add_media_dir)
        self.media_group.add(add_media)
        self.library_page.add(self.media_group)

        self._rom_dir_rows = []
        self._media_dir_rows = []
        self._readiness_rows = []
        self._refresh_rom_dir_rows()
        self._refresh_media_dir_rows()

    def _on_host_toggled(self, row, _pspec):
        enabled = row.get_active()
        self.config.network["host_enabled"] = enabled
        self.config.save()
        if self.host_service:
            if enabled:
                self.host_service.start()
            else:
                self.host_service.stop()
        self._update_host_status()

    def _debounce_edit(self, key: str, callback, delay_ms: int = TEXT_EDIT_DEBOUNCE_MS):
        """Run `callback` once the user stops typing.

        Text rows emit "changed" per keystroke, and some of these edits are
        expensive enough that chasing every character is harmful - renaming
        the host used to stop and restart the HTTP server (rebinding the
        socket and respawning avahi-publish, dropping any in-flight request)
        once per character typed.
        """
        pending = self._pending_edits.pop(key, None)
        if pending:
            GLib.source_remove(pending[0])

        def fire():
            self._pending_edits.pop(key, None)
            callback()
            return False

        self._pending_edits[key] = (GLib.timeout_add(delay_ms, fire), callback)

    def _flush_pending_edits(self):
        """Apply anything still waiting on its debounce - closing the
        window right after typing must not silently drop the edit."""
        for key in list(self._pending_edits):
            source, callback = self._pending_edits.pop(key)
            GLib.source_remove(source)
            callback()

    def _on_close_request(self, *_args):
        self._flush_pending_edits()
        return False

    def _on_host_name_changed(self, _row):
        self._debounce_edit("host_name", self._apply_host_name)

    def _apply_host_name(self):
        name = self.host_name_row.get_text().strip()
        if not name or name == self.config.network.get("host_name"):
            return
        self.config.network["host_name"] = name
        self.config.save()
        if self.host_service and self.host_service.running:
            self.host_service.stop()
            self.host_service.start()
        self._update_host_status()

    def _on_create_pairing_code(self, _row):
        if not self.host_service or not self.host_service.running:
            self.pairing_status_row.set_subtitle("Enable Kabin Host before creating a code.")
            self.pairing_status_row.set_icon_name("dialog-warning-symbolic")
            return
        code = self.host_service.create_pairing_code()
        self.pairing_status_row.set_title(f"Pairing code · {code}")
        self.pairing_status_row.set_subtitle("Valid for five minutes and one device.")
        self.pairing_status_row.set_icon_name("channel-secure-symbolic")

    def _show_saved_remote_hosts(self):
        for row in self._discovered_rows:
            self.discovered_group.remove(row)
        self._discovered_rows = []
        for host in self.config.network.get("remote_hosts", []):
            row = Adw.ActionRow(
                title=host["name"],
                subtitle=f"Paired · {host['address']}:{host['port']}",
            )
            row.set_icon_name("emblem-ok-symbolic")
            disconnect = Gtk.Button(label="Disconnect", valign=Gtk.Align.CENTER)
            disconnect.add_css_class("destructive-action")
            disconnect.connect(
                "clicked", lambda _button, name=host["name"]: self._disconnect_host(name)
            )
            row.add_suffix(disconnect)
            self.discovered_group.add(row)
            self._discovered_rows.append(row)

    def _disconnect_host(self, name):
        self.config.remove_remote_host(name)
        self._show_saved_remote_hosts()

    def _refresh_paired_devices(self):
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows = []
        devices = self.config.network.get("paired_devices", [])
        if not devices:
            row = Adw.ActionRow(
                title="No paired devices",
                subtitle="Create a pairing code to authorize another Kabin device.",
            )
            row.set_icon_name("network-offline-symbolic")
            self.devices_group.add(row)
            self._device_rows.append(row)
            return
        for index, device in enumerate(devices):
            row = Adw.ActionRow(title=device.get("name", "Kabin device"), subtitle="Authorized")
            row.set_icon_name("channel-secure-symbolic")
            revoke = Gtk.Button(label="Revoke", valign=Gtk.Align.CENTER)
            revoke.add_css_class("destructive-action")
            revoke.connect("clicked", lambda _button, target=index: self._revoke_device(target))
            row.add_suffix(revoke)
            self.devices_group.add(row)
            self._device_rows.append(row)

    def _revoke_device(self, index):
        self.config.remove_paired_device(index)
        self._refresh_paired_devices()

    def _update_host_status(self):
        if self.host_service and self.host_service.running:
            self.host_status_row.set_subtitle(
                f"Online · port {self.host_service.server.server_port} · authentication required"
            )
            self.host_status_row.set_icon_name("network-server-symbolic")
        elif self.host_service and self.host_service.error:
            self.host_status_row.set_subtitle(f"Could not start · {self.host_service.error}")
            self.host_status_row.set_icon_name("dialog-error-symbolic")
        else:
            self.host_status_row.set_subtitle("Offline")
            self.host_status_row.set_icon_name("network-offline-symbolic")

    def _on_discover_hosts(self, row):
        row.set_title("Searching…")

        def worker():
            hosts = discover_hosts()
            GLib.idle_add(self._show_discovered_hosts, row, hosts)

        threading.Thread(target=worker, daemon=True).start()

    def _show_discovered_hosts(self, button_row, hosts):
        button_row.set_title("Find Kabin Hosts")
        for row in self._discovered_rows:
            self.discovered_group.remove(row)
        self._discovered_rows = []
        if not hosts:
            row = Adw.ActionRow(
                title="No hosts found",
                subtitle="Enable Kabin Host on another computer connected to this network.",
            )
            row.set_icon_name("network-offline-symbolic")
            self.discovered_group.add(row)
            self._discovered_rows.append(row)
            return False
        for host in hosts:
            row = Adw.ActionRow(
                title=host["name"], subtitle=f"{host['address']}:{host['port']}"
            )
            row.set_icon_name("network-server-symbolic")
            pair_button = Gtk.Button(label="Pair", valign=Gtk.Align.CENTER)
            pair_button.add_css_class("suggested-action")
            pair_button.connect(
                "clicked", lambda _button, selected=host, target=row: self._pair_discovered_host(
                    selected, target
                )
            )
            row.add_suffix(pair_button)
            self.discovered_group.add(row)
            self._discovered_rows.append(row)
        return False

    def _pair_discovered_host(self, host, row):
        code = self.remote_code_row.get_text().strip()
        if len(code) != 6 or not code.isdigit():
            row.set_subtitle("Enter the six-digit code shown on the host.")
            row.set_icon_name("dialog-warning-symbolic")
            return
        row.set_subtitle("Pairing…")

        def worker():
            try:
                result = pair_with_host(
                    host, code, self.config.network["host_name"]
                )
                token = result["token"]
                library = fetch_remote_library(host, token)
                error = None
            except Exception as exc:
                token, library, error = None, None, str(exc)
            GLib.idle_add(self._on_pairing_finished, host, row, token, library, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_pairing_finished(self, host, row, token, library, error):
        if error:
            row.set_subtitle(f"Pairing failed · {error}")
            row.set_icon_name("dialog-error-symbolic")
            return False
        self.config.save_remote_host(host, token)
        count = library.get("count", 0)
        row.set_subtitle(f"Paired · {count} games available")
        row.set_icon_name("emblem-ok-symbolic")
        self.remote_code_row.set_text("")
        self._show_saved_remote_hosts()
        return False

    def _on_preset_changed(self, row, _pspec):
        preset_id = self._preset_ids[row.get_selected()]
        values = settings_for_preset(preset_id)
        self.config.emulation.update(values)
        row.set_subtitle(PRESETS[preset_id]["description"])
        for key, switch in self._play_switches.items():
            switch.set_active(values[key])
        self.config.save()

    def _make_emulation_toggle_handler(self, key):
        def handler(row, _pspec):
            self.config.emulation[key] = row.get_active()
            self.config.save()

        return handler

    def _on_artwork_key_changed(self, row):
        self._debounce_edit("artwork_key", lambda: self._apply_artwork_key(row))

    def _apply_artwork_key(self, row):
        self.config.artwork["steamgriddb_api_key"] = row.get_text().strip()
        self.config.save()

    def _on_openlibrary_changed(self, row, _pspec):
        self.config.artwork["openlibrary_covers"] = bool(row.get_active())
        self.config.save()

    def _make_source_toggle_handler(self, source_id):
        def handler(row, _pspec):
            self.config.sources[source_id] = row.get_active()
            self.config.save()

        return handler

    def _refresh_hidden_games(self):
        for row in self._hidden_rows:
            self.hidden_group.remove(row)
        self._hidden_rows = []
        self.hidden_group.set_visible(bool(self.config.hidden))
        for game_id in self.config.hidden:
            row = Adw.ActionRow(
                title=self.config.hidden_titles.get(game_id, "Hidden game"),
                subtitle=game_id,
            )
            row.set_icon_name("view-conceal-symbolic")
            restore = Gtk.Button(label="Restore", valign=Gtk.Align.CENTER)
            restore.connect(
                "clicked", lambda _button, target=game_id: self._restore_hidden_game(target)
            )
            row.add_suffix(restore)
            self.hidden_group.add(row)
            self._hidden_rows.append(row)

    def _restore_hidden_game(self, game_id):
        self.config.unhide(game_id)
        self._refresh_hidden_games()

    def _refresh_rom_dir_rows(self):
        for row in self._readiness_rows:
            self.readiness_group.remove(row)
        self._readiness_rows = []

        ready_count = 0
        configured_count = 0
        for system in SYSTEMS:
            status = system_readiness(system, self.config.rom_dirs)
            ready_count += int(status["ready"])
            configured_count += int(status["entry"] is not None)
            row = Adw.ActionRow(title=system.name, subtitle=status["state"])
            row.set_icon_name(
                "emblem-ok-symbolic" if status["ready"] else "dialog-warning-symbolic"
            )
            entry = status["entry"]
            emulator = entry.get("emulator") if entry else None
            if isinstance(emulator, dict) and emulator.get("executable"):
                test_button = Gtk.Button(label="Test", valign=Gtk.Align.CENTER)
                test_button.connect(
                    "clicked", lambda _button, profile=emulator, target=row: self._test_emulator(
                        profile, target
                    )
                )
                row.add_suffix(test_button)
            elif entry is None:
                setup_button = Gtk.Button(label="Setup", valign=Gtk.Align.CENTER)
                setup_button.add_css_class("suggested-action")
                setup_button.connect(
                    "clicked", lambda _button, system_id=system.id: self._open_system_setup(
                        system_id
                    )
                )
                row.add_suffix(setup_button)
            self.readiness_group.add(row)
            self._readiness_rows.append(row)

        self.readiness_group.set_description(
            f"{ready_count} ready · {configured_count} configured · {len(SYSTEMS)} supported consoles"
        )

        for row in self._rom_dir_rows:
            self.roms_group.remove(row)
        self._rom_dir_rows = []

        for index, entry in enumerate(self.config.rom_dirs):
            system = get_system(entry.get("system", ""))
            emulator = entry.get("emulator", "")
            emulator_name = emulator.get("name", "Unknown emulator") if isinstance(emulator, dict) else "Custom command"
            row = Adw.ActionRow(
                title=system.name if system else entry.get("system", "ROMs"),
                subtitle=f"{emulator_name} · {entry.get('path', '')}",
            )
            remove_button = Gtk.Button(
                icon_name="user-trash-symbolic",
                valign=Gtk.Align.CENTER,
                css_classes=["flat"],
                tooltip_text="Remove this game library",
            )
            remove_button.connect("clicked", lambda _b, i=index: self._on_remove_rom_dir(i))
            row.add_suffix(remove_button)
            self.roms_group.add(row)
            self._rom_dir_rows.append(row)

    def _test_emulator(self, profile, row):
        try:
            environment = launch_environment(profile)
            subprocess.Popen(emulator_command(profile), env=environment)
        except (OSError, ValueError) as exc:
            row.set_subtitle(f"Could not start emulator · {exc}")
            row.set_icon_name("dialog-error-symbolic")
        else:
            row.set_subtitle("Emulator started successfully")
            row.set_icon_name("emblem-ok-symbolic")

    def _open_system_setup(self, system_id):
        dialog = AddRomDirDialog(self, self._on_rom_dir_added, initial_system=system_id)
        dialog.present()

    def _on_add_rom_dir(self, row):
        dialog = AddRomDirDialog(self, self._on_rom_dir_added)
        dialog.present()

    def _on_rom_dir_added(self, path, system, extensions, emulator, bios_path=None):
        self.config.add_rom_dir(path, system, extensions, emulator, bios_path)
        self._refresh_rom_dir_rows()

    def _on_remove_rom_dir(self, index):
        self.config.remove_rom_dir(index)
        self._refresh_rom_dir_rows()

    def _refresh_media_dir_rows(self):
        for row in self._media_dir_rows:
            self.media_group.remove(row)
        self._media_dir_rows = []
        for index, entry in enumerate(self.config.media_dirs):
            kind = get_kind(entry.get("media_type"))
            row = Adw.ActionRow(
                title=kind.plural,
                subtitle=entry.get("path", ""),
            )
            row.set_icon_name(kind.icon)
            remove_button = Gtk.Button(
                icon_name="user-trash-symbolic",
                valign=Gtk.Align.CENTER,
                css_classes=["flat"],
                tooltip_text="Remove this media folder",
            )
            remove_button.connect("clicked", lambda _b, i=index: self._on_remove_media_dir(i))
            row.add_suffix(remove_button)
            self.media_group.add(row)
            self._media_dir_rows.append(row)

    def _on_add_media_dir(self, _row):
        dialog = AddMediaDirDialog(self, self._on_media_dir_added)
        dialog.present()

    def _on_media_dir_added(self, path, media_type):
        self.config.add_media_dir(path, media_type)
        self._refresh_media_dir_rows()

    def _on_remove_media_dir(self, index):
        self.config.remove_media_dir(index)
        self._refresh_media_dir_rows()
