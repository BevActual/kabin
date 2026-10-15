# GTK → Tauri parity

Kabin’s **Tauri shell** is the primary desktop app. See [`CONVERSION.md`](CONVERSION.md).

## Shipped in Tauri

| Area | Status |
|------|--------|
| Cabinet UI | Sidebar, Home, libraries, details, Settings |
| Local library | Media folders, Steam (+ CDN covers), desktop, ROMs |
| Config | `~/.config/kabin/config.json` |
| Launch | Steam, desktop, ROM emulators (+ BIOS symlink); session tracking, play time/count, quick-failure toasts |
| Playback | Music, video, TV + progress sync to remote hosts |
| Reader | PDF, EPUB, CBZ, TXT, FB2; CBR/CBT/CB7 via `bsdtar`; MOBI/AZW3 via system |
| Emulation Center | ROM folders, native/Flatpak detect, managed AppImage install (PS1/PS2/PSP), BIOS picker, play profiles |
| Shortcuts | `/`, Ctrl+F, Esc, Ctrl+,; gamepad Back/Start/Guide/A (basic) |
| Covers | Sidecar/folder art, Steam cache, host `/v1/artwork`, remote cache |
| Kabin Host | TLS API, pairing, library, stream, progress, artwork, mDNS |
| Remote client | Discovery, pairing, merged catalog, play/read, progress, remote game stream (with `kabin-media-helper`) |
| Kabin Host streaming | `/v1/sessions/*` WebRTC via `kabin-media-helper` when built |

## GTK-only (optional)

| Area | Notes |
|------|--------|
| Legacy shell preference | `python3 -m kabin` for users who prefer the GTK4 UI |

## Development

```bash
npm run tauri dev
```

Build the media helper for streaming and in-GTK playback:

```bash
./scripts/build-media-helper.sh
```
