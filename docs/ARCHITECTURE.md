# Kabin architecture (Tauri)

Kabin’s **primary desktop app** is **Tauri 2 + Rust + React (TypeScript) + Vite**. The legacy **Python + GTK4** tree remains for remote game streaming (WebRTC) and managed emulator downloads — see [`CONVERSION.md`](CONVERSION.md) and [`PARITY.md`](PARITY.md).

## Layers

```
┌─────────────────────────────────────────────────────────┐
│  React + TypeScript (Vite)                               │
│  TanStack Router · Query · Zustand · design/tokens.css   │
└───────────────────────────┬─────────────────────────────┘
                            │ invoke + events
┌───────────────────────────▼─────────────────────────────┐
│  Tauri 2 (Rust)                                          │
│  config · library · host · remote · playback · reader  │
└───────────────────────────┬─────────────────────────────┘
                            │
         ~/.config/kabin/config.json · ~/.cache/kabin/
```

## Repository layout

| Path | Role |
|------|------|
| `src/` | Web UI (cabinet shell, routes, components) |
| `src-tauri/` | Rust crate: catalog, host, remote, launch, commands |
| `design/` | Design tokens and language |
| `kabin/` | **Legacy** GTK application (still `python3 -m kabin`) |
| `native/` | **Legacy** `kabin-media-helper` (GStreamer/WebRTC); to be absorbed into Rust |
| `docs/` | Architecture and migration notes |

## Frontend stack

- **React 19** + **TypeScript** (strict)
- **Vite** (port `1420` for Tauri dev)
- **Tailwind CSS v4** themed with `design/tokens.css`
- **TanStack Router** — navigation and back stack
- **TanStack Query** — catalog, config, host API caching
- **Zustand** — focus index, sidebar, ephemeral UI
- **Framer Motion** — screen and tile motion (respects reduced motion)
- **Lucide** — iconography

Typed IPC: `src/lib/kabin-api.ts` wraps all `invoke` calls.

## Rust surface

Commands:

- `get_app_info` — version and config path
- `scan_library` — full local scan + Home shelves (cached by config fingerprint)
- `get_home_shelves` / `get_library_titles` / `get_title` / `get_library_counts` — views over the cached scan

Local discovery (see `src-tauri/src/catalog/`):

- **Media folders** — same layout rules as `kabin/sources/media_dirs.py`
- **Steam** — `appmanifest_*.acf` + `libraryfolders.vdf`
- **Desktop games** — `.desktop` entries with `Categories=Game`
- **ROMs** — `rom_dirs` with emulator profiles and `{rom}` templates (`catalog/roms.rs`, `emulators/`)

Config read/write: `~/.config/kabin/config.json` (`config.rs`). Launch updates `recent`. See [`PARITY.md`](PARITY.md) for GTK-only features.

## Migration phases

1. **Shell** — done (cabinet UI, Settings, design system).
2. **Library + launch** — done for local sources (scan + Play/Launch).
3. **Playback & reader** — done in Tauri (see [`CONVERSION.md`](CONVERSION.md)).
4. **Host + remote** — done in Rust; WebRTC game streaming remains GTK-only.
5. **GTK optional** — managed emulator downloads + remote game stream; see [`PARITY.md`](PARITY.md).

## Development

```bash
npm install
npm run tauri dev    # full app (needs Linux WebKit GTK deps)
npm run dev          # Vite only (mock data when not in Tauri)
```

Rust **stable** (see [`rust-toolchain.toml`](../rust-toolchain.toml)) — recent Tauri 2 releases need a current toolchain.

Legacy:

```bash
python3 -m kabin
python3 -m unittest discover -s tests
```

## Design

See [`design/README.md`](../design/README.md) and [`design/tokens.css`](../design/tokens.css).
