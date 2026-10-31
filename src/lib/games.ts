import type { CatalogTitle } from "../types/catalog";

export type GameSource = "steam" | "installed" | "console";

export function gameSource(title: CatalogTitle): GameSource | null {
  if (title.kind !== "game") return null;
  const id = nestedId(title.id);
  if (id.startsWith("steam:") || title.subtitle === "Steam") return "steam";
  if (id.startsWith("desktop:") || title.subtitle === "Installed App" || title.subtitle === "Installed") {
    return "installed";
  }
  if (id.startsWith("roms:")) return "console";
  return null;
}

function nestedId(id: string) {
  if (!id.startsWith("remote:")) return id;
  const parts = id.split(":");
  return parts.slice(2).join(":");
}

export function gamesInSection(titles: CatalogTitle[], sectionId: string) {
  if (sectionId === "steam" || sectionId === "installed") {
    return titles.filter((title) => gameSource(title) === sectionId);
  }
  if (sectionId === "consoles") {
    return titles.filter((title) => gameSource(title) === "console");
  }
  if (sectionId === "played") {
    return titles.filter((title) => (title.recentAt ?? 0) > 0);
  }
  return titles;
}

export function consoleGroups(titles: CatalogTitle[]) {
  const map = new Map<string, CatalogTitle[]>();
  for (const title of titles) {
    const name = title.subtitle.trim() || "Consoles";
    const list = map.get(name) ?? [];
    list.push(title);
    map.set(name, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map(([name, games]) => ({ name, titles: games }));
}

export function gameHomeSubtitle(titles: CatalogTitle[]) {
  const steam = titles.filter((title) => gameSource(title) === "steam").length;
  const installed = titles.filter((title) => gameSource(title) === "installed").length;
  const consoles = titles.filter((title) => gameSource(title) === "console").length;
  const parts = [
    steam > 0 ? (steam === 1 ? "1 on Steam" : `${steam} on Steam`) : null,
    installed > 0 ? (installed === 1 ? "1 installed" : `${installed} installed`) : null,
    consoles > 0 ? (consoles === 1 ? "1 console game" : `${consoles} console games`) : null,
  ].filter((part): part is string => !!part);
  if (parts.length > 0) return parts.join(" · ");
  return "Steam, installed apps, and consoles";
}
