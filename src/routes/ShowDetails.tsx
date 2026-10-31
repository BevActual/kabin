import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { getLibraryTitles } from "../lib/kabin-api";
import {
  episodeProgressLabel,
  episodesForShow,
  resumeEpisode,
  showTile,
} from "../lib/shows";

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

  return (
    <div className="max-w-3xl">
      <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
        TV
      </p>
      <h1 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
        {show.title}
      </h1>
      <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
        {show.subtitle}
      </p>
      <div className="mt-6">
        <Link
          to="/player/$titleId"
          params={{ titleId: next.id }}
          className="inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
        >
          {started ? "Continue" : "Watch"}
        </Link>
        <p className="mt-2 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
          {next.subtitle} · {next.title}
        </p>
      </div>
      <div className="kabin-grouped mt-8">
        {episodes.map((episode) => {
          const mark = episodeProgressLabel(episode);
          return (
            <Link
              key={episode.id}
              to="/title/$titleId"
              params={{ titleId: episode.id }}
              className="kabin-grouped-row hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_5%,transparent)]"
            >
              <span className="w-16 shrink-0 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
                {episode.subtitle}
              </span>
              <span className="min-w-0 flex-1 truncate text-[calc(15px*var(--kabin-type-scale))]">
                {episode.title}
              </span>
              {mark ? (
                <span className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary tabular-nums">
                  {mark}
                </span>
              ) : null}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
