import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { MediaTile } from "../components/MediaTile";
import { getLibraryTitles } from "../lib/kabin-api";

const route = getRouteApi("/library/$kind");

export function LibraryView() {
  const { kind } = route.useParams();
  const titlesQuery = useQuery({
    queryKey: ["library", kind],
    queryFn: () => getLibraryTitles(kind),
  });

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
          Add folders in the GTK Settings app, or enable Steam scanning in your
          config, then refresh from Home.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-4">
      {titles.map((title) => (
        <MediaTile key={title.id} title={title} />
      ))}
    </div>
  );
}
