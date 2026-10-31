import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { legacyLibraryTarget } from "../lib/modes";
import { useUiStore } from "../store/ui";

const route = getRouteApi("/library/$kind");

export function LibraryView() {
  const { kind } = route.useParams();
  const navigate = useNavigate();
  const contentMode = useUiStore((s) => s.contentMode);

  useEffect(() => {
    const target = legacyLibraryTarget(kind, contentMode);
    void navigate({
      to: "/browse/$mode/$section",
      params: target,
      replace: true,
    });
  }, [kind, contentMode, navigate]);

  return null;
}
