import { Link, getRouteApi, useNavigate } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { getLibraryTitles } from "../lib/kabin-api";
import {
  getContentMode,
  isContentModeId,
  normalizeContentMode,
  sectionForMode,
} from "../lib/modes";
import { MediaTile } from "../components/MediaTile";
import { consoleGroups, gamesInSection } from "../lib/games";
import { libraryEntries } from "../lib/shows";
import { SegmentedControl } from "../components/SegmentedControl";
import type { CatalogTitle } from "../types/catalog";
import { useUiStore, type LibrarySort } from "../store/ui";
import { useEffect } from "react";

const route = getRouteApi("/browse/$mode/$section");

export function ModeSectionView() {
  const { mode: modeId, section: sectionId } = route.useParams();
  const navigate = useNavigate();
  const searchQuery = useUiStore((s) => s.searchQuery.trim());
  const librarySort = useUiStore((s) => s.librarySort);
  const setLibrarySort = useUiStore((s) => s.setLibrarySort);
  const mode = getContentMode(modeId);
  const section = isContentModeId(modeId)
    ? sectionForMode(mode, sectionId)
    : null;

  useEffect(() => {
    if (!isContentModeId(modeId) || !section) {
      void navigate({
        to: "/browse/$mode",
        params: { mode: normalizeContentMode(modeId) },
        replace: true,
      });
    }
  }, [modeId, section, navigate]);

  const kinds = section?.id === "favorites" ? ["favorites"] : (section?.kinds ?? mode.kinds);
  const queries = useQueries({
    queries: kinds.map((kind) => ({
      queryKey: ["library", kind],
      queryFn: () => getLibraryTitles(kind),
      enabled: !searchQuery && !!section,
    })),
  });

  if (searchQuery || !section) {
    return null;
  }

  if (queries.some((query) => query.isLoading)) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  let titles = queries.flatMap((query) => query.data ?? []);
  if (section.id === "favorites") {
    const allowed = section.kinds ?? mode.kinds;
    titles = titles.filter((title) => allowed.includes(title.kind));
  }
  titles = libraryEntries(titles, section.id);
  titles = gamesInSection(titles, section.id);
  const sortMode = section.id === "added" ? "added" : section.id === "played" ? "recent" : librarySort;
  const sorted = sortTitles(titles, sortMode);
  const systems = section.id === "consoles" ? consoleGroups(sorted) : [];

  return (
    <div>
      {sorted.length > 0 ? (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
            {countLabel(mode.id, section.id, sorted.length)}
          </p>
          {section.id === "added" || section.id === "played" ? null : (
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
          )}
        </div>
      ) : null}
      {sorted.length === 0 ? (
        <EmptySection
          modeLabel={mode.label}
          sectionId={section.id}
          hint={section.emptyHint ?? mode.emptyHint}
        />
      ) : systems.length > 1 ? (
        <div className="space-y-10">
          {systems.map((system) => (
            <section key={system.name}>
              <div className="mb-4 flex items-baseline justify-between gap-4">
                <h2 className="text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
                  {system.name}
                </h2>
                <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
                  {system.titles.length === 1 ? "1 game" : `${system.titles.length} games`}
                </p>
              </div>
              <div className="kabin-library-grid">
                {system.titles.map((title) => (
                  <MediaTile key={title.id} title={title} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="kabin-library-grid">
          {sorted.map((title) => (
            <MediaTile key={title.id} title={title} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptySection({
  modeLabel,
  sectionId,
  hint,
}: {
  modeLabel: string;
  sectionId: string;
  hint: string;
}) {
  if (sectionId === "favorites") {
    return (
      <div className="max-w-lg">
        <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
          No favorite {modeLabel.toLowerCase()} yet.
        </p>
        <p className="mt-2 text-[calc(15px*var(--kabin-type-scale))] text-kabin-tertiary">
          Open a title and tap the heart to save it here.
        </p>
      </div>
    );
  }
  if (sectionId === "progress") {
    return (
      <div className="max-w-lg">
        <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
          Nothing in progress.
        </p>
        <p className="mt-2 text-[calc(15px*var(--kabin-type-scale))] text-kabin-tertiary">
          {modeLabel} you have started show up here until you finish them.
        </p>
      </div>
    );
  }
  if (!hint.includes("Open Settings")) {
    return (
      <div className="max-w-lg">
        <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">{hint}</p>
      </div>
    );
  }
  const [before, after] = hint.split("Open Settings");
  return (
    <div className="max-w-lg">
      <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
        {before}
        <Link to="/settings" className="text-kabin-accent">
          Open Settings
        </Link>
        {after}
      </p>
    </div>
  );
}

function countLabel(modeId: string, sectionId: string, count: number) {
  if (sectionId === "tv") return count === 1 ? "1 show" : `${count} shows`;
  if (modeId === "games") return count === 1 ? "1 game" : `${count} games`;
  return count === 1 ? "1 title" : `${count} titles`;
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
