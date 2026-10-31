import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SegmentedControl } from "./SegmentedControl";
import { Switch } from "./Switch";
import {
  getDownloadStatus,
  pickFolder,
  removeIndexer,
  saveIndexer,
  saveUsenetServer,
  setDownloadFolder,
  setDownloadImportDir,
  setDownloadQuality,
  setUsenetConnections,
  testUsenetServer,
} from "../lib/kabin-api";

const fieldClass = "kabin-field w-full";

export function DownloadsSettings() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
  });
  const data = status.data;
  const [host, setHost] = useState("");
  const [port, setPort] = useState("563");
  const [ssl, setSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [connections, setConnections] = useState("4");
  const [indexerName, setIndexerName] = useState("");
  const [indexerUrl, setIndexerUrl] = useState("");
  const [indexerKey, setIndexerKey] = useState("");
  const [indexerKind, setIndexerKind] = useState<"torznab" | "newznab">(
    "torznab",
  );
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setHost(data.usenet.host);
    setPort(String(data.usenet.port || (data.usenet.ssl ? 563 : 119)));
    setSsl(data.usenet.ssl);
    setUsername(data.usenet.username);
    setConnections(String(data.connections || 4));
  }, [data]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["downloads"] });
  };

  const saveServer = useMutation({
    mutationFn: () =>
      saveUsenetServer({
        host,
        port: Number(port) || 0,
        ssl,
        username,
        password,
      }),
    onSuccess: () => {
      setPassword("");
      setNotice(null);
      refresh();
    },
    onError: (error: Error) => setNotice(error.message),
  });

  const testServer = useMutation({
    mutationFn: async () => {
      await saveUsenetServer({
        host,
        port: Number(port) || 0,
        ssl,
        username,
        password,
      });
      return testUsenetServer();
    },
    onSuccess: (message) => {
      setPassword("");
      setNotice(message);
      refresh();
    },
    onError: (error: Error) => setNotice(error.message),
  });

  const chooseImport = useMutation({
    mutationFn: async () => {
      const path = await pickFolder();
      if (path) await setDownloadImportDir(path);
    },
    onSuccess: refresh,
  });

  const chooseDownload = useMutation({
    mutationFn: async () => {
      const path = await pickFolder();
      if (path) await setDownloadFolder(path);
    },
    onSuccess: refresh,
  });

  const addIndexer = useMutation({
    mutationFn: () =>
      saveIndexer({
        name: indexerName,
        url: indexerUrl,
        apiKey: indexerKey,
        kind: indexerKind,
      }),
    onSuccess: () => {
      setIndexerName("");
      setIndexerUrl("");
      setIndexerKey("");
      setNotice(null);
      refresh();
    },
    onError: (error: Error) => setNotice(error.message),
  });

  return (
    <section className="space-y-8">
      <div>
        <h2 className="mb-2 px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Downloads
        </h2>
        <div className="kabin-grouped">
          <div className="kabin-grouped-row">
            <span className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary">
              Quality
            </span>
            <SegmentedControl
              label="Quality"
              value={data?.quality ?? "1080p"}
              onChange={(quality) => {
                void setDownloadQuality(quality).then(refresh);
              }}
              options={[
                { id: "any", label: "Any" },
                { id: "720p", label: "720p" },
                { id: "1080p", label: "1080p" },
                { id: "2160p", label: "4K" },
              ]}
            />
          </div>
          <button
            type="button"
            className="kabin-grouped-row w-full text-left"
            onClick={() => chooseImport.mutate()}
          >
            <span className="min-w-0 flex-1">
              <span className="block text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary">
                Library folder
              </span>
              <span className="block truncate font-mono text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
                {data?.importDir || "Finished videos are added here"}
              </span>
            </span>
          </button>
          <button
            type="button"
            className="kabin-grouped-row w-full text-left"
            onClick={() => chooseDownload.mutate()}
          >
            <span className="min-w-0 flex-1">
              <span className="block text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary">
                Download folder
              </span>
              <span className="block truncate font-mono text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
                {data?.downloadDir || "Kabin"}
              </span>
            </span>
          </button>
        </div>
        <p className="mt-2 px-1 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Point the library folder at a Movies folder you already added under
          Media folders. Kabin keeps the original download as well.
        </p>
      </div>

      <div>
        <h2 className="mb-2 px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Usenet server
        </h2>
        <form
          className="kabin-grouped space-y-3 px-4 py-4"
          onSubmit={(event) => {
            event.preventDefault();
            saveServer.mutate();
          }}
        >
          <input
            value={host}
            onChange={(event) => setHost(event.target.value)}
            placeholder="news.example.com"
            className={fieldClass}
          />
          <div className="flex flex-wrap items-center gap-3">
            <input
              value={port}
              onChange={(event) => setPort(event.target.value)}
              inputMode="numeric"
              aria-label="Port"
              className="kabin-field w-28"
            />
            <div className="flex items-center gap-2">
              <Switch label="TLS" checked={ssl} onChange={setSsl} />
              <span className="text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
                TLS
              </span>
            </div>
            <label className="flex items-center gap-2 text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
              Connections
              <input
                value={connections}
                onChange={(event) => setConnections(event.target.value)}
                inputMode="numeric"
                aria-label="Connections"
                className="kabin-field w-20"
                onBlur={() => {
                  const value = Number(connections);
                  if (value) void setUsenetConnections(value).then(refresh);
                }}
              />
            </label>
          </div>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Username"
            autoComplete="off"
            className={fieldClass}
          />
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={data?.usenet.hasPassword ? "Password saved" : "Password"}
            type="password"
            autoComplete="new-password"
            className={fieldClass}
          />
          <div className="flex gap-4">
            <button type="submit" className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent">
              Save server
            </button>
            <button
              type="button"
              className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary"
              onClick={() => testServer.mutate()}
            >
              Test
            </button>
          </div>
        </form>
      </div>

      <div>
        <h2 className="mb-2 px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Indexers
        </h2>
        <div className="kabin-grouped">
          {(data?.indexers ?? []).map((indexer) => (
            <div key={indexer.id} className="kabin-grouped-row">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary">
                  {indexer.name}
                </p>
                <p className="truncate text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
                  {indexer.kind === "newznab" ? "Newznab" : "Torznab"}
                </p>
              </div>
              <button
                type="button"
                className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
                onClick={() => {
                  void removeIndexer(indexer.id).then(refresh);
                }}
              >
                Remove
              </button>
            </div>
          ))}
          <form
            className="space-y-3 px-4 py-4"
            onSubmit={(event) => {
              event.preventDefault();
              addIndexer.mutate();
            }}
          >
            <SegmentedControl
              label="Indexer type"
              value={indexerKind}
              onChange={setIndexerKind}
              options={[
                { id: "torznab", label: "Torznab" },
                { id: "newznab", label: "Newznab" },
              ]}
            />
            <input
              value={indexerName}
              onChange={(event) => setIndexerName(event.target.value)}
              placeholder="Name"
              className={fieldClass}
            />
            <input
              value={indexerUrl}
              onChange={(event) => setIndexerUrl(event.target.value)}
              placeholder="https://indexer.example/api"
              className={fieldClass}
            />
            <input
              value={indexerKey}
              onChange={(event) => setIndexerKey(event.target.value)}
              placeholder="API key"
              type="password"
              autoComplete="new-password"
              className={fieldClass}
            />
            <button
              type="submit"
              className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
            >
              Add indexer
            </button>
          </form>
        </div>
        <p className="mt-2 px-1 text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
          Kabin does not include indexers. Add a Torznab address for torrents
          and a Newznab address for Usenet. Nothing is searched until you ask.
          Usenet posts that are still packed archives stay in the download
          folder until a video file is ready.
        </p>
        {notice ? (
          <p className="mt-2 px-1 text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary">
            {notice}
          </p>
        ) : null}
      </div>
    </section>
  );
}
