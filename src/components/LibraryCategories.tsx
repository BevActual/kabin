import { Link } from "@tanstack/react-router";
import type { ContentMode } from "../lib/modes";
import type { CatalogTitle } from "../types/catalog";

type Props = {
  mode: ContentMode;
  titles: CatalogTitle[];
};

export function LibraryCategories({ mode, titles }: Props) {
  const categories = mode.sections.filter((section) => section.kinds?.length);
  if (categories.length < 2) return null;

  return (
    <div className="kabin-category-row mb-8">
      {categories.map((section) => {
        const count = titles.filter((title) =>
          section.kinds?.includes(title.kind),
        ).length;
        const Icon = section.icon;
        return (
          <Link
            key={section.id}
            to="/browse/$mode/$section"
            params={{ mode: mode.id, section: section.id }}
            className="kabin-category-card"
          >
            <span className="kabin-category-icon">
              <Icon size={18} strokeWidth={1.5} />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[calc(15px*var(--kabin-type-scale))] font-semibold">
                {section.label}
              </span>
              <span className="block text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary tabular-nums">
                {count === 0 ? "None yet" : count === 1 ? "1 title" : `${count} titles`}
              </span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}
