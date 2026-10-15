import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAppInfo, getHomeShelves } from "../lib/kabin-api";
import { ShelfRow } from "../components/ShelfRow";

export function HomeView() {
  const shelvesQuery = useQuery({
    queryKey: ["homeShelves"],
    queryFn: getHomeShelves,
  });
  const infoQuery = useQuery({
    queryKey: ["appInfo"],
    queryFn: getAppInfo,
  });

  if (shelvesQuery.isLoading) {
    return <StatusMessage>Loading your cabinet…</StatusMessage>;
  }

  if (shelvesQuery.isError) {
    return (
      <StatusMessage>
        Could not load the library. Run inside the Tauri app or check Rust logs.
      </StatusMessage>
    );
  }

  const shelves = shelvesQuery.data ?? [];

  return (
    <div>
      {infoQuery.data?.legacyPython ? (
        <p className="mb-6 max-w-2xl text-[calc(15px*var(--kabin-type-scale))] text-kabin-secondary">
          This build uses the new Kabin shell. Your existing config stays at{" "}
          <span className="font-mono text-[calc(13px*var(--kabin-type-scale))] text-kabin-primary">
            {infoQuery.data.configPath}
          </span>
          . The GTK app remains available with{" "}
          <span className="font-mono text-[calc(13px*var(--kabin-type-scale))]">
            python3 -m kabin
          </span>
          .
        </p>
      ) : null}
      {shelves.length === 0 ? (
        <StatusMessage>
          No titles here yet. Add library folders in Settings when scanning is wired up.
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
