import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useUiStore } from "../store/ui";

export function OpenLastMode() {
  const navigate = useNavigate();
  const mode = useUiStore((s) => s.contentMode);

  useEffect(() => {
    void navigate({
      to: "/browse/$mode",
      params: { mode },
      replace: true,
    });
  }, [mode, navigate]);

  return null;
}
