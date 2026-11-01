import { Link } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { MediaTile } from "../components/MediaTile";
import { getLibraryTitles } from "../lib/kabin-api";
import { authorFromLibrary, worksForAuthor } from "../lib/authors";
import type { CatalogTitle } from "../types/catalog";

const kinds = ["book", "audiobook", "comic", "pdf"] as const;

type Props = {
  authorId: string;
};

export function AuthorDetails({ authorId }: Props) {
  const queries = useQueries({
    queries: kinds.map((kind) => ({
      queryKey: ["library", kind],
      queryFn: () => getLibraryTitles(kind),
    })),
  });
  const titles = queries.flatMap((query) => query.data ?? []);
  const author = authorFromLibrary(titles, authorId);
  const works = worksForAuthor(titles, authorId);

  if (queries.some((query) => query.isLoading)) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!author) {
    return (
      <div>
        <p className="text-kabin-secondary">Author not found.</p>
        <Link
          to="/browse/$mode/$section"
          params={{ mode: "books", section: "authors" }}
          className="mt-4 inline-block text-kabin-accent"
        >
          Back to Authors
        </Link>
      </div>
    );
  }

  const sections: { label: string; titles: CatalogTitle[] }[] = [
    { label: "Books", titles: works.books },
    { label: "Audiobooks", titles: works.audiobooks },
    { label: "Comics", titles: works.comics },
    { label: "PDFs", titles: works.pdfs },
  ];

  return (
    <div>
      <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
        Author
      </p>
      <h1 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
        {author.title}
      </h1>
      <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
        {author.subtitle}
      </p>
      {sections.map((section) =>
        section.titles.length ? (
          <section key={section.label} className="mt-8">
            <h2 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
              {section.label}
            </h2>
            <div className="kabin-library-grid">
              {section.titles.map((title) => (
                <MediaTile key={title.id} title={title} />
              ))}
            </div>
          </section>
        ) : null,
      )}
    </div>
  );
}
