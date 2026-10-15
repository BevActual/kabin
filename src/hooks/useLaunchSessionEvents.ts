import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { useUiStore } from "../store/ui";

export type GameSessionFinished = {
  gameId: string;
  title: string;
  elapsedSeconds: number;
  recordedSeconds: number;
  exitCode: number | null;
  message: string | null;
};

export function useLaunchSessionEvents() {
  const queryClient = useQueryClient();
  const setToast = useUiStore((s) => s.setToast);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("__TAURI_INTERNALS__" in window || "__TAURI__" in window)
    ) {
      return;
    }
    let unlisten: (() => void) | undefined;
    void listen<GameSessionFinished>("game-session-finished", (event) => {
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
      void queryClient.invalidateQueries({ queryKey: ["title"] });
      const msg = event.payload.message;
      if (msg) {
        setToast(msg);
      }
    }).then((fn) => {
      unlisten = fn;
    });
    return () => {
      unlisten?.();
    };
  }, [queryClient, setToast]);
}
