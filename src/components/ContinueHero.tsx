import { Link } from "@tanstack/react-router";
import type { CatalogTitle } from "../types/catalog";
import { coverUrl } from "../lib/kabin-api";
import { resumeActionLabel, resumeTarget } from "../lib/resumeRoute";

type Props = {
  title: CatalogTitle;
};

export function ContinueHero({ title }: Props) {
  const art = coverUrl(title.coverPath);
  const progress = Math.min(100, Math.max(0, (title.progress ?? 0) * 100));
  const target = resumeTarget(title);

  return (
    <section className="kabin-continue-hero mb-10 overflow-hidden rounded-[var(--kabin-radius-sheet)]">
      <div
        className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-end sm:p-8"
        style={{
          background: art
            ? undefined
            : `linear-gradient(135deg, hsl(${title.accentHue} 38% 28%) 0%, hsl(${title.accentHue} 22% 12%) 100%)`,
        }}
      >
        {art ? (
          <>
            <img
              src={art}
              alt=""
              className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-35"
            />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[var(--kabin-bg-base)] via-[color-mix(in_srgb,var(--kabin-bg-base)_55%,transparent)] to-transparent" />
          </>
        ) : null}
        <div
          className="relative aspect-[2/3] w-36 shrink-0 overflow-hidden rounded-[var(--kabin-radius-tile)] shadow-[var(--kabin-shadow-tile-focus)] sm:w-44"
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
        <div className="relative min-w-0 flex-1 pb-1">
          <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
            Continue
          </p>
          <h2 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
            {title.title}
          </h2>
          <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
            {title.subtitle}
          </p>
          {progress > 0 ? (
            <div className="mt-4 max-w-md">
              <div className="h-1 overflow-hidden rounded-full bg-kabin-separator">
                <div
                  className="h-full rounded-full bg-kabin-accent transition-[width] duration-[var(--kabin-motion-fast)]"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          ) : null}
          <Link
            to={target.to}
            params={target.params}
            className="mt-6 inline-flex rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white transition-opacity hover:opacity-90"
          >
            {resumeActionLabel(title.kind)}
          </Link>
        </div>
      </div>
    </section>
  );
}
