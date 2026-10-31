import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { navigateCabinetTiles } from "../lib/cabinetFocus";
import { useUiStore } from "../store/ui";

export function useCabinetShortcuts(searchInputRef?: React.RefObject<HTMLInputElement | null>) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const previewTitleId = useUiStore((s) => s.previewTitleId);
  const setPreviewTitleId = useUiStore((s) => s.setPreviewTitleId);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (previewTitleId && (e.key === "Escape" || e.code === "Space")) {
        e.preventDefault();
        const returnId = previewTitleId;
        setPreviewTitleId(null);
        document
          .querySelector<HTMLElement>(`[data-title-id="${CSS.escape(returnId)}"]`)
          ?.focus();
        return;
      }
      if (previewTitleId) return;
      if (e.code === "Space") {
        const tile = document.activeElement?.closest("[data-cabinet-tile]");
        const titleId = tile instanceof HTMLElement ? tile.dataset.titleId : undefined;
        if (titleId) {
          e.preventDefault();
          setPreviewTitleId(titleId);
        }
        return;
      }
      if (e.key === "Escape") {
        if (pathname !== "/") {
          e.preventDefault();
          window.history.back();
        } else {
          setSearchQuery("");
        }
        return;
      }
      if (e.key === "/" || (e.key === "f" && e.ctrlKey)) {
        e.preventDefault();
        searchInputRef?.current?.focus();
        return;
      }
      if (e.key === "," && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        void navigate({ to: "/settings" });
        return;
      }
      if (e.key === "\\" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        toggleSidebar();
        return;
      }
      if (e.key === "ArrowLeft" && navigateCabinetTiles("left")) {
        e.preventDefault();
        return;
      }
      if (e.key === "ArrowRight" && navigateCabinetTiles("right")) {
        e.preventDefault();
        return;
      }
      if (e.key === "ArrowUp" && navigateCabinetTiles("up")) {
        e.preventDefault();
        return;
      }
      if (e.key === "ArrowDown" && navigateCabinetTiles("down")) {
        e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    navigate,
    pathname,
    previewTitleId,
    searchInputRef,
    setPreviewTitleId,
    setSearchQuery,
    toggleSidebar,
  ]);
}
