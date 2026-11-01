import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Headphones } from "lucide-react";
import { coverUrl, getLibraryTitles } from "../lib/kabin-api";
import { authorIdFor, sharedAuthor } from "../lib/authors";
import {
  isSeriesId,
  resumeVolume,
  seriesFromLibrary,
  volumeLabel,
  volumeProgressLabel,
  volumesForSeries,
} from "../lib/series";
import type { CatalogTitle } from "../types/catalog";

type Props = {
  seriesId: string;
};

export function SeriesDetails({ seriesId }: Props) {
  const kind = seriesKind(seriesId);
  const query = useQuery({
    queryKey: ["library", kind],
    queryFn: () => getLibraryTitles(kind),
    enabled: !!kind,
  });
  const volumes = volumesForSeries(query.data ?? [], seriesId);
  const series = volumes.length ? seriesFromLibrary(query.data ?? [], seriesId) : null;
  const next = resumeVolume(volumes);
  const author = sharedAuthor(volumes);

  if (query.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!series || !next) {
    return (
      <div>
        <p className="text-kabin-secondary">Series not found.</p>
        <Link
          to="/browse/$mode/$section"
          params={{ mode: "books", section: "series" }}
          className="mt-4 inline-block text-kabin-accent"
        >
          Back to Series
        </Link>
      </div>
    );
  }

  const started = (next.progress ?? 0) > 0.02 && (next.progress ?? 0) < 0.98;
  const listening = next.kind === "audiobook";
  const progress = Math.min(100, Math.max(0, (series.progress ?? 0) * 100));
  const art = coverUrl(series.coverPath);

  return (
    <div className="-mx-6">
      <section className="kabin-continue-hero relative mb-8 overflow-hidden rounded-[var(--kabin-radius-sheet)]">
        <div
          className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-end sm:p-8"
          style={{
            background: `linear-gradient(135deg, hsl(${series.accentHue} 38% 28%) 0%, hsl(${series.accentHue} 22% 12%) 100%)`,
          }}
        >
          <div
            className={`relative shrink-0 overflow-hidden rounded-[var(--kabin-radius-tile)] shadow-[var(--kabin-shadow-tile-focus)] ${
              series.aspect === "square"
                ? "aspect-square w-40 sm:w-52"
                : "aspect-[2/3] w-36 sm:w-44"
            }`}
            style={
              art
                ? undefined
                : {
                    background: `linear-gradient(145deg, hsl(${series.accentHue} 42% 38%), hsl(${series.accentHue} 28% 18%))`,
                  }
            }
          >
            {art ? <img src={art} alt="" className="h-full w-full object-cover" /> : null}
          </div>
          <div className="relative min-w-0 flex-1 pb-1 text-white">
            {author ? (
              <Link
                to="/title/$titleId"
                params={{ titleId: authorIdFor(author) }}
                className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-white/70 uppercase hover:text-white"
              >
                {author}
              </Link>
            ) : (
              <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-white/70 uppercase">
                Series
              </p>
            )}
            <h1 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
              {series.title}
            </h1>
            <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-white/70">
              {series.subtitle}
            </p>
            {progress > 0 ? (
              <div className="mt-4 h-1 max-w-md overflow-hidden rounded-full bg-white/20">
                <div className="h-full rounded-full bg-white" style={{ width: `${progress}%` }} />
              </div>
            ) : null}
            <Link
              to={listening ? "/player/$titleId" : "/read/$titleId"}
              params={{ titleId: next.id }}
              className="mt-6 inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white"
            >
              {started ? "Continue" : listening ? "Listen" : "Read"}
            </Link>
            <p className="mt-2 text-[calc(13px*var(--kabin-type-scale))] text-white/70">
              {volumeLabel(next)} · {next.title}
            </p>
          </div>
        </div>
      </section>
      <div className="kabin-grouped mx-6 max-w-3xl">
        {volumes.map((volume) => (
          <VolumeRow key={volume.id} volume={volume} current={volume.id === next.id} />
        ))}
      </div>
    </div>
  );
}

function VolumeRow({ volume, current }: { volume: CatalogTitle; current: boolean }) {
  const mark = volumeProgressLabel(volume);
  const ratio = volume.progress ?? 0;
  const partial = ratio > 0.02 && ratio < 0.98;
  const listening = volume.kind === "audiobook";
  const Icon = listening ? Headphones : BookOpen;
  return (
    <div
      className={`kabin-grouped-row ${
        current ? "bg-[color-mix(in_srgb,var(--kabin-accent)_12%,transparent)]" : ""
      }`}
    >
      <Link
        to="/title/$titleId"
        params={{ titleId: volume.id }}
        className="flex min-w-0 flex-1 items-center gap-4"
      >
        <span className="w-16 shrink-0 text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
          {volumeLabel(volume)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[calc(15px*var(--kabin-type-scale))]">
            {volume.title}
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
        to={listening ? "/player/$titleId" : "/read/$titleId"}
        params={{ titleId: volume.id }}
        aria-label={`${listening ? "Listen to" : "Read"} ${volume.title}`}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
      >
        <Icon size={16} strokeWidth={1.75} />
      </Link>
    </div>
  );
}

function seriesKind(seriesId: string) {
  if (!isSeriesId(seriesId)) return "";
  const rest = seriesId.slice("series:".length);
  const split = rest.indexOf(":");
  return split > 0 ? rest.slice(0, split) : "";
}
