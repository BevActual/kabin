import { Link } from "@tanstack/react-router";
import { Pause, Play, X } from "lucide-react";
import { coverUrl } from "../lib/kabin-api";
import { labelForKind } from "../lib/modes";
import { formatClock, useTransportStore } from "../store/transport";

export function TransportBar() {
  const audio = useTransportStore((s) => s.audio);
  const reading = useTransportStore((s) => s.reading);
  const toggleAudio = useTransportStore((s) => s.toggleAudio);
  const stopAudio = useTransportStore((s) => s.stopAudio);
  const clearReading = useTransportStore((s) => s.clearReading);
  const session = audio ?? reading;
  if (!session) return null;

  const art = coverUrl(session.coverPath);
  const playing = audio?.playing ?? false;
  const progress = audio
    ? audio.duration > 0
      ? Math.min(100, (audio.position / audio.duration) * 100)
      : 0
    : reading && reading.pageCount > 0
      ? Math.min(100, ((reading.page + 1) / reading.pageCount) * 100)
      : 0;
  const detail = audio
    ? audio.duration > 0
      ? `${formatClock(audio.position)} / ${formatClock(audio.duration)}`
      : labelForKind(audio.kind)
    : reading
      ? `Page ${reading.page + 1} of ${Math.max(reading.pageCount, 1)}`
      : "";

  return (
    <div className="kabin-transport" data-transport={audio ? "audio" : "reading"}>
      <div className="kabin-glass relative flex items-center gap-3 px-3 py-2">
        <div className="absolute inset-x-4 top-0 h-0.5 overflow-hidden rounded-full">
          <div className="h-full bg-kabin-accent" style={{ width: `${progress}%` }} />
        </div>
        <Link
          to={audio ? "/player/$titleId" : "/read/$titleId"}
          params={{ titleId: session.titleId }}
          className="flex min-w-0 flex-1 items-center gap-3"
        >
          <span
            className="h-11 w-11 shrink-0 overflow-hidden rounded-[10px]"
            style={
              art
                ? undefined
                : {
                    background: `linear-gradient(145deg, hsl(${session.accentHue} 42% 38%), hsl(${session.accentHue} 28% 18%))`,
                  }
            }
          >
            {art ? <img src={art} alt="" className="h-full w-full object-cover" /> : null}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[calc(15px*var(--kabin-type-scale))] font-semibold">
              {session.title}
            </span>
            <span className="block truncate text-[calc(13px*var(--kabin-type-scale))] text-kabin-secondary">
              {session.subtitle ? `${session.subtitle} · ${detail}` : detail}
            </span>
          </span>
        </Link>
        {audio ? (
          <button
            type="button"
            onClick={toggleAudio}
            aria-label={playing ? "Pause" : "Play"}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-kabin-accent text-white"
          >
            {playing ? (
              <Pause size={16} strokeWidth={1.75} className="fill-current" />
            ) : (
              <Play size={16} strokeWidth={1.75} className="fill-current" />
            )}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => (audio ? stopAudio() : clearReading())}
          aria-label={audio ? "Stop playing" : "Close book"}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
        >
          <X size={16} strokeWidth={1.75} />
        </button>
      </div>
    </div>
  );
}
