export type FocusDirection = "left" | "right" | "up" | "down";

function cabinetTiles(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>("[data-cabinet-tile]"));
}

function center(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

export function navigateCabinetTiles(direction: FocusDirection): boolean {
  const tiles = cabinetTiles();
  if (tiles.length === 0) return false;

  const active = document.activeElement as HTMLElement | null;
  let index = active ? tiles.indexOf(active) : -1;
  if (index < 0) {
    tiles[0]?.focus();
    return true;
  }

  const origin = center(tiles[index]);
  let best = -1;
  let bestScore = Number.POSITIVE_INFINITY;

  for (let i = 0; i < tiles.length; i += 1) {
    if (i === index) continue;
    const point = center(tiles[i]);
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    let ok = false;
    let primary = 0;
    let secondary = 0;
    switch (direction) {
      case "left":
        ok = dx < -8;
        primary = -dx;
        secondary = Math.abs(dy);
        break;
      case "right":
        ok = dx > 8;
        primary = dx;
        secondary = Math.abs(dy);
        break;
      case "up":
        ok = dy < -8;
        primary = -dy;
        secondary = Math.abs(dx);
        break;
      case "down":
        ok = dy > 8;
        primary = dy;
        secondary = Math.abs(dx);
        break;
    }
    if (!ok) continue;
    const score = primary * 1000 + secondary;
    if (score < bestScore) {
      bestScore = score;
      best = i;
    }
  }

  if (best < 0) return false;
  tiles[best]?.focus();
  return true;
}
