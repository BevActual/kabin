import { useQuery } from "@tanstack/react-query";
import { MediaTile } from "../components/MediaTile";
import { searchLibrary } from "../lib/kabin-api";
import { useUiStore } from "../store/ui";

export function SearchView() {
  const query = useUiStore((s) => s.searchQuery.trim());
  const resultsQuery = useQuery({
    queryKey: ["search", query],
    queryFn: () => searchLibrary(query),
    enabled: query.length > 0,
  });

  if (!query) {
    return null;
  }

  if (resultsQuery.isLoading) {
    return <p className="text-kabin-secondary">Searching…</p>;
  }

  const results = resultsQuery.data ?? [];

  return (
    <div>
      <p className="mb-4 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
        {results.length} {results.length === 1 ? "result" : "results"}
      </p>
      {results.length === 0 ? (
        <div className="max-w-lg space-y-2">
          <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
            No titles match “{query}”.
          </p>
          <button
            type="button"
            onClick={() => useUiStore.getState().setSearchQuery("")}
            className="text-kabin-accent"
          >
            Clear search
          </button>
        </div>
      ) : (
        <div className="kabin-library-grid">
          {results.map((title) => (
            <MediaTile key={title.id} title={title} />
          ))}
        </div>
      )}
    </div>
  );
}
