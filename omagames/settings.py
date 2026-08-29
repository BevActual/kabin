import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class AddRomDirDialog(Adw.Window):
    def __init__(self, transient_for, on_added):
        super().__init__(transient_for=transient_for, modal=True, title="Add ROM Directory")
        self.set_default_size(480, -1)
        self._on_added = on_added

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()

        group = Adw.PreferencesGroup()

        self.path_row = Adw.ActionRow(title="Folder", subtitle="Not selected")
        choose_button = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose_button.connect("clicked", self._on_choose_folder)
        self.path_row.add_suffix(choose_button)
        group.add(self.path_row)

        self.system_entry = Adw.EntryRow(title="System name (e.g. GBA, PS1)")
        group.add(self.system_entry)

        self.extensions_entry = Adw.EntryRow(title="File extensions, comma-separated (e.g. gba,zip)")
        group.add(self.extensions_entry)

        self.emulator_entry = Adw.EntryRow(
            title="Emulator command, use {rom} for the file path"
        )
        group.add(self.emulator_entry)

        page.add(group)

        add_button = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_button.add_css_class("suggested-action")
        add_button.connect("clicked", self._on_add_clicked)

        action_group = Adw.PreferencesGroup()
        action_group.add(add_button)
        page.add(action_group)

        toolbar_view.set_content(page)
        self._selected_path = None
        self.set_content(toolbar_view)

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

    def _on_add_clicked(self, button):
        if not self._selected_path:
            return
        system = self.system_entry.get_text().strip() or "ROMs"
        extensions = [e.strip() for e in self.extensions_entry.get_text().split(",") if e.strip()]
        emulator = self.emulator_entry.get_text().strip()
        if not emulator or "{rom}" not in emulator:
            self.emulator_entry.add_css_class("error")
            return
        self._on_added(self._selected_path, system, extensions, emulator)
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

        self.roms_group = Adw.PreferencesGroup(title="ROM Directories")
        add_row = Adw.ButtonRow(title="Add ROM Directory")
        add_row.connect("activated", self._on_add_rom_dir)
        self.roms_group.add(add_row)
        self.page.add(self.roms_group)

        toolbar_view.set_content(self.page)
        self.set_content(toolbar_view)

        self._rom_dir_rows = []
        self._refresh_rom_dir_rows()

    def _make_source_toggle_handler(self, source_id):
        def handler(row, _pspec):
            self.config.sources[source_id] = row.get_active()
            self.config.save()

        return handler

    def _refresh_rom_dir_rows(self):
        for row in self._rom_dir_rows:
            self.roms_group.remove(row)
        self._rom_dir_rows = []

        for index, entry in enumerate(self.config.rom_dirs):
            row = Adw.ActionRow(
                title=entry.get("system", "ROMs"),
                subtitle=entry.get("path", ""),
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

    def _on_add_rom_dir(self, row):
        dialog = AddRomDirDialog(self, self._on_rom_dir_added)
        dialog.present()

    def _on_rom_dir_added(self, path, system, extensions, emulator):
        self.config.add_rom_dir(path, system, extensions, emulator)
        self._refresh_rom_dir_rows()

    def _on_remove_rom_dir(self, index):
        self.config.remove_rom_dir(index)
        self._refresh_rom_dir_rows()
