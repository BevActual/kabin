import type { CatalogTitle } from "../types/catalog";

const SERIES_PREFIX = "series:";
const VOLUME_KINDS = new Set(["book", "audiobook", "comic", "pdf"]);

export function isVolumeKind(kind: string) {
  return VOLUME_KINDS.has(kind);
}

export function isSeriesId(id: string) {
  return id.startsWith(SERIES_PREFIX);
}

/** Kind plus series name, so a book series and a comic series can share a title. */
export function seriesKey(title: CatalogTitle) {
  if (!isVolumeKind(title.kind) || isSeriesId(title.id)) return null;
  const named = title.series?.trim();
  if (!named) return null;
  return `${title.kind}:${named.toLowerCase()}`;
}

export function seriesIdFor(title: CatalogTitle) {
  const key = seriesKey(title);
  if (!key) return null;
  const split = key.indexOf(":");
  const kind = key.slice(0, split);
  const name = key.slice(split + 1);
  return `${SERIES_PREFIX}${kind}:${encodeURIComponent(name)}`;
}

export function seriesTiles(titles: CatalogTitle[]) {
  return groupedVolumes(titles).map((volumes) => seriesTile(volumes));
}

export function seriesFromLibrary(titles: CatalogTitle[], seriesId: string) {
  const volumes = volumesForSeries(titles, seriesId);
  return volumes.length >= 2 ? seriesTile(volumes) : null;
}

export function volumesForSeries(titles: CatalogTitle[], seriesId: string) {
  const key = keyFromSeriesId(seriesId);
  if (!key) return [];
  return sortVolumes(titles.filter((title) => seriesKey(title) === key));
}

/** Replace a run of two or more volumes with one series tile. A single volume stays itself. */
export function collapseSeries(titles: CatalogTitle[]) {
  const groups = new Map<string, CatalogTitle[]>();
  for (const title of titles) {
    const key = seriesKey(title);
    if (!key) continue;
    const list = groups.get(key) ?? [];
    list.push(title);
    groups.set(key, list);
  }
  const multi = new Set(
    [...groups.entries()].filter(([, list]) => list.length >= 2).map(([key]) => key),
  );
  const seen = new Set<string>();
  const out: CatalogTitle[] = [];
  for (const title of titles) {
    const key = seriesKey(title);
    if (!key || !multi.has(key)) {
      out.push(title);
      continue;
    }
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(seriesTile(groups.get(key) ?? [title]));
  }
  return out;
}

