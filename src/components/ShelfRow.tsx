import type { HomeShelf } from "../types/catalog";
import { MediaTile } from "./MediaTile";

type Props = {
  shelf: HomeShelf;
};

export function ShelfRow({ shelf }: Props) {
  if (shelf.titles.length === 0) return null;

  return (
    <section className="mb-8">
      <h2 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
        {shelf.label}
      </h2>
      <div className="kabin-shelf-track overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {shelf.titles.map((title) => (
          <MediaTile
            key={title.id}
            title={title}
            scale={shelf.titles.length === 1 ? 1.28 : 1}
          />
        ))}
      </div>
    </section>
  );
}
