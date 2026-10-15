import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addMediaDir,
  getAppInfo,
  getSettings,
  pickFolder,
  setSourceEnabled,
} from "../lib/kabin-api";
import { useUiStore, type ThemeMode } from "../store/ui";

const SOURCE_ROWS: { key: string; label: string }[] = [
  { key: "steam", label: "Steam" },
  { key: "desktop", label: "Installed apps" },
  { key: "roms", label: "Console ROMs" },
  { key: "book", label: "Books" },
  { key: "comic", label: "Comics" },
  { key: "music", label: "Music" },
  { key: "video", label: "Movies" },
  { key: "tv", label: "TV" },
  { key: "remote", label: "Remote hosts" },
];

const MEDIA_KINDS = [
  { id: "book", label: "Books" },
  { id: "comic", label: "Comics" },
  { id: "music", label: "Music" },
  { id: "video", label: "Movies" },
  { id: "tv", label: "TV" },
];

export function SettingsView() {
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const queryClient = useQueryClient();
  const infoQuery = useQuery({ queryKey: ["appInfo"], queryFn: getAppInfo });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });

  const toggleSource = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      setSourceEnabled(key, enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
      void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
    },
  });

  const addFolder = useMutation({
    mutationFn: async (mediaType: string) => {
      const path = await pickFolder();
      if (!path) return;
      await addMediaDir(path, mediaType);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
    },
  });

  const settings = settingsQuery.data;
  const sources = settings?.sources ?? {};

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

      <SettingsGroup title="Sources">
        {SOURCE_ROWS.map(({ key, label }) => (
          <SettingsRow key={key} label={label}>
            <input
              type="checkbox"
              checked={Boolean(sources[key] ?? true)}
              onChange={(e) =>
                toggleSource.mutate({ key, enabled: e.target.checked })
              }
              className="h-4 w-4 accent-[var(--kabin-accent)]"
            />
          </SettingsRow>
        ))}
        <p className="px-4 pb-3 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Toggles are saved to your config and apply on the next library refresh.
        </p>
      </SettingsGroup>

      <SettingsGroup title="Media folders">
        {(settings?.mediaDirs ?? []).map((entry, index) => (
          <div key={index} className="kabin-grouped-row text-[calc(13px*var(--kabin-type-scale))]">
            <span className="text-kabin-secondary">
              {(entry as { mediaType?: string }).mediaType ?? "media"}
            </span>
            <span className="max-w-[240px] truncate font-mono text-kabin-primary">
              {(entry as { path?: string }).path ?? ""}
            </span>
          </div>
        ))}
        <div className="flex flex-wrap gap-2 p-4 pt-2">
          {MEDIA_KINDS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => addFolder.mutate(id)}
              className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] font-medium text-white"
            >
              Add {label} folder…
            </button>
          ))}
        </div>
      </SettingsGroup>

      <SettingsGroup title="Console libraries">
        {(settings?.romDirs ?? []).length === 0 ? (
          <p className="px-4 py-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
            No ROM folders in config. Add them with the GTK app (Emulation Center)
            for now.
          </p>
        ) : (
          (settings?.romDirs ?? []).map((entry, index) => (
            <div key={index} className="kabin-grouped-row text-[calc(13px*var(--kabin-type-scale))]">
              <span className="text-kabin-secondary">
                {(entry as { system?: string }).system ?? "roms"}
              </span>
              <span className="max-w-[240px] truncate font-mono text-kabin-primary">
                {(entry as { path?: string }).path ?? ""}
              </span>
            </div>
          ))
        )}
      </SettingsGroup>

      <SettingsGroup title="About">
        <SettingsRow label="Version">
          <span className="text-kabin-secondary">
            {infoQuery.data?.version ?? "…"}
          </span>
        </SettingsRow>
        <SettingsRow label="Config">
          <span className="max-w-[220px] truncate font-mono text-[calc(12px*var(--kabin-type-scale))] text-kabin-secondary">
            {settings?.configPath ?? infoQuery.data?.configPath ?? "…"}
          </span>
        </SettingsRow>
        <p className="px-4 pb-3 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          See <span className="font-mono">docs/PARITY.md</span> for GTK-only features.
        </p>
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
