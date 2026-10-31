import { Link, getRouteApi } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MediaTile } from "../components/MediaTile";
import { SegmentedControl } from "../components/SegmentedControl";
import { getLibraryTitles } from "../lib/kabin-api";
import type { CatalogTitle } from "../types/catalog";
import { useUiStore, type LibrarySort } from "../store/ui";

const route = getRouteApi("/library/$kind");

const libraryLabels: Record<string, string> = {
  game: "Games",
  music: "Music",
  video: "Movies",
  book: "Books",
  comic: "Comics",
  favorites: "Favorites",
};

export function LibraryView() {
  const { kind } = route.useParams();
  const searchQuery = useUiStore((s) => s.searchQuery.trim());
  const librarySort = useUiStore((s) => s.librarySort);
  const setLibrarySort = useUiStore((s) => s.setLibrarySort);
  const titlesQuery = useQuery({
    queryKey: ["library", kind],
    queryFn: () => getLibraryTitles(kind),
    enabled: !searchQuery,
  });

  if (searchQuery) {
    return null;
  }

  if (titlesQuery.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  const titles = titlesQuery.data ?? [];

  if (titles.length === 0) {
    if (kind === "favorites") {
      return (
        <div className="max-w-lg">
          <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
            No favorites yet.
          </p>
          <p className="mt-2 text-[calc(15px*var(--kabin-type-scale))] text-kabin-tertiary">
            Open any title and tap the heart to save it here.
          </p>
        </div>
      );
    }
    return (
      <div className="max-w-lg">
        <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
          No titles in {libraryLabels[kind] ?? "this library"} yet.
        </p>
        <p className="mt-2 text-[calc(15px*var(--kabin-type-scale))] text-kabin-tertiary">
          <Link to="/settings" className="text-kabin-accent">
            Open Settings
          </Link>{" "}
          to add folders or enable Steam, then refresh from Home.
        </p>
      </div>
    );
  }

  const sorted = sortTitles(titles, librarySort);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
          {sorted.length} {sorted.length === 1 ? "title" : "titles"}
        </p>
        <SegmentedControl
          label="Sort library"
          value={librarySort}
          onChange={setLibrarySort}
          options={[
            { id: "title", label: "Title" },
            { id: "recent", label: "Recent" },
            { id: "added", label: "Added" },
            { id: "played", label: "Played" },
          ]}
        />
      </div>
      <div className="kabin-library-grid">
        {sorted.map((title) => (
          <MediaTile key={title.id} title={title} />
        ))}
      </div>
    </div>
  );
}

function sortTitles(titles: CatalogTitle[], mode: LibrarySort) {
  const byTitle = (a: CatalogTitle, b: CatalogTitle) =>
    a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
  const copy = [...titles];
  if (mode === "recent") {
    return copy.sort(
      (a, b) => (b.recentAt ?? 0) - (a.recentAt ?? 0) || byTitle(a, b),
    );
  }
  if (mode === "added") {
    return copy.sort(
      (a, b) => (b.addedAt ?? 0) - (a.addedAt ?? 0) || byTitle(a, b),
    );
  }
  if (mode === "played") {
    return copy.sort(
      (a, b) => (b.playCount ?? 0) - (a.playCount ?? 0) || byTitle(a, b),
    );
  }
  return copy.sort(byTitle);
}
