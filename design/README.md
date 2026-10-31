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
- **Libraries** are Video, Books, Music, and Games. Video holds Movies and TV. Books holds books, audiobooks, comics, and PDFs. A books folder sorts those formats, and a video folder sorts movies from TV episodes.
- **Liquid glass chrome** (the navigation layer only): the sidebar and a compact toolbar chip float above the base with a 12px gutter and a blur material. Search and Settings live in the sidebar. A large title leads the page and joins the toolbar chip once the page scrolls. Space on a focused title opens a preview. Music, audiobooks, and an open book sit in a centered capsule at the bottom, the compact form of the full player or reader. Category cards on a library home open Movies, TV, books, audiobooks, comics, and PDFs. Player and reader stay full-bleed, with no glass frame.

## Components

- **Tiles:** flat at rest; hover scale ~1.02; gamepad/TV focus scale ~1.06 + accent ring.
- **Primary button:** filled accent, 10px radius, semibold 17px label — one per screen when possible.
- **Settings:** inset grouped rows, caption footnotes, toggles and navigation chevrons.
- **Icons:** Lucide at ~1.5px stroke, SF Symbols–like sizing (20–22px).

## Copy

Short, neutral, helpful — no marketing fluff. Empty states explain the next step (“Open Settings”).

## References (behavior, not cloning)

Apple TV (shelves, Continue), Music (sidebar + Now Playing), Books (reader), macOS Settings (grouped lists), tvOS (focus scale).
