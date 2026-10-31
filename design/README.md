# Kabin design language

Kabin’s UI should feel like a first-party Apple media app: **Apple TV** shelves and focus, **Music** artwork-first grids, **Books** reader chrome, and **System Settings** grouped lists.

## Principles

1. **Content is the interface** — posters, jackets, and album art dominate; chrome stays thin.
2. **Hierarchy through type and space** — not boxes and heavy borders.
3. **One accent** — system blue for primary actions and focus (`--kabin-accent`).
4. **Motion explains structure** — ease-out transitions; tvOS-like scale on gamepad focus.
5. **Dark-first** — light mode follows macOS utility apps.

## Tokens

Shared CSS variables live in [`tokens.css`](./tokens.css). The React app imports them via `src/styles/app.css`.

| Token | Usage |
|-------|--------|
| `--kabin-bg-*` | Shell, sidebar material, grouped settings background |
| `--kabin-label-*` | Primary / secondary / tertiary text |
| `--kabin-radius-tile` | Poster, album, movie cards |
| `--kabin-type-scale` | Couch/TV scaling at 1800px and 2600px width |
| `--kabin-motion-*` | Transitions; disabled when `prefers-reduced-motion` |

## Layout

- **8pt grid**; tile gutters 16–24px (32–48px on wide/TV layouts).
- **Aspect ratios:** games/mixed **2:3**, music **1:1**, movies **16:9**.
- **Sidebar** for libraries; **horizontal shelves** on Home and details.
- **Liquid glass chrome** (the navigation layer only): the sidebar and toolbar float above the base with a 12px gutter, concentric 22px corners (`--kabin-radius-chrome`), and a blur material. Content scrolls underneath the toolbar; the material gets more opaque once the scroll edge lifts. Related toolbar actions stay grouped. The sidebar collapses to an icon rail. Player and reader stay full-bleed, with no glass frame.

## Components

- **Tiles:** flat at rest; hover scale ~1.02; gamepad/TV focus scale ~1.06 + accent ring.
- **Primary button:** filled accent, 10px radius, semibold 17px label — one per screen when possible.
- **Settings:** inset grouped rows, caption footnotes, toggles and navigation chevrons.
- **Icons:** Lucide at ~1.5px stroke, SF Symbols–like sizing (20–22px).

## Copy

Short, neutral, helpful — no marketing fluff. Empty states explain the next step (“Open Settings”).

## References (behavior, not cloning)

Apple TV (shelves, Continue), Music (sidebar + Now Playing), Books (reader), macOS Settings (grouped lists), tvOS (focus scale).
