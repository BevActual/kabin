import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { coverUrl, getPlaybackSession, toggleFavorite } from "../lib/kabin-api";
import { artistIdFor, artistName } from "../lib/music";
import type { CatalogTitle } from "../types/catalog";

type Props = {
  title: CatalogTitle;
};

export function AlbumDetails({ title }: Props) {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["playback", title.id],
    queryFn: () => getPlaybackSession(title.id),
  });
  const favorite = useMutation({
    mutationFn: () => toggleFavorite(title.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["title", title.id] });
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
      void queryClient.invalidateQueries({ queryKey: ["library", "music"] });
    },
  });
  const artist = artistName(title);
  const tracks = sessionQuery.data?.tracks ?? [];
  const count = tracks.length || title.trackCount || 0;
  const progress = Math.min(100, Math.max(0, (title.progress ?? 0) * 100));
  const started = (title.progress ?? 0) > 0.02 && (title.progress ?? 0) < 0.98;
  const art = coverUrl(title.coverPath);

  return (
    <div className="-mx-6">
      <section className="kabin-continue-hero relative mb-8 overflow-hidden rounded-[var(--kabin-radius-sheet)]">
        <div
          className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-end sm:p-8"
          style={{
            background: `linear-gradient(135deg, hsl(${title.accentHue} 38% 28%) 0%, hsl(${title.accentHue} 22% 12%) 100%)`,
          }}
        >
          <div
            className="relative aspect-square w-40 shrink-0 overflow-hidden rounded-[var(--kabin-radius-tile)] shadow-[var(--kabin-shadow-tile-focus)] sm:w-52"
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
          <div className="relative min-w-0 flex-1 pb-1 text-white">
            {artist ? (
              <Link
                to="/title/$titleId"
                params={{ titleId: artistIdFor(artist) }}
                className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-white/70 uppercase hover:text-white"
              >
                {artist}
              </Link>
            ) : (
              <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-white/70 uppercase">
                Album
              </p>
            )}
            <div className="mt-1 flex items-start gap-3">
              <h1 className="min-w-0 flex-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
                {title.title}
              </h1>
              <button
                type="button"
                disabled={favorite.isPending}
                onClick={() => favorite.mutate()}
                aria-label={title.isFavorite ? "Remove from Favorites" : "Add to Favorites"}
                aria-pressed={!!title.isFavorite}
                className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                  title.isFavorite ? "bg-white/20 text-white" : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <Heart
                  size={22}
                  strokeWidth={1.5}
                  className={title.isFavorite ? "fill-current" : undefined}
                />
              </button>
            </div>
            <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-white/70">
              {count === 1 ? "1 song" : count > 1 ? `${count} songs` : "Album"}
            </p>
            {progress > 0 ? (
              <div className="mt-4 h-1 max-w-md overflow-hidden rounded-full bg-white/20">
                <div className="h-full rounded-full bg-white" style={{ width: `${progress}%` }} />
              </div>
            ) : null}
            <Link
              to="/player/$titleId"
              params={{ titleId: title.id }}
              className="mt-6 inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
            >
              {started ? "Continue" : "Listen"}
            </Link>
          </div>
        </div>
      </section>
      {tracks.length > 0 ? (
        <div className="kabin-grouped mx-6 max-w-3xl">
          {tracks.map((track, index) => (
            <div key={`${track.path}-${index}`} className="kabin-grouped-row">
              <span className="w-8 shrink-0 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-[calc(15px*var(--kabin-type-scale))]">
                {track.label}
              </span>
            </div>
          ))}
        </div>
      ) : sessionQuery.isLoading ? (
        <p className="mx-6 text-kabin-secondary">Loading songs…</p>
      ) : null}
    </div>
  );
}
