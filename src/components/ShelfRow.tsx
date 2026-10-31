import { Link } from "@tanstack/react-router";
import type { HomeShelf } from "../types/catalog";
import { legacyLibraryTarget, modeForKind } from "../lib/modes";
import { MediaTile } from "./MediaTile";

type Props = {
  shelf: HomeShelf;
};

export function ShelfRow({ shelf }: Props) {
  if (shelf.titles.length === 0) return null;
  const more = seeAllTarget(shelf);

  return (
    <section className="mb-8">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
          {shelf.label}
        </h2>
        {more ? (
          <Link
            to="/browse/$mode/$section"
            params={more}
            className="shrink-0 text-[calc(15px*var(--kabin-type-scale))] font-medium text-kabin-accent"
          >
            See All
          </Link>
        ) : null}
      </div>
      <div className="kabin-shelf-track overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {shelf.titles.map((title) => (
          <MediaTile key={title.id} title={title} />
        ))}
      </div>
    </section>
  );
}

function seeAllTarget(shelf: HomeShelf) {
  const title = shelf.titles[0];
  if (!title) return null;
  const mode = modeForKind(title.kind).id;
  if (shelf.id === "favorites" || shelf.id.startsWith("continue-")) {
    const played = shelf.id.startsWith("continue-") && title.kind === "game";
    return {
      mode,
      section: shelf.id === "favorites" ? "favorites" : played ? "played" : "progress",
    };
  }
  if (shelf.id.startsWith("added-") && (title.kind === "game" || title.kind === "music")) {
    return { mode: title.kind === "game" ? "games" : "music", section: "added" };
  }
  if (shelf.id.startsWith("added-") || shelf.id === "library") {
    if (shelf.id === "library" && title.kind === "game") return null;
    return legacyLibraryTarget(title.kind, mode);
  }
  return null;
}
