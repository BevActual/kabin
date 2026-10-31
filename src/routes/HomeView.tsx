import type { ReactNode } from "react";
import { Link, getRouteApi, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { ContinueHero } from "../components/ContinueHero";
import { LibraryCategories } from "../components/LibraryCategories";
import { ShelfRow } from "../components/ShelfRow";
import type { CatalogTitle, HomeShelf } from "../types/catalog";
import { scanLibrary } from "../lib/kabin-api";
import {
  getContentMode,
  homeSubtitle,
  isContentModeId,
  normalizeContentMode,
  shelvesForMode,
} from "../lib/modes";

const route = getRouteApi("/browse/$mode");

export function HomeView() {
  const { mode: modeId } = route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const mode = getContentMode(modeId);
  const scanQuery = useQuery({
    queryKey: ["libraryScan"],
    queryFn: () => scanLibrary(false),
  });

  useEffect(() => {
    if (!isContentModeId(modeId)) {
      void navigate({
        to: "/browse/$mode",
        params: { mode: normalizeContentMode(modeId) },
        replace: true,
      });
    }
  }, [modeId, navigate]);

  const refresh = () => {
    void queryClient.fetchQuery({
      queryKey: ["libraryScan"],
      queryFn: () => scanLibrary(true),
    });
    void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
  };

  if (!isContentModeId(modeId)) {
    return null;
  }

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
  const shelves = shelvesForMode(snapshot?.shelves ?? [], mode);
  const modeTitles = (snapshot?.titles ?? []).filter((title) =>
    mode.kinds.includes(title.kind),
  );
  const shown =
    shelves.length > 0
      ? shelves
      : modeTitles.length > 0
        ? [{ id: "library", label: "Library", titles: modeTitles.slice(0, 18) }]
        : [];
  const hero = pickContinueHero(shelves);

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <p className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
          {homeSubtitle(mode, modeTitles)}
        </p>
        <button
          type="button"
          onClick={refresh}
          className="inline-flex shrink-0 items-center gap-1.5 text-[calc(15px*var(--kabin-type-scale))] font-medium text-kabin-accent"
        >
          <RefreshCw size={16} strokeWidth={1.5} />
          Refresh
        </button>
      </div>

      <LibraryCategories mode={mode} titles={modeTitles} />

      {snapshot?.errors.map((err) => (
        <p
          key={`${err.source}-${err.message}`}
          className="mb-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary"
        >
          {err.source}: {err.message}
        </p>
      ))}

      {hero ? <ContinueHero title={hero} /> : null}

      {shown.length === 0 ? (
        <StatusMessage>
          {mode.emptyHint.split("Open Settings")[0]}
          <Link to="/settings" className="text-kabin-accent">
            Open Settings
          </Link>
          {mode.emptyHint.split("Open Settings")[1]}
        </StatusMessage>
      ) : (
        shown.map((shelf) => <ShelfRow key={shelf.id} shelf={shelf} />)
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
