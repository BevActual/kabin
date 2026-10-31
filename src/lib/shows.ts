import type { CatalogTitle } from "../types/catalog";

const SHOW_PREFIX = "show:";

export function isShowId(id: string) {
  return id.startsWith(SHOW_PREFIX);
}

export function isUnwatched(title: CatalogTitle) {
  return (title.progress ?? 0) < 0.02;
}

export function showKey(title: CatalogTitle) {
  if (title.kind !== "tv" || isShowId(title.id)) return null;
  const named = title.series?.trim();
  if (named) return named.toLowerCase();
  return parseEpisode(title.title)?.series.toLowerCase() ?? null;
}

export function seriesLabel(title: CatalogTitle) {
  const named = title.series?.trim();
  if (named) return named;
  return parseEpisode(title.title)?.series ?? title.title;
}

/** Turn episode files that share a show name into one tile. */
export function collapseShows(titles: CatalogTitle[]) {
  const groups = new Map<string, CatalogTitle[]>();
  for (const title of titles) {
    const key = showKey(title);
    if (!key) continue;
    const list = groups.get(key) ?? [];
    list.push(title);
    groups.set(key, list);
  }
  const seen = new Set<string>();
  const out: CatalogTitle[] = [];
  for (const title of titles) {
    const key = showKey(title);
    if (!key) {
      out.push(title);
      continue;
    }
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(showTile(groups.get(key) ?? [title]));
  }
  return out;
}

export function libraryEntries(titles: CatalogTitle[], sectionId: string) {
  const presented = sectionId === "favorites" ? titles : collapseShows(titles);
  if (sectionId === "unwatched") return presented.filter(isUnwatched);
  if (sectionId === "progress") return presented.filter(isInProgress);
  return presented;
}

function isInProgress(title: CatalogTitle) {
  const progress = title.progress ?? 0;
  return progress > 0.01 && progress < 0.98;
}

export function episodesForShow(titles: CatalogTitle[], showId: string) {
  if (!isShowId(showId)) return [];
  let key = showId.slice(SHOW_PREFIX.length);
  try {
    key = decodeURIComponent(key);
  } catch {
    /* keep the raw key */
  }
  return sortEpisodes(titles.filter((title) => showKey(title) === key));
}

export function showTile(episodes: CatalogTitle[]): CatalogTitle {
  const ordered = sortEpisodes(episodes);
  const first = ordered[0];
  const series = seriesLabel(first);
  const key = series.toLowerCase();
  const watched = ordered.reduce(
    (sum, episode) => sum + Math.min(1, Math.max(0, episode.progress ?? 0)),
    0,
  );
  const ratio = ordered.length ? watched / ordered.length : 0;
  const addedAt = Math.max(0, ...ordered.map((episode) => episode.addedAt ?? 0));
  const recentAt = Math.max(0, ...ordered.map((episode) => episode.recentAt ?? 0));
  return {
    id: `${SHOW_PREFIX}${encodeURIComponent(key)}`,
    title: series,
    subtitle: ordered.length === 1 ? "1 episode" : `${ordered.length} episodes`,
    kind: "tv",
    aspect: "widescreen",
    progress: ratio > 0 ? ratio : null,
    accentHue: first?.accentHue ?? 210,
    coverPath: ordered.find((episode) => episode.coverPath)?.coverPath ?? null,
    canLaunch: false,
    addedAt: addedAt > 0 ? addedAt : null,
    recentAt: recentAt > 0 ? recentAt : null,
    series,
  };
}

export function showIdFor(title: CatalogTitle) {
  const key = showKey(title);
  if (!key) return null;
  return `${SHOW_PREFIX}${encodeURIComponent(key)}`;
}

export function nextEpisode(episodes: CatalogTitle[], currentId: string) {
  const ordered = sortEpisodes(episodes);
  const index = ordered.findIndex((episode) => episode.id === currentId);
  const after = index >= 0 ? ordered.slice(index + 1) : ordered;
  return after.find((episode) => (episode.progress ?? 0) < 0.98) ?? null;
}

export function presentSearch(titles: CatalogTitle[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return titles;
  const grouped = new Set<string>();
  for (const title of titles) {
    const key = showKey(title);
    if (key && seriesLabel(title).toLowerCase().includes(needle)) grouped.add(key);
  }
  const seen = new Set<string>();
  const out: CatalogTitle[] = [];
  for (const title of titles) {
    const key = showKey(title);
    if (key && grouped.has(key)) {
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(showTile(titles.filter((item) => showKey(item) === key)));
      continue;
    }
    out.push(title);
  }
  return out;
}

export function resumeEpisode(episodes: CatalogTitle[]) {
  const ordered = sortEpisodes(episodes);
  return (
    ordered.find((episode) => {
      const progress = episode.progress ?? 0;
      return progress > 0.01 && progress < 0.98;
    }) ??
    ordered.find((episode) => (episode.progress ?? 0) < 0.98) ??
    ordered[0] ??
    null
  );
}

export function sortEpisodes(episodes: CatalogTitle[]) {
  return [...episodes].sort((a, b) => {
    const ai = a.seriesIndex ?? Number.MAX_SAFE_INTEGER;
    const bi = b.seriesIndex ?? Number.MAX_SAFE_INTEGER;
    if (ai !== bi) return ai - bi;
    return a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
  });
}

export function episodeProgressLabel(episode: CatalogTitle) {
  const progress = episode.progress ?? 0;
  if (progress >= 0.98) return "Watched";
  if (progress > 0.02) return `${Math.round(progress * 100)}%`;
  return "";
}

type ParsedEpisode = { series: string; index: number };

function parseEpisode(title: string): ParsedEpisode | null {
  const normalized = title.replace(/\./g, " ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
  const seasonEpisode =
    /^(?<series>.+?)\s+[s](?<season>\d{1,2})\s*[e](?<episode>\d{1,3})\b/i.exec(normalized);
  const cross =
    /^(?<series>.+?)\s+(?<season>\d{1,2})x(?<episode>\d{1,3})\b/i.exec(normalized);
  const match = seasonEpisode ?? cross;
  if (!match?.groups) return null;
  const series = match.groups.series?.trim();
  const season = Number(match.groups.season);
  const episode = Number(match.groups.episode);
  if (!series || !episode || season > 99) return null;
  return { series, index: season * 1000 + episode };
}
