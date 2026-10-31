import { Link } from "@tanstack/react-router";
import { gameSource } from "../lib/games";
import { musicCount } from "../lib/music";
import { seriesTiles } from "../lib/series";
import type { ContentMode } from "../lib/modes";
import { collapseShows } from "../lib/shows";
import type { CatalogTitle } from "../types/catalog";

type Props = {
  mode: ContentMode;
  titles: CatalogTitle[];
};

export function LibraryCategories({ mode, titles }: Props) {
  const categories = mode.sections.filter(
    (section) => section.kinds?.length || section.gameSource || section.musicShelf,
  );
  if (categories.length < 2) return null;

  return (
    <div className="kabin-category-row mb-8">
      {categories.map((section) => {
        const count =
          section.id === "series"
            ? seriesTiles(titles).length
            : section.musicShelf
              ? musicCount(titles, section.musicShelf)
              : section.gameSource
                ? titles.filter((title) => gameSource(title) === section.gameSource).length
                : collapseShows(titles.filter((title) => section.kinds?.includes(title.kind)))
                    .length;
        const detail =
          count === 0
            ? "None yet"
            : section.id === "series"
              ? count === 1
                ? "1 series"
                : `${count} series`
              : section.musicShelf === "albums"
              ? count === 1
                ? "1 album"
                : `${count} albums`
              : section.musicShelf === "artists"
                ? count === 1
                  ? "1 artist"
                  : `${count} artists`
                : section.musicShelf === "songs"
                  ? count === 1
                    ? "1 song"
                    : `${count} songs`
              : section.id === "books"
                ? count === 1
                  ? "1 book"
                  : `${count} books`
                : section.id === "audiobooks"
                  ? count === 1
                    ? "1 audiobook"
                    : `${count} audiobooks`
                  : section.id === "comics"
                    ? count === 1
                      ? "1 comic"
                      : `${count} comics`
                    : section.id === "pdfs"
                      ? count === 1
                        ? "1 PDF"
                        : `${count} PDFs`
                      : section.id === "tv"
                    ? count === 1
                      ? "1 show"
                      : `${count} shows`
                    : section.gameSource
                      ? count === 1
                        ? "1 game"
                        : `${count} games`
                      : count === 1
                        ? "1 title"
                        : `${count} titles`;
        const Icon = section.icon;
        return (
          <Link
            key={section.id}
            to="/browse/$mode/$section"
            params={{ mode: mode.id, section: section.id }}
            className="kabin-category-card"
          >
            <span className="kabin-category-icon">
              <Icon size={18} strokeWidth={1.5} />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[calc(15px*var(--kabin-type-scale))] font-semibold">
                {section.label}
              </span>
              <span className="block text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
                {detail}
              </span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}
