import { Link, getRouteApi } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import ePub from "epubjs";
import {
  coverUrl,
  getReaderSession,
  saveReaderProgress,
} from "../lib/kabin-api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const route = getRouteApi("/read/$titleId");

export function ReaderView() {
  const { titleId } = route.useParams();
  const sessionQuery = useQuery({
    queryKey: ["reader", titleId],
    queryFn: () => getReaderSession(titleId),
  });

  const session = sessionQuery.data;
  const [page, setPage] = useState(0);
  const [numPages, setNumPages] = useState(1);
  const epubRef = useRef<ReturnType<typeof ePub> | null>(null);
  const saveTimer = useRef<number | null>(null);

  useEffect(() => {
    if (session) {
      setPage(session.initialPage);
      setNumPages(session.pageCount || 1);
    }
  }, [session]);

  const persist = useCallback(
    (p: number, total: number) => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void saveReaderProgress(titleId, p, total);
      }, 600);
    },
    [titleId],
  );

  useEffect(() => {
    if (!session || session.backend !== "epub" || !session.filePath) return;
    const book = ePub(coverUrl(session.filePath) ?? session.filePath);
    epubRef.current = book;
    const rendition = book.renderTo("kabin-epub-view", {
      width: "100%",
      height: "70vh",
      flow: "paginated",
    });
    void rendition.display(session.initialPage).then(() => {
      rendition.on("relocated", (location: { start: { displayed: { page: number } } }) => {
        const p = location.start.displayed.page;
        setPage(p);
        persist(p, numPages);
      });
    });
    return () => {
      book.destroy();
    };
  }, [session, numPages, persist]);

  const go = useCallback(
    (delta: number) => {
    if (!session) return;
    if (session.backend === "epub" && epubRef.current) {
      const r = epubRef.current.rendition;
      if (delta > 0) void r?.next();
      else void r?.prev();
      return;
    }
    const next = Math.max(0, Math.min(numPages - 1, page + delta));
    setPage(next);
    persist(next, numPages);
    },
    [session, numPages, page, persist],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "PageDown") {
        e.preventDefault();
        go(1);
      }
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        go(-1);
      }
      if (e.code === "Space") {
        e.preventDefault();
        go(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  if (sessionQuery.isLoading) {
    return <p className="text-kabin-secondary">Opening reader…</p>;
  }

  if (!session) {
    return (
      <div>
        <p className="text-kabin-secondary">
          Kabin cannot read this file in-app (try MOBI/AZW3/CBR in the GTK app).
        </p>
        <Link to="/title/$titleId" params={{ titleId }} className="mt-4 inline-block text-kabin-accent">
          Back
        </Link>
      </div>
    );
  }

  const fileSrc = session.filePath ? coverUrl(session.filePath) : null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 pb-28">
      <header className="flex items-center justify-between">
        <h1 className="truncate text-[calc(20px*var(--kabin-type-scale))] font-semibold">
          {session.title}
        </h1>
        <Link
          to="/title/$titleId"
          params={{ titleId }}
          className="inline-flex items-center gap-1 text-kabin-secondary hover:text-kabin-primary"
        >
          <X size={20} strokeWidth={1.5} />
          Close
        </Link>
      </header>

      <div className="min-h-[60vh] rounded-[var(--kabin-radius-sheet)] bg-kabin-elevated p-4">
        {session.backend === "pdf" && fileSrc ? (
          <Document
            file={fileSrc}
            onLoadSuccess={({ numPages: n }) => {
              setNumPages(n);
              persist(page, n);
            }}
          >
            <Page pageNumber={page + 1} width={720} />
          </Document>
        ) : null}

        {session.backend === "cbz" ? (
          session.pages[page] ? (
            <img
              src={coverUrl(session.pages[page]) ?? undefined}
              alt=""
              className="mx-auto max-h-[70vh] object-contain"
            />
          ) : null
        ) : null}

        {session.backend === "txt" && fileSrc ? (
          <TxtReader src={fileSrc} titleId={titleId} initialPage={session.initialPage} />
        ) : null}

        {session.backend === "epub" ? (
          <div id="kabin-epub-view" className="min-h-[70vh]" />
        ) : null}

        {session.backend === "fb2" ? (
          <p className="text-kabin-secondary">
            FB2 in-app reading is not ported yet. Use{" "}
            <span className="font-mono">python3 -m kabin</span>.
          </p>
        ) : null}
      </div>

      {session.backend !== "txt" && session.backend !== "epub" ? (
        <ReaderChrome
          page={page}
          total={numPages}
          onPrev={() => go(-1)}
          onNext={() => go(1)}
          onSeek={(p) => {
            setPage(p);
            persist(p, numPages);
          }}
        />
      ) : null}
    </div>
  );
}

function TxtReader({
  src,
  titleId,
  initialPage,
}: {
  src: string;
  titleId: string;
  initialPage: number;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void fetch(src)
      .then((r) => r.text())
      .then(setText);
  }, [src]);

  useEffect(() => {
    if (ref.current && initialPage > 0) {
      ref.current.scrollTop = initialPage;
    }
  }, [text, initialPage]);

  return (
    <div
      ref={ref}
      className="max-h-[70vh] overflow-y-auto whitespace-pre-wrap font-serif text-[calc(17px*var(--kabin-type-scale))] leading-relaxed"
      onScroll={() => {
        if (!ref.current) return;
        void saveReaderProgress(titleId, Math.floor(ref.current.scrollTop), 1);
      }}
    >
      {text}
    </div>
  );
}

function ReaderChrome({
  page,
  total,
  onPrev,
  onNext,
  onSeek,
}: {
  page: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  onSeek: (p: number) => void;
}) {
  return (
    <div className="kabin-material-bar fixed inset-x-0 bottom-0 px-6 py-4">
      <div className="mx-auto flex max-w-4xl flex-col gap-2">
        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={page}
          onChange={(e) => onSeek(Number(e.target.value))}
          className="w-full accent-[var(--kabin-accent)]"
        />
        <div className="flex items-center justify-between text-[calc(14px*var(--kabin-type-scale))] text-kabin-secondary">
          <button type="button" onClick={onPrev} className="rounded-full p-2 hover:bg-kabin-grouped">
            <ChevronLeft size={22} />
          </button>
          <span className="tabular-nums">
            Page {page + 1} of {total}
          </span>
          <button type="button" onClick={onNext} className="rounded-full p-2 hover:bg-kabin-grouped">
            <ChevronRight size={22} />
          </button>
        </div>
      </div>
    </div>
  );
}
