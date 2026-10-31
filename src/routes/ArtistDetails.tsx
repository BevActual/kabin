import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MediaTile } from "../components/MediaTile";
import { getLibraryTitles } from "../lib/kabin-api";
import { artistFromLibrary, worksForArtist } from "../lib/music";

type Props = {
  artistId: string;
};

export function ArtistDetails({ artistId }: Props) {
  const query = useQuery({
    queryKey: ["library", "music"],
    queryFn: () => getLibraryTitles("music"),
  });
  const titles = query.data ?? [];
  const artist = artistFromLibrary(titles, artistId);
  const works = worksForArtist(titles, artistId);

  if (query.isLoading) {
    return <p className="text-kabin-secondary">Loading…</p>;
  }

  if (!artist) {
    return (
      <div>
        <p className="text-kabin-secondary">Artist not found.</p>
        <Link
          to="/browse/$mode/$section"
          params={{ mode: "music", section: "artists" }}
          className="mt-4 inline-block text-kabin-accent"
        >
          Back to Artists
        </Link>
      </div>
    );
  }

  return (
    <div>
      <p className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
        Music
      </p>
      <h1 className="mt-1 text-[calc(34px*var(--kabin-type-scale))] font-semibold tracking-tight">
        {artist.title}
      </h1>
      <p className="mt-1 text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
        {artist.subtitle}
      </p>
      {works.albums.length > 0 ? (
        <section className="mt-8">
          <h2 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
            Albums
          </h2>
          <div className="kabin-library-grid">
            {works.albums.map((album) => (
              <MediaTile key={album.id} title={album} />
            ))}
          </div>
        </section>
      ) : null}
      {works.songs.length > 0 ? (
        <section className="mt-8">
          <h2 className="mb-4 text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight">
            Songs
          </h2>
          <div className="kabin-library-grid">
            {works.songs.map((song) => (
              <MediaTile key={song.id} title={song} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
