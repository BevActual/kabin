import { Link, getRouteApi, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Heart } from "lucide-react";
import {
  coverUrl,
  getRelatedTitles,
  getTitleDetails,
  launchTitle,
  remoteGameStreamAvailable,
  remoteGameStreamStatus,
  startRemoteGameStream,
  stopRemoteGameStream,
  toggleFavorite,
} from "../lib/kabin-api";
import { MediaTile } from "../components/MediaTile";
import { getContentMode, modeForKind } from "../lib/modes";
import { resumeActionLabel } from "../lib/resumeRoute";
import { useUiStore } from "../store/ui";

const route = getRouteApi("/title/$titleId");

export function TitleDetailsView() {
  const { titleId } = route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const titleQuery = useQuery({
    queryKey: ["title", titleId],
    queryFn: () => getTitleDetails(titleId),
  });
  const relatedQuery = useQuery({
    queryKey: ["related", titleId],
    queryFn: () => getRelatedTitles(titleId),
  });
  const streamAvailableQuery = useQuery({
    queryKey: ["remoteStreamAvailable"],
    queryFn: remoteGameStreamAvailable,
  });
  const streamStatusQuery = useQuery({
    queryKey: ["remoteStreamStatus"],
    queryFn: remoteGameStreamStatus,
    refetchInterval: 2000,
  });

  const details = titleQuery.data;
  const title = details?.title;
  const contentMode = useUiStore((s) => s.contentMode);
  const setContentMode = useUiStore((s) => s.setContentMode);
  useEffect(() => {
    if (!title) return;
    setContentMode(modeForKind(title.kind).id);
  }, [title, setContentMode]);
  const metaLines = details?.metaLines ?? [];
  const isFavorite = details?.isFavorite ?? false;
  const favorite = useMutation({
    mutationFn: () => toggleFavorite(titleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["title", titleId] });
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
      void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
      void queryClient.invalidateQueries({ queryKey: ["library", "favorites"] });
    },
  });
  const launch = useMutation({
    mutationFn: () => launchTitle(titleId),
  });
  const stream = useMutation({
    mutationFn: () => startRemoteGameStream(titleId),
    onSuccess: () => {
      void streamStatusQuery.refetch();
    },
  });
  const stopStream = useMutation({
    mutationFn: () => stopRemoteGameStream(),
    onSuccess: () => {
      void streamStatusQuery.refetch();
    },
  });

  const playsInKabin = (kind: string) =>
    kind === "music" || kind === "audiobook" || kind === "video" || kind === "tv";
  const readsInKabin = (kind: string) =>
    kind === "book" || kind === "comic" || kind === "pdf";

  if (titleQuery.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!title) {
    return (
      <div>
        <p className="text-kabin-secondary">Title not found.</p>
        <Link
          to="/browse/$mode"
          params={{ mode: contentMode }}
          className="mt-4 inline-block text-kabin-accent"
        >
          Back to {getContentMode(contentMode).label}
        </Link>
      </div>
    );
  }

  const art = coverUrl(title.coverPath);
  const isRemoteGame = title.canLaunch === false && title.kind === "game";
  const canStreamRemote =
    isRemoteGame && (streamAvailableQuery.data ?? false);
  const streamingThis =
    streamStatusQuery.data != null &&
    streamStatusQuery.data.length > 0 &&
    stream.isSuccess;

  const related = relatedQuery.data;

  return (
    <div className="-mx-6">
      <section className="relative mb-10 overflow-hidden">
        {art ? (
          <img
            src={art}
            alt=""
            className="pointer-events-none absolute inset-0 h-full w-full scale-110 object-cover opacity-40 blur-3xl"
          />
        ) : (
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background: `linear-gradient(180deg, hsl(${title.accentHue} 36% 28%), transparent)`,
            }}
          />
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-[color-mix(in_srgb,var(--kabin-bg-base)_35%,transparent)] to-[var(--kabin-bg-base)]" />
        <div className="relative mx-auto flex max-w-4xl flex-col gap-6 px-6 pt-6 pb-2 sm:flex-row sm:items-end">
          <div
            className={`shrink-0 overflow-hidden rounded-[var(--kabin-radius-sheet)] shadow-[var(--kabin-shadow-tile-focus)] ${
              title.aspect === "widescreen"
                ? "aspect-video w-full max-w-sm"
                : title.aspect === "square"
                  ? "aspect-square w-44 sm:w-52"
                  : "aspect-[2/3] w-40 sm:w-52"
            }`}
            style={
              art
                ? undefined
                : {
                    background: `linear-gradient(145deg, hsl(${title.accentHue} 42% 38%), hsl(${title.accentHue} 28% 18%))`,
                  }
            }
          >
            {art ? (
              <img src={art} alt="" className="h-full w-full object-cover" />
            ) : null}
          </div>
          <div className="min-w-0 flex-1 pb-1">
            <div className="flex items-start gap-3">
              <h1 className="min-w-0 flex-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
                {title.title}
              </h1>
              <button
                type="button"
                disabled={favorite.isPending}
                onClick={() => favorite.mutate()}
                aria-label={
                  isFavorite ? "Remove from Favorites" : "Add to Favorites"
                }
                aria-pressed={isFavorite}
                className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors ${
                  isFavorite
                    ? "bg-kabin-accent/20 text-kabin-accent"
                    : "text-kabin-secondary hover:bg-kabin-grouped hover:text-kabin-primary"
                }`}
              >
                <Heart
                  size={22}
                  strokeWidth={1.5}
                  className={isFavorite ? "fill-current" : undefined}
                />
              </button>
            </div>
            <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
              {title.subtitle}
            </p>
      {metaLines.length > 0 ? (
        <p className="mt-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-tertiary">
          {metaLines.join(" · ")}
        </p>
      ) : null}
      {title.kind === "game" &&
      (title.playCount || title.playTimeLabel) ? (
        <p className="mt-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-tertiary">
          {title.playCount ? `${title.playCount} plays` : null}
          {title.playCount && title.playTimeLabel ? " · " : null}
          {title.playTimeLabel ? `${title.playTimeLabel} played` : null}
        </p>
      ) : null}
      {canStreamRemote ? (
        <p className="mt-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-tertiary">
          Streams through Kabin&apos;s media helper when the host is ready.
        </p>
      ) : null}
      <div className="mt-8 flex flex-wrap gap-3">
        {canStreamRemote ? (
          streamingThis || streamStatusQuery.data ? (
            <>
              <button
                type="button"
                disabled={stopStream.isPending}
                onClick={() => stopStream.mutate()}
                className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
              >
                Stop stream
              </button>
              <span className="self-center text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
                Streaming — video opens in Kabin&apos;s media window
              </span>
            </>
          ) : (
            <button
              type="button"
              disabled={stream.isPending}
              onClick={() => stream.mutate()}
              className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white disabled:opacity-50"
            >
              {stream.isPending ? "Preparing…" : "Stream"}
            </button>
          )
        ) : (
          <button
            type="button"
            disabled={
              launch.isPending ||
              (title.canLaunch === false &&
                !playsInKabin(title.kind) &&
                !readsInKabin(title.kind))
            }
            onClick={() => {
              if (playsInKabin(title.kind) && title.canLaunch !== false) {
                void navigate({ to: "/player/$titleId", params: { titleId } });
                return;
              }
              if (readsInKabin(title.kind) && title.canLaunch !== false) {
                void navigate({ to: "/read/$titleId", params: { titleId } });
                return;
              }
              launch.mutate();
            }}
            className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {launch.isPending && !playsInKabin(title.kind)
              ? "Launching…"
              : primaryAction(title.kind, title.canLaunch === false)}
          </button>
        )}
        {launch.isError ? (
          <p className="w-full text-[calc(14px*var(--kabin-type-scale))] text-red-400">
            {launch.error instanceof Error
              ? launch.error.message
              : "Launch failed"}
          </p>
        ) : null}
        {stream.isError ? (
          <p className="w-full text-[calc(14px*var(--kabin-type-scale))] text-red-400">
            {stream.error instanceof Error
              ? stream.error.message
              : "Stream failed"}
          </p>
        ) : null}
      </div>
          </div>
        </div>
      </section>
      {related && related.titles.length > 0 ? (
        <section className="mx-auto mt-4 max-w-4xl px-6">
          <h3 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold">
            {related.heading || "Up next"}
          </h3>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {related.titles.map((t) => (
              <MediaTile key={t.id} title={t} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function primaryAction(kind: string, blocked?: boolean) {
  if (blocked) return "Unavailable";
  return resumeActionLabel(kind);
}
