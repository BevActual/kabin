# GTK → Tauri conversion status

**Conversion complete for daily use.** The Tauri app is the primary Kabin
desktop experience. The Python/GTK tree remains in the repository for
reference, tests, and two specialized capabilities that still depend on
native GStreamer/WebRTC (see below).

## Daily use (Tauri)

- Cabinet UI, library scan, launch, playback, reader, Settings
- Kabin Host (TLS catalog, pairing, media stream, artwork, progress)
- Remote paired libraries (LAN discovery, in-app play/read)
- Emulation Center (ROM folders, native emulators, BIOS folder for PS1/PS2)
- Steam cover fetch from CDN on scan

## Reader (Tauri)

| Format | In-app |
|--------|--------|
| PDF, EPUB, CBZ, TXT | Yes |
| FB2 | Yes (HTML sections) |
| CBR, CBT, CB7 | Yes when `bsdtar` is installed |
| MOBI, AZW3 | Opens in system default reader |

## Optional GTK (`python3 -m kabin`)

Optional GTK remains for users who prefer the legacy shell; Tauri implements
the same host `/v1/sessions` API and remote game streaming when
`kabin-media-helper` is built (`./scripts/build-media-helper.sh`).

Managed DuckStation, PCSX2, and PPSSPP AppImages install from **Settings →
Emulation Center** in Tauri. Daily use: **`npm run tauri dev`**.

## Config

Both apps read/write `~/.config/kabin/config.json`. Prefer running one shell
at a time to avoid concurrent saves.
