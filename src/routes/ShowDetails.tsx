import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { coverUrl, getLibraryTitles } from "../lib/kabin-api";
import {
  episodeProgressLabel,
  episodesForShow,
  resumeEpisode,
  showTile,
} from "../lib/shows";
import type { CatalogTitle } from "../types/catalog";

type Props = {
  showId: string;
};

export function ShowDetails({ showId }: Props) {
  const query = useQuery({
    queryKey: ["library", "tv"],
    queryFn: () => getLibraryTitles("tv"),
  });
  const episodes = episodesForShow(query.data ?? [], showId);
  const show = episodes.length ? showTile(episodes) : null;
  const next = resumeEpisode(episodes);

  if (query.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!show || !next) {
    return (
      <div>
        <p className="text-kabin-secondary">Show not found.</p>
        <Link
          to="/browse/$mode/$section"
          params={{ mode: "video", section: "tv" }}
          className="mt-4 inline-block text-kabin-accent"
        >
          Back to TV
        </Link>
      </div>
    );
  }

  const started = (next.progress ?? 0) > 0.02 && (next.progress ?? 0) < 0.98;
  const progress = Math.min(100, Math.max(0, (show.progress ?? 0) * 100));
  const art = coverUrl(show.coverPath);

  return (
    <div className="-mx-6">
      <section className="kabin-continue-hero relative mb-8 overflow-hidden rounded-[var(--kabin-radius-sheet)]">
        <div
          className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-end sm:p-8"
          style={{
            background: `linear-gradient(135deg, hsl(${show.accentHue} 38% 28%) 0%, hsl(${show.accentHue} 22% 12%) 100%)`,
          }}
        >
          {art ? (
            <div className="relative aspect-video w-full max-w-sm shrink-0 overflow-hidden rounded-[var(--kabin-radius-tile)] shadow-[var(--kabin-shadow-tile-focus)]">
              <img src={art} alt="" className="h-full w-full object-cover" />
            </div>
          ) : null}
          <div className="relative min-w-0 flex-1 pb-1 text-white">
            <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-white/70 uppercase">
              TV
            </p>
            <h1 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
              {show.title}
            </h1>
            <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-white/70">
              {show.subtitle}
            </p>
            {progress > 0 ? (
              <div className="mt-4 h-1 max-w-md overflow-hidden rounded-full bg-white/20">
                <div className="h-full rounded-full bg-white" style={{ width: `${progress}%` }} />
              </div>
            ) : null}
            <Link
              to="/player/$titleId"
              params={{ titleId: next.id }}
              className="mt-6 inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
            >
              {started ? "Continue" : "Watch"}
            </Link>
            <p className="mt-2 text-[calc(13px*var(--kabin-type-scale))] text-white/70">
              {next.subtitle} · {next.title}
            </p>
          </div>
        </div>
      </section>
      <div className="kabin-grouped mx-6 max-w-3xl">
        {episodes.map((episode) => (
          <EpisodeRow key={episode.id} episode={episode} current={episode.id === next.id} />
        ))}
      </div>
    </div>
  );
}

function EpisodeRow({ episode, current }: { episode: CatalogTitle; current: boolean }) {
  const mark = episodeProgressLabel(episode);
  const ratio = episode.progress ?? 0;
  const partial = ratio > 0.02 && ratio < 0.98;
  return (
    <div
      className={`kabin-grouped-row ${
        current ? "bg-[color-mix(in_srgb,var(--kabin-accent)_12%,transparent)]" : ""
      }`}
    >
      <Link
        to="/title/$titleId"
        params={{ titleId: episode.id }}
        className="flex min-w-0 flex-1 items-center gap-4"
      >
        <span className="w-16 shrink-0 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
          {episode.subtitle}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[calc(15px*var(--kabin-type-scale))]">
            {episode.title}
          </span>
          {partial ? (
            <span className="mt-1.5 block h-0.5 max-w-36 overflow-hidden rounded-full bg-kabin-separator">
              <span
                className="block h-full bg-kabin-accent"
                style={{ width: `${Math.round(ratio * 100)}%` }}
              />
            </span>
          ) : null}
        </span>
        {mark ? (
          <span className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary tabular-nums">
            {mark}
          </span>
        ) : null}
      </Link>
      <Link
        to="/player/$titleId"
        params={{ titleId: episode.id }}
        aria-label={`Watch ${episode.title}`}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
      >
        <Play size={16} strokeWidth={1.75} className="fill-current" />
      </Link>
    </div>
  );
}
