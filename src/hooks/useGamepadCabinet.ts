import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { navigateCabinetTiles } from "../lib/cabinetFocus";
import { scanLibrary } from "../lib/kabin-api";
import { isModeHome } from "../lib/modes";

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
          if (pathname !== "/" && !isModeHome(pathname)) window.history.back();
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
          if (Math.abs(ax) > Math.abs(ay)) {
            navigateCabinetTiles(ax > 0 ? "right" : "left");
          } else {
            navigateCabinetTiles(ay > 0 ? "down" : "up");
          }
        }
      }
      frame = requestAnimationFrame(poll);
    };
    frame = requestAnimationFrame(poll);
    return () => cancelAnimationFrame(frame);
  }, [navigate, pathname, queryClient, searchInputRef]);
}
