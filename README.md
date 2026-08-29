# Kabin

Your games live here.

A standalone game launcher for Omarchy — one fullscreen grid for Steam games,
other apps categorized as games, and ROMs, instead of switching between
Steam, a file manager, and an emulator.

This is not an Omarchy shell plugin. It's a regular GTK4/libadwaita app you
launch like any other, and it isn't tied to the Quickshell bar.

## Sources

- **Steam** — scans `~/.local/share/Steam` (and any additional library
  folders listed in `libraryfolders.vdf`) for installed games, filtering out
  Proton/runtime/redistributable entries that aren't actually games. Cover
  art is fetched from Steam's CDN and cached in `~/.cache/kabin/steam/`.
  Games launch via `steam steam://rungameid/<appid>`.
- **Other apps** — any installed `.desktop` entry with `Categories=Game`
  (catches things like custom shortcuts for non-Steam games).
- **Emulation Center** — choose a game system and ROM folder; Kabin supplies
  the correct file types and detects compatible native or Flatpak emulators.
  standalone emulators are discovered automatically, and advanced users can
  still provide a custom command containing `{rom}`.

Kabin currently recognizes NES, SNES, Nintendo 64, Game Boy, Game Boy Color,
Game Boy Advance, Genesis/Mega Drive, PlayStation, PlayStation 2, PSP,
GameCube, Wii, and arcade libraries. Kabin detects dedicated emulators such as
Mesen, Snes9x, RMG, mGBA, BlastEm, DuckStation, PCSX2, PPSSPP, Dolphin, and MAME.

The Emulation Center also provides Balanced, Original Hardware, Quality, and
Performance play profiles. Common fullscreen, VSync, integer-scaling, and
rewind controls form Kabin's unified settings layer and are translated by each
standalone emulator adapter as support is added. Connected Linux game
controllers are shown alongside these defaults.

Optional console cover art comes from SteamGridDB. Add a personal API key in
Settings → Game Artwork; Kabin then sends normalized game titles to the
SteamGridDB search API and caches portrait covers locally. The key is stored
only in Kabin's owner-readable configuration file. The same artwork pipeline
is used for console libraries and non-Steam games; native application icons
remain the fallback when no cover is available.

For DuckStation, PCSX2, and PPSSPP, Kabin can download a portable Linux
runtime directly from the emulator's official GitHub releases. Downloads are
installed under `~/.local/share/kabin/emulators/` only after their published
SHA-256 digest is verified. Kabin refuses unverified release assets.

PlayStation and PlayStation 2 setup also requires the user to select a folder
containing their legally dumped BIOS. Kabin validates that firmware-like files
are present and stores the folder path; it never downloads or redistributes
console firmware.

Any source can be toggled off in Settings. Hidden individual games are
tracked by id in the config file.

## Install

```bash
./scripts/install.sh
```

Writes a small `kabin` wrapper into `~/.local/bin` that runs this repo
in place (no pip/venv needed), and puts a `Kabin` entry in your app
launcher. Requires system GTK4/libadwaita/PyGObject, which Omarchy already
ships. Make sure `~/.local/bin` is on your `PATH`.

Run directly during development with:

```bash
python3 -m kabin
```

## Config

Settings are stored at `~/.config/kabin/config.json` (rom directories,
per-source enable/disable, hidden game ids).

## Shortcuts

- `Ctrl+F` or `/` — focus search
- `Esc` — clear search, then leave fullscreen
- `Ctrl+,` — open Settings
- `F11` — toggle fullscreen

## Tests

```bash
python3 -m unittest discover -s tests
```
