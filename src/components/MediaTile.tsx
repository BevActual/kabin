import { Link } from "@tanstack/react-router";
import { motion, useReducedMotion } from "framer-motion";
import { Heart } from "lucide-react";
import { coverUrl } from "../lib/kabin-api";
import type { CatalogTitle, TileAspect } from "../types/catalog";

const widthClass: Record<TileAspect, string> = {
  poster: "w-[140px] sm:w-[156px] lg:w-[172px]",
  square: "w-[140px] sm:w-[156px]",
  widescreen: "w-[220px] sm:w-[248px]",
};

const ratioClass: Record<TileAspect, string> = {
  poster: "aspect-[2/3]",
  square: "aspect-square",
  widescreen: "aspect-video",
};

type Props = {
  title: CatalogTitle;
};

export function MediaTile({ title }: Props) {
  const art = coverUrl(title.coverPath);
  const reduceMotion = useReducedMotion();
  const progress =
    title.progress != null && title.progress > 0
      ? Math.min(100, Math.round(title.progress * 100))
      : 0;

  return (
    <Link
      to="/title/$titleId"
      params={{ titleId: title.id }}
      className={`group block shrink-0 focus:outline-none ${widthClass[title.aspect]}`}
      data-cabinet-tile=""
      data-title-id={title.id}
      tabIndex={0}
    >
      <div>
        <motion.article
          whileHover={reduceMotion ? undefined : { scale: 1.02 }}
          transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
          className={`relative overflow-hidden rounded-[var(--kabin-radius-tile)] bg-kabin-grouped shadow-[var(--kabin-shadow-tile)] group-hover:shadow-[var(--kabin-shadow-tile-focus)] group-focus-visible:scale-[1.06] group-focus-visible:shadow-[var(--kabin-focus-ring),var(--kabin-shadow-tile-focus)] ${ratioClass[title.aspect]}`}
        >
          {art ? (
            <img
              src={art}
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div
              className="absolute inset-0"
              style={{
                background: `linear-gradient(145deg, hsl(${title.accentHue} 42% 38%), hsl(${title.accentHue} 28% 18%))`,
              }}
            />
          )}
          {title.isFavorite ? (
            <span className="absolute top-2 right-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-black/45 text-white backdrop-blur-md">
              <Heart size={13} strokeWidth={1.75} className="fill-current" />
            </span>
          ) : null}
          {progress > 0 ? (
            <div className="absolute inset-x-0 bottom-0 h-[3px] bg-black/35">
              <div
                className="h-full bg-kabin-accent"
                style={{ width: `${progress}%` }}
              />
            </div>
          ) : null}
        </motion.article>
        <div className="pt-2">
          <p className="line-clamp-2 text-[calc(13px*var(--kabin-type-scale))] leading-snug font-semibold text-kabin-primary">
            {title.title}
          </p>
          <p className="mt-0.5 truncate text-[calc(12px*var(--kabin-type-scale))] text-kabin-secondary">
            {title.subtitle}
          </p>
        </div>
      </div>
    </Link>
  );
}
