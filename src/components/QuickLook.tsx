import { Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { coverUrl, getTitle, toggleFavorite } from "../lib/kabin-api";
import { labelForKind } from "../lib/modes";
import { resumeActionLabel, resumeTarget } from "../lib/resumeRoute";
import { useUiStore } from "../store/ui";
import type { CatalogTitle, LibrarySnapshot } from "../types/catalog";

const aspectClass = {
  poster: "aspect-[2/3] sm:w-52",
  square: "aspect-square sm:w-56",
  widescreen: "aspect-video sm:w-72",
} as const;

export function QuickLook() {
  const titleId = useUiStore((s) => s.previewTitleId);
  const setPreviewTitleId = useUiStore((s) => s.setPreviewTitleId);
  const queryClient = useQueryClient();
  const primaryRef = useRef<HTMLAnchorElement>(null);
  const titleQuery = useQuery({
    queryKey: ["title-preview", titleId],
    queryFn: () => getTitle(titleId ?? ""),
    enabled: !!titleId,
    placeholderData: () => (titleId ? findCachedTitle(queryClient, titleId) : undefined),
  });

  const title = titleQuery.data ?? null;

  useEffect(() => {
    if (title) primaryRef.current?.focus();
  }, [title]);

  if (!titleId || !title) return null;

  const close = () => {
    setPreviewTitleId(null);
    document.querySelector<HTMLElement>(`[data-title-id="${CSS.escape(title.id)}"]`)?.focus();
  };
  const art = coverUrl(title.coverPath);
  const progress = Math.min(100, Math.max(0, (title.progress ?? 0) * 100));
  const target = resumeTarget(title);
  const direct = target.to !== "/title/$titleId";

  return (
    <div className="kabin-quicklook-backdrop" onMouseDown={close}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="kabin-quicklook-title"
        className="kabin-quicklook flex w-full max-w-[680px] flex-col gap-6 p-5 sm:flex-row sm:items-center"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={close}
          aria-label="Close preview"
          className="absolute top-3 right-3 inline-flex h-8 w-8 items-center justify-center rounded-full text-kabin-secondary hover:bg-kabin-grouped hover:text-kabin-primary"
        >
          <X size={18} strokeWidth={1.5} />
        </button>
        <div
          className={`relative w-full shrink-0 overflow-hidden rounded-[var(--kabin-radius-tile)] shadow-[var(--kabin-shadow-tile-focus)] ${aspectClass[title.aspect]}`}
          style={
            art
              ? undefined
              : {
                  background: `linear-gradient(145deg, hsl(${title.accentHue} 42% 38%), hsl(${title.accentHue} 28% 18%))`,
                }
          }
        >
          {art ? <img src={art} alt="" className="h-full w-full object-cover" /> : null}
        </div>
        <div className="min-w-0 flex-1 pb-1">
          <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
            {labelForKind(title.kind)}
          </p>
          <h2
            id="kabin-quicklook-title"
            className="mt-1 text-[calc(28px*var(--kabin-type-scale))] font-semibold tracking-tight"
          >
            {title.title}
          </h2>
          <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
            {title.subtitle}
          </p>
          {progress > 0 ? (
            <div className="mt-4 h-1 max-w-xs overflow-hidden rounded-full bg-kabin-separator">
              <div className="h-full rounded-full bg-kabin-accent" style={{ width: `${progress}%` }} />
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Link
              ref={primaryRef}
              to={target.to}
              params={target.params}
              onClick={() => setPreviewTitleId(null)}
              className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
            >
              {direct ? resumeActionLabel(title.kind) : "Open"}
            </Link>
            {direct ? (
              <Link
                to="/title/$titleId"
                params={{ titleId: title.id }}
                onClick={() => setPreviewTitleId(null)}
                className="rounded-[var(--kabin-radius-control)] px-4 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-medium text-kabin-accent hover:bg-kabin-grouped"
              >
                Details
              </Link>
            ) : null}
            {title.id.startsWith("show:") ? null : <FavoriteButton title={title} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function FavoriteButton({ title }: { title: CatalogTitle }) {
  const queryClient = useQueryClient();
  const favorite = !!title.isFavorite;

  return (
    <button
      type="button"
      aria-label={favorite ? "Remove from Favorites" : "Add to Favorites"}
      aria-pressed={favorite}
      onClick={() => {
        void toggleFavorite(title.id).then((next) => {
          patchFavorite(queryClient, title.id, next);
        });
      }}
      className={`inline-flex h-10 w-10 items-center justify-center rounded-full ${
        favorite
          ? "bg-kabin-accent/20 text-kabin-accent"
          : "text-kabin-secondary hover:bg-kabin-grouped hover:text-kabin-primary"
      }`}
    >
      <Heart size={20} strokeWidth={1.5} className={favorite ? "fill-current" : undefined} />
    </button>
  );
}

function findCachedTitle(
  queryClient: ReturnType<typeof useQueryClient>,
  titleId: string,
): CatalogTitle | undefined {
  const snapshot = queryClient.getQueryData<LibrarySnapshot>(["libraryScan"]);
  const fromScan = snapshot?.titles.find((title) => title.id === titleId);
  if (fromScan) return fromScan;
  const lists = queryClient.getQueriesData<CatalogTitle[]>({ queryKey: ["library"] });
  for (const [, titles] of lists) {
    const match = titles?.find((title) => title.id === titleId);
    if (match) return match;
  }
  return undefined;
}

function patchFavorite(
  queryClient: ReturnType<typeof useQueryClient>,
  titleId: string,
  isFavorite: boolean,
) {
  const patch = (title: CatalogTitle) =>
    title.id === titleId ? { ...title, isFavorite } : title;
  queryClient.setQueryData<CatalogTitle | null>(["title-preview", titleId], (current) =>
    current ? patch(current) : current,
  );
  queryClient.setQueryData<{ title: CatalogTitle; isFavorite: boolean } | null>(
    ["title", titleId],
    (current) => {
      if (!current?.title) return current;
      return {
        ...current,
        isFavorite,
        title: patch(current.title),
      };
    },
  );
  queryClient.setQueryData<LibrarySnapshot>(["libraryScan"], (current) => {
    if (!current) return current;
    return {
      ...current,
      titles: current.titles.map(patch),
      shelves: current.shelves.map((shelf) => ({
        ...shelf,
        titles: shelf.titles.map(patch),
      })),
    };
  });
  void queryClient.invalidateQueries({ queryKey: ["library"] });
}
