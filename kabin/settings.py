import threading
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .emulation import PRESETS, connected_controllers, settings_for_preset, system_readiness
from .emulators import detect_emulators, emulator_command, launch_environment
from .managed import ManagedRuntimeError, install_runtime, recommended_runtime
from .systems import SYSTEMS, firmware_files, get_system


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
        custom_valid = "{rom}" in self.custom_emulator_entry.get_text() if custom else True
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
            if "{rom}" not in emulator:
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


class SettingsWindow(Adw.Window):
    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.set_title("Settings")
        self.set_default_size(600, 500)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        self.page = Adw.PreferencesPage()

        play_group = Adw.PreferencesGroup(
            title="Play Defaults",
            description="Fullscreen is applied at launch. Other defaults are saved for expanding emulator adapters.",
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
        for key, title, subtitle in (
            ("fullscreen", "Start fullscreen", "Launch games directly into fullscreen mode."),
            ("vsync", "Vertical sync", "Reduce tearing by synchronizing frames with the display."),
            ("integer_scaling", "Integer scaling", "Keep classic pixels evenly sized."),
            ("rewind", "Rewind", "Allow supported emulators to retain recent gameplay history."),
        ):
            row = Adw.SwitchRow(title=title, subtitle=subtitle)
            row.set_active(bool(self.config.emulation.get(key, False)))
            row.connect("notify::active", self._make_emulation_toggle_handler(key))
            play_group.add(row)
            self._play_switches[key] = row

        controllers = connected_controllers()
        controller_row = Adw.ActionRow(
            title="Controllers",
            subtitle=(", ".join(controllers) if controllers else "No game controller detected"),
        )
        controller_row.set_icon_name(
            "input-gaming-symbolic" if controllers else "dialog-warning-symbolic"
        )
        play_group.add(controller_row)
        self.page.add(play_group)

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
        key_link.add_css_class("pill")
        key_link_row = Adw.ActionRow(
            title="SteamGridDB account",
            subtitle="Generate or manage your personal API key",
        )
        key_link_row.add_suffix(key_link)
        key_link_row.set_activatable_widget(key_link)
        artwork_group.add(key_link_row)
        self.page.add(artwork_group)

        sources_group = Adw.PreferencesGroup(title="Sources")
        for source_id, label in (
            ("steam", "Steam"),
            ("desktop", "Other installed apps categorized as Games"),
            ("roms", "ROM directories"),
        ):
            row = Adw.SwitchRow(title=label)
            row.set_active(self.config.sources.get(source_id, True))
            row.connect("notify::active", self._make_source_toggle_handler(source_id))
            sources_group.add(row)
        self.page.add(sources_group)

        self.readiness_group = Adw.PreferencesGroup(
            title="Emulation Center",
            description="Every console's library, standalone emulator, and firmware status at a glance.",
        )
        self.page.add(self.readiness_group)

        self.roms_group = Adw.PreferencesGroup(
            title="Game Libraries",
            description="Add or remove the folders Kabin scans for games.",
        )
        add_row = Adw.ButtonRow(title="Add Game Library")
        add_row.connect("activated", self._on_add_rom_dir)
        self.roms_group.add(add_row)
        self.page.add(self.roms_group)

        toolbar_view.set_content(self.page)
        self.set_content(toolbar_view)

        self._rom_dir_rows = []
        self._readiness_rows = []
        self._refresh_rom_dir_rows()

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
        self.config.artwork["steamgriddb_api_key"] = row.get_text().strip()
        self.config.save()

    def _make_source_toggle_handler(self, source_id):
        def handler(row, _pspec):
            self.config.sources[source_id] = row.get_active()
            self.config.save()

        return handler

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
                test_button.add_css_class("pill")
                test_button.connect(
                    "clicked", lambda _button, profile=emulator, target=row: self._test_emulator(
                        profile, target
                    )
                )
                row.add_suffix(test_button)
            elif entry is None:
                setup_button = Gtk.Button(label="Setup", valign=Gtk.Align.CENTER)
                setup_button.add_css_class("suggested-action")
                setup_button.add_css_class("pill")
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
