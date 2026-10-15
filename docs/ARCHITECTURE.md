# Kabin architecture (Tauri migration)

Kabin is moving from **Python + GTK4/libadwaita** to **Tauri 2 + Rust + React (TypeScript) + Vite**. The legacy Python app remains runnable until feature parity; new UI and host logic land in this stack.

## Layers

```
┌─────────────────────────────────────────────────────────┐
│  React + TypeScript (Vite)                               │
│  TanStack Router · Query · Zustand · design/tokens.css   │
└───────────────────────────┬─────────────────────────────┘
                            │ invoke + events
┌───────────────────────────▼─────────────────────────────┐
│  Tauri 2 (Rust)                                          │
│  config · library scan · host API · playback (later)   │
└───────────────────────────┬─────────────────────────────┘
                            │
         ~/.config/kabin/config.json · ~/.cache/kabin/
```

## Repository layout

| Path | Role |
|------|------|
| `src/` | Web UI (cabinet shell, routes, components) |
| `src-tauri/` | Rust crate: commands, config, future library/host |
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
- **ROMs** — not yet ported (`sources/roms.py` is next)

Config reads use the same path as the Python app: `~/.config/kabin/config.json` (`src-tauri/src/config.rs`). Progress and `recent` drive Continue shelves.

## Migration phases

1. **Shell** — sidebar, Home shelves, details placeholder, Settings grouped list (current).
2. **Library** — port scanners from `kabin/sources/*` to Rust; artwork cache reuse.
3. **Playback & reader** — stream URLs, progress sync, reader routes (PDF/EPUB/CBZ).
4. **Host** — TLS API, pairing, WebRTC stream (replace Python host + C helper).
5. **Retire GTK** — remove or archive `kabin/` UI when parity is reached.

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
