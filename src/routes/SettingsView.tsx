import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addMediaDir,
  addRomDir,
  addRomDirCustom,
  createHostPairingCode,
  discoverNearbyKabinHosts,
  getAppInfo,
  getHostStatus,
  getSettings,
  listEmulationPresets,
  listRemoteHosts,
  pairRemoteHost,
  removeRemoteHost,
  installManagedRuntime,
  listEmulators,
  listSystems,
  pickFolder,
  recommendedManagedRuntime,
  setEmulationPreset,
  setHostEnabled,
  setSourceEnabled,
  setSystemBiosPath,
  type EmulatorChoice,
  type SystemInfo,
} from "../lib/kabin-api";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { SegmentedControl } from "../components/SegmentedControl";
import { Switch } from "../components/Switch";
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
          <SegmentedControl
            label="Theme"
            value={theme}
            onChange={(value) => setTheme(value as ThemeMode)}
            options={[
              { id: "dark", label: "Dark" },
              { id: "light", label: "Light" },
            ]}
          />
        </SettingsRow>
      </SettingsGroup>

      <SettingsGroup title="Sources">
        {SOURCE_ROWS.map(({ key, label }) => (
          <SettingsRow key={key} label={label}>
            <Switch
              label={label}
              checked={Boolean(sources[key] ?? true)}
              disabled={toggleSource.isPending}
              onChange={(enabled) => toggleSource.mutate({ key, enabled })}
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
        {MEDIA_KINDS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => addFolder.mutate(id)}
            className="kabin-grouped-row w-full text-left text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary hover:bg-kabin-grouped"
          >
            <span>Add {label} folder</span>
            <ChevronRight size={16} strokeWidth={1.5} className="text-kabin-tertiary" />
          </button>
        ))}
      </SettingsGroup>

      <KabinHostPanel />

      <RemoteHostsPanel
        onChanged={() => {
          void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
          void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
        }}
      />

      <PlayDefaultsPanel
        emulation={settings?.emulation}
        controllers={settings?.connectedControllers ?? []}
        onChanged={() => {
          void queryClient.invalidateQueries({ queryKey: ["settings"] });
          void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
        }}
      />

      <EmulationCenterPanel
        romDirs={settings?.romDirs ?? []}
        biosPaths={settings?.biosPaths ?? {}}
        onAdded={() => {
          void queryClient.invalidateQueries({ queryKey: ["settings"] });
          void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
        }}
      />

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

