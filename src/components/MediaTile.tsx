import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { coverUrl } from "../lib/kabin-api";
import type { CatalogTitle, TileAspect } from "../types/catalog";

const aspectClass: Record<TileAspect, string> = {
  poster: "aspect-[2/3] w-[140px] sm:w-[156px] lg:w-[172px]",
  square: "aspect-square w-[140px] sm:w-[156px]",
  widescreen: "aspect-video w-[220px] sm:w-[248px]",
};

type Props = {
  title: CatalogTitle;
};

export function MediaTile({ title }: Props) {
  const art = coverUrl(title.coverPath);

  return (
    <Link
      to="/title/$titleId"
      params={{ titleId: title.id }}
      className="group block shrink-0 rounded-[var(--kabin-radius-tile)] focus:outline-none"
      data-cabinet-tile=""
      tabIndex={0}
    >
      <motion.article
        whileHover={{ scale: 1.02 }}
        transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
        className={`relative overflow-hidden rounded-[var(--kabin-radius-tile)] bg-kabin-grouped shadow-[var(--kabin-shadow-tile)] group-hover:shadow-[var(--kabin-shadow-tile-focus)] group-focus-visible:scale-[1.06] group-focus-visible:shadow-[var(--kabin-shadow-tile-focus)] ${aspectClass[title.aspect]}`}
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
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-3 pt-10">
          <p className="line-clamp-2 text-[calc(15px*var(--kabin-type-scale))] leading-snug font-semibold text-white">
            {title.title}
          </p>
          <p className="mt-0.5 truncate text-[calc(12px*var(--kabin-type-scale))] text-white/70">
            {title.subtitle}
          </p>
        </div>
        {title.progress != null && title.progress > 0 ? (
          <div className="absolute inset-x-0 bottom-0 h-[3px] bg-white/20">
            <div
              className="h-full bg-kabin-accent"
              style={{ width: `${Math.round(title.progress * 100)}%` }}
            />
          </div>
        ) : null}
      </motion.article>
    </Link>
  );
}
