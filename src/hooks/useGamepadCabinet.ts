import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { scanLibrary } from "../lib/kabin-api";

const DEADZONE = 0.45;
const REPEAT_MS = 280;

/** Standard mapping: A=0, B=1, Start=9, Guide=16 (when present). */
export function useGamepadCabinet(searchInputRef?: React.RefObject<HTMLInputElement | null>) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const queryClient = useQueryClient();
  const held = useRef<Record<number, number>>({});

  useEffect(() => {
    let frame = 0;
    const poll = () => {
      const pads = navigator.getGamepads?.() ?? [];
      for (const pad of pads) {
        if (!pad) continue;
        const now = performance.now();
        const press = (index: number, action: () => void) => {
          const down = pad.buttons[index]?.pressed;
          if (!down) {
            delete held.current[index];
            return;
          }
          const last = held.current[index] ?? 0;
          if (now - last >= REPEAT_MS) {
            held.current[index] = now;
            action();
          }
        };

        press(1, () => {
          if (pathname !== "/") window.history.back();
        });
        press(9, () => {
          void navigate({ to: "/settings" });
        });
        press(16, () => {
          void queryClient.fetchQuery({
            queryKey: ["libraryScan"],
            queryFn: () => scanLibrary(true),
          });
          void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
        });
        press(0, () => {
          const active = document.activeElement;
          if (active instanceof HTMLElement && active !== document.body) {
            active.click();
            return;
          }
          const link = document.querySelector<HTMLElement>("main a[href], main button");
          link?.click();
        });
        const ax = pad.axes[0] ?? 0;
        const ay = pad.axes[1] ?? 0;
        if (Math.abs(ax) > DEADZONE || Math.abs(ay) > DEADZONE) {
          const tiles = Array.from(
            document.querySelectorAll<HTMLElement>("[data-cabinet-tile]"),
          );
          if (tiles.length > 0) {
            const current = document.activeElement as HTMLElement | null;
            let index = tiles.findIndex((el) => el === current);
            if (index < 0) index = 0;
            if (Math.abs(ax) > Math.abs(ay)) {
              index = ax > 0 ? Math.min(tiles.length - 1, index + 1) : Math.max(0, index - 1);
            } else {
              index = ay > 0 ? Math.min(tiles.length - 1, index + 1) : Math.max(0, index - 1);
            }
            tiles[index]?.focus();
          }
        }
      }
      frame = requestAnimationFrame(poll);
    };
    frame = requestAnimationFrame(poll);
    return () => cancelAnimationFrame(frame);
  }, [navigate, pathname, queryClient, searchInputRef]);
}
