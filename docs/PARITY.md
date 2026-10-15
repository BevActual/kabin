# GTK → Tauri parity

Kabin’s **Tauri shell** is the primary target for new work. The GTK app remains for features not yet ported.

## Shipped in Tauri

| Area | Status |
|------|--------|
| Cabinet UI | Sidebar, Home shelves, libraries, details, Settings |
| Local library scan | Media folders, Steam, desktop games, ROM folders |
| Config | Read/write `~/.config/kabin/config.json` (sources, media dirs, recent on launch) |
| Launch | Steam, `gio launch` (desktop), ROM emulators (native + custom `{rom}`) |
| In-app playback | Music and video/TV via webview player + progress in config |
| Cover art | Local sidecar / folder art via asset protocol |

## Not yet in Tauri (use GTK or wait)

| Area | GTK / legacy |
|------|----------------|
| Reader & helper playback | PDF/EPUB/CBZ reader, `kabin-media-helper` GStreamer path |
| Kabin Host | TLS API, pairing, remote catalog, WebRTC stream |
| Emulation Center UI | Add ROM folder, BIOS picker, managed emulator downloads |
| Artwork | SteamGridDB, Open Library fetch queues |
| Gamepad / TV polish | Full shortcut and focus model from GTK |

## Development

- **Daily UI / scan / launch:** `npm run tauri dev`
- **Playback, host, emulation setup:** `python3 -m kabin` until ported
