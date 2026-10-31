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
- **Liquid glass chrome** (the navigation layer only): the sidebar floats above the base with a 12px gutter and a blur material. In a library it holds search, the shelves, and the control that hides the pane. Downloads and Settings replace that list with their own sections, and the page shows the section you choose. A large title leads the page and joins a compact chip once the page scrolls. Space on a focused title opens a preview. Music, audiobooks, and an open book sit in a centered capsule at the bottom, the compact form of the full player or reader. Category cards on a library home open Movies, TV, books, audiobooks, comics, PDFs, and, for games, Steam, Installed, and Consoles. Console games group by system. Music opens as Albums, Artists, and Songs. An album opens to its tracks, and an artist opens to the albums and songs that belong to them. Recently added and Unwatched sit below a break in the sidebar. TV episodes that share a show name open as one show, and the episode you are on offers the next one. Searching a show name returns the show. Books, comics, audiobooks, and PDFs that share a series name open as one series, and the volume you are on offers the next one. Searching a series name returns the series. Player and reader stay full-bleed, with no glass frame.

## Components

- **Tiles:** flat at rest; hover scale ~1.02; gamepad/TV focus scale ~1.06 + accent ring.
- **Primary button:** filled accent, 10px radius, semibold 17px label — one per screen when possible.
- **Settings:** inset grouped rows, caption footnotes, toggles and navigation chevrons.
- **Icons:** Lucide at ~1.5px stroke, SF Symbols–like sizing (20–22px).

## Copy

Short, neutral, helpful — no marketing fluff. Empty states explain the next step (“Open Settings”).

## References (behavior, not cloning)

Apple TV (shelves, Continue), Music (sidebar + Now Playing), Books (reader), macOS Settings (grouped lists), tvOS (focus scale).
