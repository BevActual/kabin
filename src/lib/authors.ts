import type { CatalogTitle } from "../types/catalog";

const AUTHOR_PREFIX = "author:";
const WORK_KINDS = new Set(["book", "audiobook", "comic", "pdf"]);

export function isAuthorId(id: string) {
  return id.startsWith(AUTHOR_PREFIX);
}

export function authorNames(title: CatalogTitle) {
  if (!WORK_KINDS.has(title.kind) || isAuthorId(title.id)) return [];
  const seen = new Set<string>();
  const names: string[] = [];
  for (const raw of title.creators ?? []) {
    const name = raw.trim();
    const key = name.toLowerCase();
    if (!name || seen.has(key)) continue;
    seen.add(key);
    names.push(name);
  }
  return names;
}

export function authorIdFor(name: string) {
  return `${AUTHOR_PREFIX}${encodeURIComponent(name.toLowerCase())}`;
}

export function authorTiles(titles: CatalogTitle[]) {
  const groups = new Map<string, { name: string; works: CatalogTitle[] }>();
  for (const title of titles) {
    for (const name of authorNames(title)) {
      const key = name.toLowerCase();
      const group = groups.get(key) ?? { name, works: [] };
      if (!group.works.some((work) => work.id === title.id)) group.works.push(title);
      groups.set(key, group);
    }
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map(([, group]) => authorTile(group.name, group.works));
}

export function authorFromLibrary(titles: CatalogTitle[], authorId: string) {
  const key = keyFromAuthorId(authorId);
  if (!key) return null;
  const works = titles.filter((title) =>
    authorNames(title).some((name) => name.toLowerCase() === key),
  );
  if (!works.length) return null;
  const name =
    authorNames(works[0]).find((entry) => entry.toLowerCase() === key) ?? works[0].title;
  return authorTile(name, works);
}

export function worksForAuthor(titles: CatalogTitle[], authorId: string) {
  const key = keyFromAuthorId(authorId);
  const works = key
    ? titles.filter((title) => authorNames(title).some((name) => name.toLowerCase() === key))
    : [];
  return {
    books: works.filter((title) => title.kind === "book"),
    audiobooks: works.filter((title) => title.kind === "audiobook"),
    comics: works.filter((title) => title.kind === "comic"),
    pdfs: works.filter((title) => title.kind === "pdf"),
  };
}

/** The author shared by every volume, when the series has one. */
export function sharedAuthor(titles: CatalogTitle[]) {
  if (!titles.length) return "";
  const first = authorNames(titles[0])[0];
  if (!first) return "";
  const key = first.toLowerCase();
  const same = titles.every((title) => authorNames(title)[0]?.toLowerCase() === key);
  return same ? first : "";
}

export function presentAuthors(titles: CatalogTitle[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return titles;
  const grouped = new Set<string>();
  for (const title of titles) {
    for (const name of authorNames(title)) {
      if (name.toLowerCase().includes(needle)) grouped.add(name.toLowerCase());
    }
  }
  const seen = new Set<string>();
  const out: CatalogTitle[] = [];
  for (const title of titles) {
    const match = authorNames(title).find((name) => grouped.has(name.toLowerCase()));
    if (!match) {
      out.push(title);
      continue;
    }
    const key = match.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const works = titles.filter((item) =>
      authorNames(item).some((name) => name.toLowerCase() === key),
    );
    out.push(authorTile(match, works));
  }
  return out;
}

function authorTile(name: string, works: CatalogTitle[]): CatalogTitle {
  const lead = works.find((title) => title.kind === "book") ?? works[0];
  const addedAt = Math.max(0, ...works.map((title) => title.addedAt ?? 0));
  return {
    id: authorIdFor(name),
    title: name,
    subtitle: authorSubtitle(works),
    kind: lead.kind,
    aspect: lead.kind === "audiobook" && works.every((title) => title.kind === "audiobook")
      ? "square"
      : "poster",
    accentHue: lead.accentHue,
    coverPath: works.find((title) => title.coverPath)?.coverPath ?? null,
    canLaunch: false,
    creators: [name],
    addedAt: addedAt > 0 ? addedAt : null,
  };
}

function authorSubtitle(works: CatalogTitle[]) {
  const parts = [
    countLabel(works.filter((title) => title.kind === "book").length, "book", "books"),
    countLabel(works.filter((title) => title.kind === "audiobook").length, "audiobook", "audiobooks"),
    countLabel(works.filter((title) => title.kind === "comic").length, "comic", "comics"),
    countLabel(works.filter((title) => title.kind === "pdf").length, "PDF", "PDFs"),
  ].filter((part): part is string => !!part);
  return parts.join(" · ") || "Author";
}

function countLabel(count: number, one: string, many: string) {
  if (count === 1) return `1 ${one}`;
  if (count > 1) return `${count} ${many}`;
  return "";
}

function keyFromAuthorId(authorId: string) {
  if (!isAuthorId(authorId)) return null;
  let key = authorId.slice(AUTHOR_PREFIX.length);
  try {
    key = decodeURIComponent(key);
  } catch {
    /* keep the raw key */
  }
  return key;
}
