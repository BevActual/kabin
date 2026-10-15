import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { ShelfRow } from "../components/ShelfRow";
import { getAppInfo, scanLibrary } from "../lib/kabin-api";

export function HomeView() {
  const queryClient = useQueryClient();
  const scanQuery = useQuery({
    queryKey: ["libraryScan"],
    queryFn: () => scanLibrary(false),
  });
  const infoQuery = useQuery({
    queryKey: ["appInfo"],
    queryFn: getAppInfo,
  });

  const refresh = () => {
    void queryClient.fetchQuery({
      queryKey: ["libraryScan"],
      queryFn: () => scanLibrary(true),
    });
    void queryClient.invalidateQueries({ queryKey: ["libraryCounts"] });
  };

  if (scanQuery.isLoading) {
    return <StatusMessage>Scanning your library…</StatusMessage>;
  }

  if (scanQuery.isError) {
    return (
      <StatusMessage>
        Could not scan the library. Run inside the Tauri app or check Rust logs.
      </StatusMessage>
    );
  }

  const snapshot = scanQuery.data;
  const shelves = snapshot?.shelves ?? [];

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <p className="max-w-2xl text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
          {infoQuery.data ? (
            <>
              Config:{" "}
              <span className="font-mono text-[calc(13px*var(--kabin-type-scale))] text-kabin-primary">
                {infoQuery.data.configPath}
              </span>
              . Legacy GTK:{" "}
              <span className="font-mono text-[calc(13px*var(--kabin-type-scale))]">
                python3 -m kabin
              </span>
              .
            </>
          ) : null}
        </p>
        <button
          type="button"
          onClick={refresh}
          className="inline-flex items-center gap-2 rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-elevated px-3 py-2 text-[calc(14px*var(--kabin-type-scale))] font-medium text-kabin-primary hover:bg-kabin-grouped"
        >
          <RefreshCw size={16} strokeWidth={1.5} />
          Refresh
        </button>
      </div>

      {snapshot?.errors.map((err) => (
        <p
          key={`${err.source}-${err.message}`}
          className="mb-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary"
        >
          {err.source}: {err.message}
        </p>
      ))}

      {shelves.length === 0 ? (
        <StatusMessage>
          No titles found yet. Add media folders, Steam, or paired remote hosts
          in Settings, then refresh.
        </StatusMessage>
      ) : (
        shelves.map((shelf) => <ShelfRow key={shelf.id} shelf={shelf} />)
      )}
    </div>
  );
}

function StatusMessage({ children }: { children: ReactNode }) {
  return (
    <p className="text-[calc(17px*var(--kabin-type-scale))] text-kabin-secondary">
      {children}
    </p>
  );
}
