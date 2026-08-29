# Omagames

A standalone game launcher for Omarchy — one fullscreen grid for Steam games,
other apps categorized as games, and ROMs, instead of switching between
Steam, a file manager, and an emulator.

This is not an Omarchy shell plugin. It's a regular GTK4/libadwaita app you
launch like any other, and it isn't tied to the Quickshell bar.

## Sources

- **Steam** — scans `~/.local/share/Steam` (and any additional library
  folders listed in `libraryfolders.vdf`) for installed games, filtering out
  Proton/runtime/redistributable entries that aren't actually games. Cover
  art is fetched from Steam's CDN and cached in `~/.cache/omagames/steam/`.
  Games launch via `steam steam://rungameid/<appid>`.
- **Other apps** — any installed `.desktop` entry with `Categories=Game`
  (catches things like custom shortcuts for non-Steam games).
- **ROMs** — directories you configure in Settings, each with a system name,
  a list of file extensions to scan for, and an emulator command template
  using `{rom}` as the file-path placeholder (e.g.
  `retroarch -L /path/to/core.so {rom}`). No emulator is bundled or assumed
  to be installed — point it at whatever you have.

Any source can be toggled off in Settings. Hidden individual games are
tracked by id in the config file.

## Install

```bash
./scripts/install.sh
```

Writes a small `omagames` wrapper into `~/.local/bin` that runs this repo
in place (no pip/venv needed), and puts a `Games` entry in your app
launcher. Requires system GTK4/libadwaita/PyGObject, which Omarchy already
ships. Make sure `~/.local/bin` is on your `PATH`.

Run directly during development with:

```bash
python3 -m omagames
```

## Config

Settings are stored at `~/.config/omagames/config.json` (rom directories,
per-source enable/disable, hidden game ids).

## Tests

```bash
python3 -m unittest discover -s tests
```