function RemoteHostsPanel({ onChanged }: { onChanged: () => void }) {
  const savedQuery = useQuery({
    queryKey: ["remoteHosts"],
    queryFn: listRemoteHosts,
  });
  const discover = useMutation({
    mutationFn: discoverNearbyKabinHosts,
  });
  const [pairCode, setPairCode] = useState("");
  const [pairTarget, setPairTarget] = useState<string | null>(null);
  const pair = useMutation({
    mutationFn: ({
      host,
      code,
    }: {
      host: import("../lib/kabin-api").DiscoveredHost;
      code: string;
    }) => pairRemoteHost(host, code),
    onSuccess: () => {
      setPairCode("");
      setPairTarget(null);
      void savedQuery.refetch();
      onChanged();
    },
  });
  const remove = useMutation({
    mutationFn: (name: string) => removeRemoteHost(name),
    onSuccess: () => {
      void savedQuery.refetch();
      onChanged();
    },
  });

  const nearby = discover.data ?? [];

  return (
    <SettingsGroup title="Remote hosts">
      {(savedQuery.data ?? []).map((host) => (
        <div key={host.name} className="kabin-grouped-row text-[calc(13px*var(--kabin-type-scale))]">
          <div className="min-w-0 flex-1">
            <div className="text-kabin-primary">{host.name}</div>
            <div className="font-mono text-kabin-secondary">
              {host.address}:{host.port}
            </div>
          </div>
          <button
            type="button"
            onClick={() => remove.mutate(host.name)}
            className="text-kabin-accent"
          >
            Remove
          </button>
        </div>
      ))}
      <div className="space-y-3 p-4">
        <button
          type="button"
          disabled={discover.isPending}
          onClick={() => discover.mutate()}
          className="rounded-[var(--kabin-radius-control)] border border-kabin-separator px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary"
        >
          {discover.isPending ? "Searching…" : "Find Kabin hosts on LAN"}
        </button>
        {discover.isError ? (
          <p className="text-[calc(13px*var(--kabin-type-scale))] text-red-400">
            {discover.error instanceof Error
              ? discover.error.message
              : "Discovery failed"}
          </p>
        ) : null}
        {nearby.length === 0 && discover.isSuccess ? (
          <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
            No hosts found. Enable Kabin Host on another computer on this network.
          </p>
        ) : null}
        {nearby.map((host) => (
          <div
            key={`${host.address}:${host.port}`}
            className="rounded-[var(--kabin-radius-control)] border border-kabin-separator p-3"
          >
            <div className="font-medium text-kabin-primary">{host.name}</div>
            <div className="font-mono text-[calc(12px*var(--kabin-type-scale))] text-kabin-secondary">
              {host.address}:{host.port}
            </div>
            {pairTarget === host.name ? (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <input
                  value={pairCode}
                  onChange={(e) => setPairCode(e.target.value)}
                  placeholder="6-digit code"
                  className="w-32 rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-grouped px-2 py-1 font-mono"
                />
                <button
                  type="button"
                  disabled={pair.isPending}
                  onClick={() => pair.mutate({ host, code: pairCode })}
                  className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-3 py-1 text-white"
                >
                  Pair
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setPairTarget(host.name);
                  setPairCode("");
                }}
                className="mt-2 text-kabin-accent"
              >
                Pair…
              </button>
            )}
            {pair.isError && pairTarget === host.name ? (
              <p className="mt-1 text-[calc(12px*var(--kabin-type-scale))] text-red-400">
                {pair.error instanceof Error ? pair.error.message : "Pairing failed"}
              </p>
            ) : null}
          </div>
        ))}
        <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Paired libraries appear when the Remote hosts source is enabled. Remote
          game streaming needs kabin-media-helper on this machine.
        </p>
      </div>
    </SettingsGroup>
  );
}

function KabinHostPanel() {
  const queryClient = useQueryClient();
  const hostQuery = useQuery({
    queryKey: ["hostStatus"],
    queryFn: getHostStatus,
    refetchInterval: (query) =>
      query.state.data?.enabled ? 5000 : false,
  });
  const toggleHost = useMutation({
    mutationFn: (enabled: boolean) => setHostEnabled(enabled),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hostStatus"] });
    },
  });
  const pairing = useMutation({
    mutationFn: () => createHostPairingCode(300),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hostStatus"] });
    },
  });

  const host = hostQuery.data;
  const pairingCode = host?.pairingCode;

  return (
    <SettingsGroup title="Kabin Host">
      <SettingsRow label="Share this library">
        <input
          type="checkbox"
          checked={Boolean(host?.enabled)}
          disabled={toggleHost.isPending}
          onChange={(e) => toggleHost.mutate(e.target.checked)}
          className="h-4 w-4 accent-[var(--kabin-accent)]"
        />
      </SettingsRow>
      {host?.enabled ? (
        <>
          <SettingsRow label="Status">
            <span className="text-kabin-secondary">
              {host.error
                ? `Error · ${host.error}`
                : host.running
                  ? `Running on port ${host.port}`
                  : "Starting…"}
            </span>
          </SettingsRow>
          <SettingsRow label="Name">
            <span className="text-kabin-secondary">{host.hostName}</span>
          </SettingsRow>
          {host.fingerprint ? (
            <div className="kabin-grouped-row flex-col items-start gap-1">
              <span className="text-[calc(15px*var(--kabin-type-scale))]">
                TLS fingerprint
              </span>
              <span className="break-all font-mono text-[calc(11px*var(--kabin-type-scale))] text-kabin-secondary">
                {host.fingerprint}
              </span>
            </div>
          ) : null}
          <div className="space-y-2 p-4">
            <button
              type="button"
              disabled={!host.running || pairing.isPending}
              onClick={() => pairing.mutate()}
              className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] font-medium text-white disabled:opacity-40"
            >
              Generate pairing code
            </button>
            {pairingCode ? (
              <p className="text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary">
                Code:{" "}
                <span className="font-mono text-lg tracking-widest">
                  {pairingCode}
                </span>
                <span className="block text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
                  Enter on another device within 5 minutes.
                </span>
              </p>
            ) : null}
            {pairing.isError ? (
              <p className="text-[calc(13px*var(--kabin-type-scale))] text-red-400">
                {pairing.error instanceof Error
                  ? pairing.error.message
                  : "Could not create code"}
              </p>
            ) : null}
          </div>
        </>
      ) : (
        <p className="px-4 pb-3 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          TLS catalog API for paired Kabin apps. Game streaming uses
          kabin-media-helper when it is built on this machine.
        </p>
      )}
    </SettingsGroup>
  );
}