export function presentSeries(titles: CatalogTitle[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return titles;
  const grouped = new Set<string>();
  for (const title of titles) {
    const key = seriesKey(title);
    if (key && (title.series ?? "").toLowerCase().includes(needle)) grouped.add(key);
  }
  const counts = new Map<string, number>();
  for (const title of titles) {
    const key = seriesKey(title);
    if (key && grouped.has(key)) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const seen = new Set<string>();
  const out: CatalogTitle[] = [];
  for (const title of titles) {
    const key = seriesKey(title);
    if (key && grouped.has(key) && (counts.get(key) ?? 0) >= 2) {
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(seriesTile(titles.filter((item) => seriesKey(item) === key)));
      continue;
    }
    out.push(title);
  }
  return out;
}

export function nextVolume(volumes: CatalogTitle[], currentId: string) {
  const ordered = sortVolumes(volumes);
  const index = ordered.findIndex((volume) => volume.id === currentId);
  const after = index >= 0 ? ordered.slice(index + 1) : ordered;
  return after.find((volume) => (volume.progress ?? 0) < 0.98) ?? null;
}

export function resumeVolume(volumes: CatalogTitle[]) {
  const ordered = sortVolumes(volumes);
  return (
    ordered.find((volume) => {
      const progress = volume.progress ?? 0;
      return progress > 0.01 && progress < 0.98;
    }) ??
    ordered.find((volume) => (volume.progress ?? 0) < 0.98) ??
    ordered[0] ??
    null
  );
}

export function volumeLabel(title: CatalogTitle) {
  const index = title.seriesIndex;
  if (index != null && index > 0 && index < 1000) {
    const whole = Math.round(index);
    if (Math.abs(index - whole) < 0.001) return `Vol. ${whole}`;
  }
  return title.subtitle;
}

export function volumeProgressLabel(volume: CatalogTitle) {
  const progress = volume.progress ?? 0;
  if (progress >= 0.98) return volume.kind === "audiobook" ? "Finished" : "Read";
  if (progress > 0.02) return `${Math.round(progress * 100)}%`;
  return "";
}

export function sortVolumes(volumes: CatalogTitle[]) {
  return [...volumes].sort((a, b) => {
    const ai = a.seriesIndex ?? Number.MAX_SAFE_INTEGER;
    const bi = b.seriesIndex ?? Number.MAX_SAFE_INTEGER;
    if (ai !== bi) return ai - bi;
    return a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
  });
}

export function booksHomeSubtitle(titles: CatalogTitle[]) {
  const books = titles.filter((title) => title.kind === "book").length;
  const audiobooks = titles.filter((title) => title.kind === "audiobook").length;
  const comics = titles.filter((title) => title.kind === "comic").length;
  const pdfs = titles.filter((title) => title.kind === "pdf").length;
  const series = seriesTiles(titles).length;
  const parts = [
    books > 0 ? (books === 1 ? "1 book" : `${books} books`) : null,
    audiobooks > 0 ? (audiobooks === 1 ? "1 audiobook" : `${audiobooks} audiobooks`) : null,
    comics > 0 ? (comics === 1 ? "1 comic" : `${comics} comics`) : null,
    pdfs > 0 ? (pdfs === 1 ? "1 PDF" : `${pdfs} PDFs`) : null,
    series > 0 ? (series === 1 ? "1 series" : `${series} series`) : null,
  ].filter((part): part is string => !!part);
  if (parts.length > 0) return parts.join(" · ");
  return "Books, audiobooks, comics, and PDFs";
}

function groupedVolumes(titles: CatalogTitle[]) {
  const groups = new Map<string, CatalogTitle[]>();
  for (const title of titles) {
    const key = seriesKey(title);
    if (!key) continue;
    const list = groups.get(key) ?? [];
    list.push(title);
    groups.set(key, list);
  }
  return [...groups.entries()]
    .filter(([, volumes]) => volumes.length >= 2)
    .sort(([a], [b]) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map(([, volumes]) => volumes);
}

function seriesTile(volumes: CatalogTitle[]): CatalogTitle {
  const ordered = sortVolumes(volumes);
  const first = ordered[0];
  const name = first.series?.trim() || first.title;
  const read = ordered.reduce(
    (sum, volume) => sum + Math.min(1, Math.max(0, volume.progress ?? 0)),
    0,
  );
  const ratio = ordered.length ? read / ordered.length : 0;
  const addedAt = Math.max(0, ...ordered.map((volume) => volume.addedAt ?? 0));
  const recentAt = Math.max(0, ...ordered.map((volume) => volume.recentAt ?? 0));
  return {
    id: seriesIdFor(first) ?? `${SERIES_PREFIX}${first.kind}:${encodeURIComponent(name.toLowerCase())}`,
    title: name,
    subtitle: volumeCountLabel(first.kind, ordered.length),
    kind: first.kind,
    aspect: first.aspect,
    progress: ratio > 0 ? ratio : null,
    accentHue: first.accentHue ?? 38,
    coverPath: ordered.find((volume) => volume.coverPath)?.coverPath ?? null,
    canLaunch: false,
    addedAt: addedAt > 0 ? addedAt : null,
    recentAt: recentAt > 0 ? recentAt : null,
    series: name,
  };
}

function volumeCountLabel(kind: string, count: number) {
  if (kind === "comic") return count === 1 ? "1 volume" : `${count} volumes`;
  if (kind === "audiobook") return count === 1 ? "1 audiobook" : `${count} audiobooks`;
  if (kind === "pdf") return count === 1 ? "1 PDF" : `${count} PDFs`;
  return count === 1 ? "1 book" : `${count} books`;
}

function keyFromSeriesId(seriesId: string) {
  if (!isSeriesId(seriesId)) return null;
  const rest = seriesId.slice(SERIES_PREFIX.length);
  const split = rest.indexOf(":");
  if (split <= 0) return null;
  const kind = rest.slice(0, split);
  let name = rest.slice(split + 1);
  try {
    name = decodeURIComponent(name);
  } catch {
    /* keep the raw name */
  }
  return `${kind}:${name}`;
}
