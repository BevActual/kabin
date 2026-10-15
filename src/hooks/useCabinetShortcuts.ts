import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { useUiStore } from "../store/ui";

export function useCabinetShortcuts(searchInputRef?: React.RefObject<HTMLInputElement | null>) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
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
      if (e.key === "," && e.ctrlKey) {
        e.preventDefault();
        void navigate({ to: "/settings" });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, pathname, searchInputRef, setSearchQuery]);
}
