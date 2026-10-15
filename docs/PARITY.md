# GTK → Tauri parity

Kabin’s **Tauri shell** is the primary app for daily use on the desktop. GTK remains for features not yet ported.

## Shipped in Tauri

| Area | Status |
|------|--------|
| Cabinet UI | Sidebar, Home shelves, libraries, details, Settings |
| Local library scan | Media folders, Steam, desktop games, ROM folders |
| Config | Read/write `~/.config/kabin/config.json` |
| Launch | Steam, desktop entries, ROM emulators |
| Playback | Music and video/TV in-app + progress |
| Reader | PDF (pdf.js), EPUB (epub.js), CBZ (extracted pages), TXT + progress |
| Emulation Center | Add ROM folder + auto-detect native emulators (Settings) |
| Shortcuts | `/` and Ctrl+F search, Esc back, Ctrl+, Settings |
| Cover art | Local sidecar / folder art |

## Deferred (GTK or future Rust work)

| Area | Notes |
|------|--------|
| **Kabin Host** | TLS catalog API, pairing, mDNS, WebRTC stream — still `kabin/network.py` + C helper. Planned Rust port in `docs/ARCHITECTURE.md` phase 4. |
| **Artwork fetch** | SteamGridDB, Open Library queues — GTK `artwork.py`. |
| **Reader gaps** | FB2, CBR/CBT/CB7, MOBI/AZW3 (GTK or system reader). |
| **Managed emulators** | Download verified runtimes — GTK `managed.py`. |
| **BIOS picker UI** | Path stored in config; full picker still in GTK Settings. |
| **Gamepad / TV** | Full focus model and couch scaling polish. |
| **GStreamer helper** | Remote game stream decode path via `kabin-media-helper`. |

## Development

```bash
npm run tauri dev
```

Host, managed emulators, and advanced emulation setup:

```bash
python3 -m kabin
```
