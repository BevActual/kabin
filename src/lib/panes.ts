import {
  Bookmark,
  Cpu,
  Download,
  Folder,
  Info,
  Library,
  Palette,
  Settings,
  Share2,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

export type PaneId = "library" | "downloads" | "settings";

export type PaneSection = {
  id: string;
  label: string;
  icon: LucideIcon;
};

export const downloadSections: PaneSection[] = [
  { id: "activity", label: "Activity", icon: Download },
  { id: "wanted", label: "Wanted", icon: Bookmark },
];

export const settingsSections: PaneSection[] = [
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "libraries", label: "Libraries", icon: Library },
  { id: "folders", label: "Folders", icon: Folder },
  { id: "downloads", label: "Downloads", icon: Download },
  { id: "sharing", label: "Sharing", icon: Share2 },
  { id: "play", label: "Play", icon: SlidersHorizontal },
  { id: "emulation", label: "Emulation", icon: Cpu },
  { id: "about", label: "About", icon: Info },
];

export function paneFromPath(pathname: string): PaneId {
  if (pathname === "/downloads" || pathname.startsWith("/downloads/")) return "downloads";
  if (pathname === "/settings" || pathname.startsWith("/settings/")) return "settings";
  return "library";
}

export function paneTitle(pane: PaneId) {
  if (pane === "downloads") return "Downloads";
  if (pane === "settings") return "Settings";
  return "";
}

export function paneHue(pane: PaneId) {
  if (pane === "downloads") return 200;
  if (pane === "settings") return 250;
  return null;
}

export function sectionFromHash(sections: PaneSection[], hash: string) {
  return sections.find((section) => section.id === hash) ?? sections[0];
}

export const settingsIcon = Settings;
