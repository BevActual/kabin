# Kabin

Your games and media live here.

Kabin is a personal media host and player — the same class of program as
Jellyfin or Plex, starting from a game cabinet. One app scans your library,
serves it to paired Kabin devices, plays music and video itself, and reads
PDF, EPUB, FB2, TXT, CBZ, CBR, CBT, and CB7 books and comics in its own
reader. MOBI and AZW3 books still open in your system reader.

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
- **Books, comics, music, and movies** — add a folder in Settings → Library.
  Kabin groups music by album folder, plays music and video in
  `kabin-media-helper`, and remembers resume position on this device and the
  host. Albums play through as a queue. Space pauses; the bottom bar seeks,
  skips tracks, and stops. Kabin reads PDF, EPUB, FB2, TXT, CBZ, CBR, CBT,
  and CB7 books and comics itself, with the same resume-position tracking
  — the arrow keys, Page Up/Down, and Space turn pages, and a page slider
  jumps around (TXT has no natural pagination, so it's one scrollable
  page; FB2 has no CSS of its own, so Kabin styles it to match the reader).
  EPUB and FB2 need `webkitgtk-6.0` installed, and CBR/CB7 need `bsdtar`
  (both ship with Omarchy); without those (or for MOBI/AZW3, which Kabin
  doesn't parse at all) books and comics open in your default reader
  instead. The cabinet uses a poster wall for mixed views, square album
  cards in Music, and widescreen cards in Movies.
- **Emulation Center** — choose a game system and ROM folder; Kabin supplies
  the correct file types and detects compatible native or Flatpak emulators.
  standalone emulators are discovered automatically, and advanced users can
  still provide a custom command containing `{rom}`.

Kabin currently recognizes NES, SNES, Nintendo 64, Game Boy, Game Boy Color,
Game Boy Advance, Genesis/Mega Drive, PlayStation, PlayStation 2, PSP,
GameCube, Wii, and arcade libraries. Kabin detects dedicated emulators such as
FCEUX, Mesen, Snes9x, RMG, mGBA, BlastEm, DuckStation, PCSX2, PPSSPP, Dolphin, and MAME.

The Emulation Center also provides Balanced, Original Hardware, Quality, and
Performance play profiles. Fullscreen, VSync, integer scaling, and rewind
are translated at launch for the emulators that accept them. Connected Linux
game controllers are shown alongside these defaults.

Optional console cover art comes from SteamGridDB. Add a personal API key in
Settings → Artwork; Kabin then sends normalized game titles to the
SteamGridDB search API and caches portrait covers locally. The key is stored
only in Kabin's owner-readable configuration file. The same artwork pipeline
is used for console libraries and non-Steam games; native application icons
remain the fallback when no cover is available.

Book jackets without an embedded EPUB cover come from Open Library. Kabin
searches by title and author, then caches the image under `~/.cache/kabin`.
No API key is required; the fetch can be turned off in Settings → Artwork.

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

## Kabin Host

Kabin can advertise its library to other Kabin devices on the local network.
Enable **Kabin Host** in Settings → Network. Host mode exposes a versioned,
authenticated TLS API on port `42424` and advertises `_kabin._tcp` through
mDNS/Avahi. Kabin generates a local host certificate, advertises its SHA-256
fingerprint during discovery, and pins that certificate before sending pairing
codes or device tokens.

The host protocol shares catalog metadata only. Local file paths, emulator
commands, and credentials are never included in library responses. Paired
clients play music and video through `GET /v1/media/stream`, which sends the
file bytes (including HTTP Range) after the same Bearer check. Album tracks
are selected with `track=`. `GET`/`POST /v1/media/progress` keeps Continue
in sync across paired Kabin devices. The catalog marks titles `playable`
and includes resume metadata without exposing a path.

Paired clients read books and comics through the same `GET /v1/media/stream`
endpoint, which Kabin caches locally and opens in the reader. Reading
progress is pushed with `POST /v1/media/progress` and also published on
the catalog, so a device that already has its own copy (Syncthing, or a
hand copy) can adopt whichever side has read further on refresh.

Remote game play is a Kabin layer, not a second app. The host captures the
desktop with PipeWire or X11, encodes it, and sends WebRTC over the existing
Kabin TLS API. The client decodes that stream in `kabin-media-helper` — the
same native process used for local Watch/Listen — so Stream never launches
Sunshine, Moonlight, VLC, or any other external player.

Build the helper with `./scripts/build-media-helper.sh` (install also does
this). It needs GStreamer WebRTC plus a capture plugin (`pipewiresrc` or
`ximagesrc`) and an encoder (`nvh264enc`, `vah264enc`, `openh264enc`, or
`vp8enc`). Settings → Network shows whether that stack is ready.

## Install

```bash
./scripts/install.sh
```

Writes a small `kabin` wrapper into `~/.local/bin` that runs this repo
in place (no pip/venv needed), and puts a `Kabin` entry in your app
launcher. Requires system GTK4/libadwaita/PyGObject, which Omarchy already
ships. Make sure `~/.local/bin` is on your `PATH`. Reading PDF, CBZ, and
CBT books/comics needs nothing beyond that; EPUB additionally needs
`webkitgtk-6.0` — install.sh warns (without failing) if it isn't found.

Run directly during development with:

```bash
python3 -m kabin
```

## Config

Settings are stored at `~/.config/kabin/config.json` (rom directories,
per-source enable/disable, hidden game ids).

## Shortcuts

Kabin is meant for mouse, keyboard, gamepads, and touch. On a controller,
D-pad or left stick moves, A opens a title, B goes back, Y favorites,
LB/RB change library, L3 picks a random title, and Start opens Settings.
Letter keys jump to that letter in the current list.

- `Ctrl+F` or `/` — focus search
- `A`–`Z` or `0`–`9` — jump to the first matching title
- `F2` — surprise me (random title in the current view)
- `Enter` — open the selected title, then play, read, listen, or watch
- `Esc` — back, then clear search, then leave fullscreen
- `Page Up` / `Page Down` — previous or next library; turns pages while reading
- `F1` or `Ctrl+,` — open Settings
- `F11` — toggle fullscreen

While reading, the arrow keys and Space also turn pages, and a page slider
at the bottom jumps to any page. EPUBs with a table of contents get a
Chapters button in the reader header to jump straight to any chapter.

## Tests

```bash
python3 -m unittest discover -s tests
```

`native/kabin-media-helper.c`'s JSON string-escape parsing has its own
small C test, run separately:

```bash
./scripts/test-media-helper.sh
```
