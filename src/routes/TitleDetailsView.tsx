import { Link, getRouteApi, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMutation } from "@tanstack/react-query";
import { coverUrl, getTitle, launchTitle } from "../lib/kabin-api";

const route = getRouteApi("/title/$titleId");

export function TitleDetailsView() {
  const { titleId } = route.useParams();
  const navigate = useNavigate();
  const titleQuery = useQuery({
    queryKey: ["title", titleId],
    queryFn: () => getTitle(titleId),
  });

  const title = titleQuery.data;
  const launch = useMutation({
    mutationFn: () => launchTitle(titleId),
  });

  const playsInKabin = (kind: string) =>
    kind === "music" || kind === "video" || kind === "tv";

  if (titleQuery.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!title) {
    return (
      <div>
        <p className="text-kabin-secondary">Title not found.</p>
        <Link to="/" className="mt-4 inline-block text-kabin-accent">
          Back to Home
        </Link>
      </div>
    );
  }

  const art = coverUrl(title.coverPath);

  return (
    <div className="mx-auto max-w-3xl">
      <div
        className="mb-8 aspect-[2/3] max-w-xs overflow-hidden rounded-[var(--kabin-radius-sheet)] shadow-[var(--kabin-shadow-tile-focus)]"
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
      <h2 className="text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
        {title.title}
      </h2>
      <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
        {title.subtitle}
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={launch.isPending}
          onClick={() => {
            if (playsInKabin(title.kind)) {
              void navigate({ to: "/player/$titleId", params: { titleId } });
              return;
            }
            launch.mutate();
          }}
          className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {launch.isPending && !playsInKabin(title.kind)
            ? "Launching…"
            : primaryAction(title.kind)}
        </button>
        {launch.isError ? (
          <p className="w-full text-[calc(14px*var(--kabin-type-scale))] text-red-400">
            {launch.error instanceof Error
              ? launch.error.message
              : "Launch failed"}
          </p>
        ) : null}
        <Link
          to="/"
          className="rounded-[var(--kabin-radius-control)] px-5 py-2.5 text-[calc(17px*var(--kabin-type-scale))] font-medium text-kabin-accent"
        >
          Done
        </Link>
      </div>
      <section className="mt-12">
        <h3 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold">
          Up next
        </h3>
        <p className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
          Recommendation shelves will mirror the GTK details page once catalog
          metadata is ported to Rust.
        </p>
      </section>
    </div>
  );
}

function primaryAction(kind: string) {
  switch (kind) {
    case "book":
    case "comic":
      return "Read";
    case "music":
      return "Listen";
    case "video":
    case "tv":
      return "Watch";
    default:
      return "Play";
  }
}
