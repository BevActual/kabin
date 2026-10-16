import type { CatalogTitle } from "../types/catalog";

export function resumeTarget(title: CatalogTitle): {
  to: "/player/$titleId" | "/read/$titleId" | "/title/$titleId";
  params: { titleId: string };
} {
  const params = { titleId: title.id };
  if (
    (title.kind === "music" || title.kind === "video" || title.kind === "tv") &&
    title.canLaunch !== false
  ) {
    return { to: "/player/$titleId", params };
  }
  if (
    (title.kind === "book" || title.kind === "comic") &&
    title.canLaunch !== false
  ) {
    return { to: "/read/$titleId", params };
  }
  return { to: "/title/$titleId", params };
}

export function resumeActionLabel(kind: string) {
  switch (kind) {
    case "music":
      return "Listen";
    case "video":
    case "tv":
      return "Watch";
    case "book":
    case "comic":
      return "Read";
    default:
      return "Continue";
  }
}