function PlayDefaultsPanel({
  emulation,
  controllers,
  onChanged,
}: {
  emulation?: Record<string, unknown>;
  controllers: string[];
  onChanged: () => void;
}) {
  const presetsQuery = useQuery({
    queryKey: ["emulationPresets"],
    queryFn: listEmulationPresets,
  });
  const presetId = (emulation?.preset as string | undefined) ?? "balanced";
  const setPreset = useMutation({
    mutationFn: (id: string) => setEmulationPreset(id),
    onSuccess: onChanged,
  });
  const current = presetsQuery.data?.find((p) => p.id === presetId);

  return (
    <SettingsGroup title="Play defaults">
      <div className="space-y-3 p-4">
        <label className="block text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
          Profile
          <select
            value={presetId}
            disabled={setPreset.isPending}
            onChange={(e) => setPreset.mutate(e.target.value)}
            className="mt-1 w-full rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-grouped px-3 py-2 text-kabin-primary"
          >
            {(presetsQuery.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {current ? (
          <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
            {current.description}
          </p>
        ) : null}
        <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Controllers:{" "}
          {controllers.length > 0
            ? controllers.join(", ")
            : "None detected on /dev/input/by-id"}
        </p>
      </div>
    </SettingsGroup>
  );
}

function EmulationCenterPanel({
  romDirs,
  biosPaths,
  onAdded,
}: {
  romDirs: unknown[];
  biosPaths: Record<string, string>;
  onAdded: () => void;
}) {
  const systemsQuery = useQuery({
    queryKey: ["systems"],
    queryFn: listSystems,
  });
  const [systemId, setSystemId] = useState("snes");
  const [useCustomCommand, setUseCustomCommand] = useState(false);
  const [customCommand, setCustomCommand] = useState("myemu {rom}");
  const queryClient = useQueryClient();
  const emulatorsQuery = useQuery({
    queryKey: ["emulators", systemId],
    queryFn: () => listEmulators(systemId),
    enabled: Boolean(systemId),
  });
  const managedQuery = useQuery({
    queryKey: ["managedRuntime", systemId],
    queryFn: () => recommendedManagedRuntime(systemId),
    enabled: Boolean(systemId),
  });
  const installManaged = useMutation({
    mutationFn: async () => {
      const spec = managedQuery.data;
      if (!spec) throw new Error("No managed emulator for this system");
      await installManagedRuntime(spec.id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["emulators", systemId] });
    },
  });
  const addBios = useMutation({
    mutationFn: async () => {
      const path = await pickFolder();
      if (!path) return;
      await setSystemBiosPath(systemId, path);
    },
    onSuccess: onAdded,
  });
  const addRom = useMutation({
    mutationFn: async () => {
      const path = await pickFolder();
      if (!path) return;
      if (useCustomCommand) {
        await addRomDirCustom(path, systemId, customCommand.trim());
        return;
      }
      const emu = emulatorsQuery.data?.[0];
      if (!emu) throw new Error("No emulator found for this system");
      await addRomDir(path, systemId, emu.id, emu.executable, emu.runtime);
    },
    onSuccess: onAdded,
  });

  const systems = systemsQuery.data ?? [];

  return (
    <SettingsGroup title="Emulation Center">
      {(romDirs ?? []).map((entry, index) => (
        <div key={index} className="kabin-grouped-row text-[calc(13px*var(--kabin-type-scale))]">
          <span className="text-kabin-secondary">
            {(entry as { system?: string }).system ?? "roms"}
          </span>
          <span className="max-w-[240px] truncate font-mono text-kabin-primary">
            {(entry as { path?: string }).path ?? ""}
          </span>
        </div>
      ))}
      <div className="space-y-3 p-4">
        <label className="block text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
          System
          <select
            value={systemId}
            onChange={(e) => setSystemId(e.target.value)}
            className="mt-1 w-full rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-grouped px-3 py-2 text-kabin-primary"
          >
            {systems.map((s: SystemInfo) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          {(emulatorsQuery.data ?? []).length > 0 ? (
            <>
              Emulator:{" "}
              {(emulatorsQuery.data ?? [])
                .map((e: EmulatorChoice) => e.name)
                .join(", ")}
            </>
          ) : managedQuery.data ? (
            <>
              No supported emulator detected. Kabin can securely download and
              manage {managedQuery.data.name} from its official release
              repository.
            </>
          ) : (
            "None detected — install a supported standalone emulator on this system."
          )}
        </p>
        {!(emulatorsQuery.data?.length ?? 0) && managedQuery.data ? (
          <button
            type="button"
            disabled={installManaged.isPending}
            onClick={() => installManaged.mutate()}
            className="rounded-[var(--kabin-radius-control)] border border-kabin-separator px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary disabled:opacity-40"
          >
            {installManaged.isPending
              ? "Downloading…"
              : `Install ${managedQuery.data.name}`}
          </button>
        ) : null}
        {installManaged.isError ? (
          <p className="text-[calc(13px*var(--kabin-type-scale))] text-red-400">
            {installManaged.error instanceof Error
              ? installManaged.error.message
              : "Installation failed"}
          </p>
        ) : null}
        {(systemId === "ps1" || systemId === "ps2") && (
          <div className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary">
            BIOS folder:{" "}
            <span className="font-mono text-kabin-primary">
              {biosPaths[systemId] ?? "Not set"}
            </span>
            <button
              type="button"
              onClick={() => addBios.mutate()}
              className="ml-2 text-kabin-accent"
            >
              Choose…
            </button>
          </div>
        )}
        <label className="flex items-center gap-2 text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary">
          <input
            type="checkbox"
            checked={useCustomCommand}
            onChange={(e) => setUseCustomCommand(e.target.checked)}
            className="h-4 w-4 accent-[var(--kabin-accent)]"
          />
          Custom launch command (must include {"{rom}"})
        </label>
        {useCustomCommand ? (
          <input
            value={customCommand}
            onChange={(e) => setCustomCommand(e.target.value)}
            className="w-full rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-grouped px-3 py-2 font-mono text-[calc(13px*var(--kabin-type-scale))] text-kabin-primary"
          />
        ) : null}
        <button
          type="button"
          disabled={
            addRom.isPending ||
            (!useCustomCommand && !(emulatorsQuery.data?.length ?? 0))
          }
          onClick={() => addRom.mutate()}
          className="rounded-[var(--kabin-radius-control)] bg-kabin-accent px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] font-medium text-white disabled:opacity-40"
        >
          Add ROM folder…
        </button>
        {addRom.isError ? (
          <p className="text-[calc(13px*var(--kabin-type-scale))] text-red-400">
            {addRom.error instanceof Error ? addRom.error.message : "Failed"}
          </p>
        ) : null}
      </div>
    </SettingsGroup>
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
