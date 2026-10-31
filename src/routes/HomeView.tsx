import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { ContinueHero } from "../components/ContinueHero";
import { ShelfRow } from "../components/ShelfRow";
import type { CatalogTitle, HomeShelf } from "../types/catalog";
import { scanLibrary } from "../lib/kabin-api";

export function HomeView() {
  const queryClient = useQueryClient();
  const scanQuery = useQuery({
    queryKey: ["libraryScan"],
    queryFn: () => scanLibrary(false),
  });

  const refresh = () => {
    void queryClient.fetchQuery({
      queryKey: ["libraryScan"],
      queryFn: () => scanLibrary(true),
    });
    void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
  };

  if (scanQuery.isLoading) {
    return <StatusMessage>Scanning your library…</StatusMessage>;
  }

  if (scanQuery.isError) {
    return (
      <StatusMessage>
        Could not read your library. Check Settings for folder paths, then try
        again.
      </StatusMessage>
    );
  }

  const snapshot = scanQuery.data;
  const shelves = snapshot?.shelves ?? [];
  const hero = pickContinueHero(shelves);

  return (
    <div>
      <div className="mb-6 flex justify-end">
        <button
          type="button"
          onClick={refresh}
          className="inline-flex items-center gap-1.5 text-[calc(15px*var(--kabin-type-scale))] font-medium text-kabin-accent"
        >
          <RefreshCw size={16} strokeWidth={1.5} />
          Refresh
        </button>
      </div>

      {snapshot?.errors.map((err) => (
        <p
          key={`${err.source}-${err.message}`}
          className="mb-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary"
        >
          {err.source}: {err.message}
        </p>
      ))}

      {hero ? <ContinueHero title={hero} /> : null}

      {shelves.length === 0 ? (
        <StatusMessage>
          Nothing here yet.{" "}
          <Link to="/settings" className="text-kabin-accent">
            Open Settings
          </Link>{" "}
          to add media folders, Steam, or a paired host, then refresh.
        </StatusMessage>
      ) : (
        shelves.map((shelf) => <ShelfRow key={shelf.id} shelf={shelf} />)
      )}
    </div>
  );
}

function pickContinueHero(shelves: HomeShelf[]): CatalogTitle | null {
  let best: CatalogTitle | null = null;
  let bestProgress = 0;
  for (const shelf of shelves) {
    if (!shelf.id.startsWith("continue-")) continue;
    for (const title of shelf.titles) {
      const progress = title.progress ?? 0;
      if (progress > bestProgress) {
        bestProgress = progress;
        best = title;
      }
    }
  }
  return best;
}

function StatusMessage({ children }: { children: ReactNode }) {
  return (
    <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
      {children}
    </p>
  );
}
