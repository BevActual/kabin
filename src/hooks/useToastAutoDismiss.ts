import { useEffect } from "react";
import { useUiStore } from "../store/ui";

const TOAST_MS = 5200;

export function useToastAutoDismiss() {
  const toast = useUiStore((s) => s.toast);
  const setToast = useUiStore((s) => s.setToast);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(id);
  }, [toast, setToast]);
}
