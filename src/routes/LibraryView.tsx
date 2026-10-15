import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { MediaTile } from "../components/MediaTile";
import { getLibraryTitles } from "../lib/kabin-api";
import { useUiStore } from "../store/ui";

const route = getRouteApi("/library/$kind");

function libraryTileScale(count: number) {
  if (count <= 1) return 1.7;
  if (count <= 3) return 1.5;
  if (count <= 6) return 1.18;
  return 1;
}

export function LibraryView() {
  const { kind } = route.useParams();
  const searchQuery = useUiStore((s) => s.searchQuery.trim());
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
    return (
      <div className="max-w-lg">
        <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
          No titles in this library yet.
        </p>
        <p className="mt-2 text-[calc(15px*var(--kabin-type-scale))] text-kabin-tertiary">
          Add folders in Settings, or enable Steam scanning, then refresh from
          Home.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-4">
      {titles.map((title) => (
        <MediaTile
          key={title.id}
          title={title}
          scale={libraryTileScale(titles.length)}
        />
      ))}
    </div>
  );
}
