# GTK → Tauri parity

Kabin’s **Tauri shell** is the primary desktop app. See [`CONVERSION.md`](CONVERSION.md).

## Shipped in Tauri

| Area | Status |
|------|--------|
| Cabinet UI | Sidebar, Home, libraries, details, Settings |
| Local library | Media folders, Steam (+ CDN covers), desktop, ROMs |
| Config | `~/.config/kabin/config.json` |
| Launch | Steam, desktop, ROM emulators (+ BIOS symlink for DuckStation/PCSX2) |
| Playback | Music, video, TV + progress sync to remote hosts |
| Reader | PDF, EPUB, CBZ, TXT, FB2; CBR/CBT/CB7 via `bsdtar`; MOBI/AZW3 via system |
| Emulation Center | ROM folders, native emulator detect, BIOS folder picker (PS1/PS2) |
| Shortcuts | `/`, Ctrl+F, Esc, Ctrl+, |
| Covers | Sidecar/folder art, Steam cache, host `/v1/artwork`, remote cache |
| Kabin Host | TLS API, pairing, library, stream, progress, artwork, mDNS |
| Remote client | Discovery, pairing, merged catalog, play/read, progress |

## GTK-only (optional)

| Area | Notes |
|------|--------|
| Remote **game** streaming | WebRTC `/v1/sessions/*` + `kabin-media-helper` |
| Managed emulator **downloads** | `kabin/managed.py` AppImage fetch |
| Advanced TV/gamepad polish | Couch focus model (basic keyboard/gamepad still usable in webview) |

## Development

```bash
npm run tauri dev
```

WebRTC streaming or managed emulator install:

```bash
python3 -m kabin
```
