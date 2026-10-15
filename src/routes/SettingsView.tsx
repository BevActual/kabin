import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAppInfo } from "../lib/kabin-api";
import { useUiStore, type ThemeMode } from "../store/ui";

export function SettingsView() {
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const infoQuery = useQuery({
    queryKey: ["appInfo"],
    queryFn: getAppInfo,
  });

  return (
    <div className="mx-auto max-w-xl space-y-8">
      <SettingsGroup title="Appearance">
        <SettingsRow label="Theme">
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as ThemeMode)}
            className="rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-grouped px-3 py-1.5 text-kabin-primary"
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </SettingsRow>
      </SettingsGroup>

      <SettingsGroup title="Library">
        <SettingsRow label="Config file">
          <span className="max-w-[220px] truncate font-mono text-[calc(12px*var(--kabin-type-scale))] text-kabin-secondary">
            {infoQuery.data?.configPath ?? "…"}
          </span>
        </SettingsRow>
        <p className="px-4 pb-3 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Folder pickers and source toggles will match the legacy GTK Settings
          as commands are ported.
        </p>
      </SettingsGroup>

      <SettingsGroup title="About">
        <SettingsRow label="Version">
          <span className="text-kabin-secondary">
            {infoQuery.data?.version ?? "…"}
          </span>
        </SettingsRow>
        <SettingsRow label="Shell">
          <span className="text-kabin-secondary">Tauri · React · Rust</span>
        </SettingsRow>
      </SettingsGroup>
    </div>
  );
}

function SettingsGroup({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-2 px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
        {title}
      </h2>
      <div className="kabin-grouped">{children}</div>
    </section>
  );
}

function SettingsRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="kabin-grouped-row">
      <span className="text-[calc(15px*var(--kabin-type-scale))]">{label}</span>
      {children}
    </div>
  );
}
