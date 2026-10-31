import type { CatalogTitle } from "../types/catalog";

const ARTIST_PREFIX = "artist:";

export type MusicShelf = "albums" | "artists" | "songs";

export function isArtistId(id: string) {
  return id.startsWith(ARTIST_PREFIX);
}

export function isAlbum(title: CatalogTitle) {
  if (title.kind !== "music" || isArtistId(title.id)) return false;
  if (title.album) return true;
  return (title.trackCount ?? 0) > 1;
}

export function isSong(title: CatalogTitle) {
  return title.kind === "music" && !isArtistId(title.id) && !isAlbum(title);
}

export function artistName(title: CatalogTitle) {
  return title.creators?.find((name) => name.trim())?.trim() ?? "";
}

export function artistIdFor(name: string) {
  return `${ARTIST_PREFIX}${encodeURIComponent(name.toLowerCase())}`;
}

export function musicEntries(titles: CatalogTitle[], sectionId: string) {
  if (sectionId === "albums") return titles.filter(isAlbum);
  if (sectionId === "songs") return titles.filter(isSong);
  if (sectionId === "artists") return artistTiles(titles);
  return titles;
}

export function musicCount(titles: CatalogTitle[], shelf: MusicShelf) {
  if (shelf === "albums") return titles.filter(isAlbum).length;
  if (shelf === "songs") return titles.filter(isSong).length;
  return artistTiles(titles).length;
}

export function artistTiles(titles: CatalogTitle[]) {
  const groups = new Map<string, CatalogTitle[]>();
  for (const title of titles) {
    if (title.kind !== "music" || isArtistId(title.id)) continue;
    const name = artistName(title);
    if (!name) continue;
    const key = name.toLowerCase();
    const list = groups.get(key) ?? [];
    list.push(title);
    groups.set(key, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map(([, works]) => artistTile(works));
}

export function artistFromLibrary(titles: CatalogTitle[], artistId: string) {
  let key = artistId.slice(ARTIST_PREFIX.length);
  try {
    key = decodeURIComponent(key);
  } catch {
    /* keep the raw key */
  }
  const works = titles.filter(
    (title) => title.kind === "music" && artistName(title).toLowerCase() === key,
  );
  return works.length ? artistTile(works) : null;
}

export function worksForArtist(titles: CatalogTitle[], artistId: string) {
  let key = artistId.slice(ARTIST_PREFIX.length);
  try {
    key = decodeURIComponent(key);
  } catch {
    /* keep the raw key */
  }
  const works = titles.filter(
    (title) => title.kind === "music" && artistName(title).toLowerCase() === key,
  );
  return {
    albums: works.filter(isAlbum),
    songs: works.filter(isSong),
  };
}

function artistTile(works: CatalogTitle[]): CatalogTitle {
  const name = artistName(works[0]);
  const albums = works.filter(isAlbum);
  const songs = works.filter(isSong);
  const lead = albums[0] ?? songs[0] ?? works[0];
  return {
    id: artistIdFor(name),
    title: name,
    subtitle: artistSubtitle(albums.length, songs.length),
    kind: "music",
    aspect: "square",
    accentHue: lead.accentHue,
    coverPath: works.find((title) => title.coverPath)?.coverPath ?? null,
    canLaunch: false,
    creators: [name],
    addedAt: Math.max(0, ...works.map((title) => title.addedAt ?? 0)) || null,
  };
}

function artistSubtitle(albums: number, songs: number) {
  const albumLabel = albums === 1 ? "1 album" : albums > 1 ? `${albums} albums` : "";
  const songLabel = songs === 1 ? "1 song" : songs > 1 ? `${songs} songs` : "";
  if (albumLabel && songLabel) return `${albumLabel} · ${songLabel}`;
  return albumLabel || songLabel || "Artist";
}

export function musicHomeSubtitle(titles: CatalogTitle[]) {
  const albums = titles.filter(isAlbum).length;
  const artists = artistTiles(titles).length;
  const songs = titles.filter(isSong).length;
  const parts = [
    albums > 0 ? (albums === 1 ? "1 album" : `${albums} albums`) : null,
    artists > 0 ? (artists === 1 ? "1 artist" : `${artists} artists`) : null,
    songs > 0 ? (songs === 1 ? "1 song" : `${songs} songs`) : null,
  ].filter((part): part is string => !!part);
  if (parts.length > 0) return parts.join(" · ");
  return "Albums, artists, and songs";
}
