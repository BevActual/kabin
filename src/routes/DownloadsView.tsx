import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SegmentedControl } from "../components/SegmentedControl";
import {
  addDownload,
  addWanted,
  downloadAction,
  getDownloadStatus,
  removeWanted,
  searchWanted,
  type DownloadJob,
  type ReleaseHit,
} from "../lib/kabin-api";

function formatBytes(bytes: number) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit += 1;
  }
  return unit === 0 ? `${bytes} B` : `${value.toFixed(1)} ${units[unit]}`;
}

function statusLabel(job: DownloadJob) {
  if (job.imported) return "In library";
  if (job.status === "paused") return "Paused";
  if (job.status === "complete") return "Finished";
  if (job.status === "error") return "Needs attention";
  if (job.status === "queued") return "Waiting";
  return job.protocol === "usenet" ? "Downloading from Usenet" : "Downloading";
}

export function DownloadsView() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
    refetchInterval: 2000,
  });
  const data = status.data;
  const [link, setLink] = useState("");
  const [title, setTitle] = useState("");
  const [year, setYear] = useState("");
  const [kind, setKind] = useState<"movie" | "series">("movie");
  const [results, setResults] = useState<Record<string, ReleaseHit[]>>({});
  const [activeSearch, setActiveSearch] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const importedCount = data?.jobs.filter((job) => job.imported).length ?? 0;

  useEffect(() => {
    if (importedCount > 0) {
      void queryClient.invalidateQueries({ queryKey: ["libraryScan"] });
      void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
    }
  }, [importedCount, queryClient]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["downloads"] });
  };

  const addLink = useMutation({
    mutationFn: () => addDownload(link, "", "", ""),
    onSuccess: () => {
      setLink("");
      setMessage(null);
      refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });

  const addTitle = useMutation({
    mutationFn: () => addWanted(title, year, kind),
    onSuccess: () => {
      setTitle("");
      setYear("");
      setMessage(null);
      refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });

  const search = useMutation({
    mutationFn: (id: string) => searchWanted(id),
    onMutate: (id) => setActiveSearch(id),
    onSuccess: (hits, id) => {
      setResults((current) => ({ ...current, [id]: hits }));
      setMessage(hits.length === 0 ? "No releases matched that quality." : null);
    },
    onError: (error: Error) => setMessage(error.message),
    onSettled: () => setActiveSearch(null),
  });

  const grab = useMutation({
    mutationFn: (hit: ReleaseHit) =>
      addDownload(hit.link, hit.title, hit.protocol, ""),
    onSuccess: () => {
      setMessage(null);
      refresh();
    },
    onError: (error: Error) => setMessage(error.message),
  });

  const mutateJob = useMutation({
    mutationFn: (input: { id: string; action: string }) =>
      downloadAction(input.id, input.action),
    onSuccess: refresh,
    onError: (error: Error) => setMessage(error.message),
  });

  const dropWanted = useMutation({
    mutationFn: (id: string) => removeWanted(id),
    onSuccess: refresh,
  });

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <p className="max-w-xl text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
        Kabin downloads torrents and Usenet posts itself, then files finished
        videos into your library.
      </p>

      {message ? (
        <p className="text-[calc(14px*var(--kabin-type-scale))] text-kabin-accent">
          {message}
        </p>
      ) : null}

      <section className="space-y-3">
        <h2 className="px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Add a link
        </h2>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            addLink.mutate();
          }}
        >
          <input
            value={link}
            onChange={(event) => setLink(event.target.value)}
            placeholder="Magnet link or NZB address"
            className="kabin-field min-w-0 flex-1"
          />
          <button
            type="submit"
            disabled={addLink.isPending || link.trim() === ""}
            className="kabin-primary-button"
          >
            Download
          </button>
        </form>
      </section>

      <section className="space-y-3">
        <h2 className="px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Wanted
        </h2>
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            addTitle.mutate();
          }}
        >
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Movie or show"
              className="kabin-field min-w-0 flex-1"
            />
            <input
              value={year}
              onChange={(event) => setYear(event.target.value)}
              placeholder="Year"
              inputMode="numeric"
              className="kabin-field sm:w-28"
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SegmentedControl
              label="Kind"
              value={kind}
              onChange={setKind}
              options={[
                { id: "movie", label: "Movie" },
                { id: "series", label: "Series" },
              ]}
            />
            <button
              type="submit"
              disabled={addTitle.isPending || title.trim() === ""}
              className="kabin-primary-button"
            >
              Add
            </button>
          </div>
        </form>

        <div className="kabin-grouped">
          {(data?.wanted ?? []).length === 0 ? (
            <p className="px-4 py-4 text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
              Titles you are looking for show up here. Search checks the
              indexers in Settings.
            </p>
          ) : (
            data?.wanted.map((item) => (
              <div key={item.id} className="border-b border-kabin-separator last:border-b-0">
                <div className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[calc(16px*var(--kabin-type-scale))] text-kabin-primary">
                      {item.title}
                    </p>
                    <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
                      {item.kind === "series" ? "Series" : "Movie"}
                      {item.year ? ` · ${item.year}` : ""} · {item.quality}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
                    disabled={search.isPending && activeSearch === item.id}
                    onClick={() => search.mutate(item.id)}
                  >
                    Search
                  </button>
                  <button
                    type="button"
                    className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary"
                    onClick={() => dropWanted.mutate(item.id)}
                  >
                    Remove
                  </button>
                </div>
                {(results[item.id] ?? []).map((hit) => (
                  <div
                    key={`${hit.indexer}-${hit.link}`}
                    className="flex items-center gap-3 bg-kabin-grouped px-4 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary">
                        {hit.title}
                      </p>
                      <p className="text-[calc(12px*var(--kabin-type-scale))] text-kabin-tertiary">
                        {hit.protocol === "usenet" ? "Usenet" : "Torrent"}
                        {hit.sizeLabel && hit.sizeLabel !== "0 B"
                          ? ` · ${hit.sizeLabel}`
                          : ""}
                        {hit.seeders != null ? ` · ${hit.seeders} seeders` : ""}
                        {` · ${hit.indexer}`}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
                      disabled={grab.isPending}
                      onClick={() => grab.mutate(hit)}
                    >
                      Download
                    </button>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="px-1 text-[calc(13px*var(--kabin-type-scale))] font-medium text-kabin-secondary uppercase">
          Activity
        </h2>
        <div className="kabin-grouped">
          {(data?.jobs ?? []).length === 0 ? (
            <p className="px-4 py-4 text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
              Nothing is downloading.
            </p>
          ) : (
            data?.jobs.map((job) => {
              const amount =
                job.bytesTotal > 0
                  ? `${formatBytes(job.bytesDone)} of ${formatBytes(job.bytesTotal)}`
                  : "";
              return (
                <div key={job.id} className="space-y-2 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[calc(16px*var(--kabin-type-scale))] text-kabin-primary">
                        {job.name}
                      </p>
                      <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-tertiary">
                        {statusLabel(job)}
                        {amount ? ` · ${amount}` : ""}
                      </p>
                    </div>
                    {job.status === "downloading" || job.status === "queued" ? (
                      <button
                        type="button"
                        className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
                        onClick={() =>
                          mutateJob.mutate({ id: job.id, action: "pause" })
                        }
                      >
                        Pause
                      </button>
                    ) : null}
                    {job.status === "paused" || job.status === "error" ? (
                      <button
                        type="button"
                        className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-accent"
                        onClick={() =>
                          mutateJob.mutate({ id: job.id, action: "resume" })
                        }
                      >
                        Resume
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary"
                      onClick={() =>
                        mutateJob.mutate({ id: job.id, action: "remove" })
                      }
                    >
                      Remove
                    </button>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-kabin-separator">
                    <div
                      className="h-full bg-kabin-accent"
                      style={{ width: `${Math.round(job.progress * 100)}%` }}
                    />
                  </div>
                  {job.error ? (
                    <p className="text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary">
                      {job.error}
                    </p>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
