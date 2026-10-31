import { Link, getRouteApi } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Pause, Play, SkipBack, SkipForward, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { coverUrl, getPlaybackSession, savePlaybackProgress } from "../lib/kabin-api";
import { getTitle } from "../lib/kabin-api";

const route = getRouteApi("/player/$titleId");

function formatClock(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function PlayerView() {
  const { titleId } = route.useParams();
  const sessionQuery = useQuery({
    queryKey: ["playback", titleId],
    queryFn: () => getPlaybackSession(titleId),
  });
  const metaQuery = useQuery({
    queryKey: ["title", titleId],
    queryFn: () => getTitle(titleId),
  });

  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement | null>(null);
  const [trackIndex, setTrackIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const saveTimer = useRef<number | null>(null);

  const session = sessionQuery.data;
  const isVideo = session?.kind === "video" || session?.kind === "tv";

  useEffect(() => {
    if (!session) return;
    setTrackIndex(session.initialTrack);
    setCurrentTime(session.initialPosition);
  }, [session]);

  const persistProgress = useCallback(
    (position: number, dur: number, track: number) => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void savePlaybackProgress(titleId, position, dur, track);
      }, 800);
    },
    [titleId],
  );

  useEffect(() => {
    const el = mediaRef.current;
    if (!el || !session) return;
    const track = session.tracks[trackIndex];
    if (!track) return;

    const onTime = () => {
      setCurrentTime(el.currentTime);
      setDuration(el.duration || 0);
      persistProgress(el.currentTime, el.duration || 0, trackIndex);
    };
    const onLoaded = () => {
      if (trackIndex === session.initialTrack && session.initialPosition > 0) {
        el.currentTime = session.initialPosition;
      }
      void el.play().catch(() => setPlaying(false));
    };
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("loadedmetadata", onLoaded);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("loadedmetadata", onLoaded);
    };
  }, [session, trackIndex, persistProgress]);

  const togglePlay = useCallback(() => {
    const el = mediaRef.current;
    if (!el) return;
    if (el.paused) {
      void el.play();
      setPlaying(true);
    } else {
      el.pause();
      setPlaying(false);
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay]);

  const changeTrack = (delta: number) => {
    if (!session) return;
    const next = Math.max(0, Math.min(session.tracks.length - 1, trackIndex + delta));
    setTrackIndex(next);
    setCurrentTime(0);
    setPlaying(true);
  };

  if (sessionQuery.isLoading) {
    return <p className="text-kabin-secondary">Loading player…</p>;
  }

  if (!session || session.tracks.length === 0) {
    return (
      <div>
        <p className="text-kabin-secondary">This title cannot play inside Kabin.</p>
        <Link to="/title/$titleId" params={{ titleId }} className="mt-4 inline-block text-kabin-accent">
          Back to details
        </Link>
      </div>
    );
  }

  const track = session.tracks[trackIndex];
  const mediaSrc = coverUrl(track.path);
  const art = coverUrl(metaQuery.data?.coverPath);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 pb-24">
      <div className="flex items-center justify-between">
        <Link
          to="/title/$titleId"
          params={{ titleId }}
          className="inline-flex items-center gap-2 text-kabin-secondary hover:text-kabin-primary"
        >
          <X size={20} strokeWidth={1.5} />
          Close
        </Link>
      </div>

      {isVideo ? (
        <div className="overflow-hidden rounded-[var(--kabin-radius-sheet)] bg-black shadow-[var(--kabin-shadow-tile-focus)]">
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            key={track.path}
            src={mediaSrc ?? undefined}
            className="aspect-video w-full bg-black"
            playsInline
            autoPlay
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
        </div>
      ) : (
        <div className="relative flex min-h-[62vh] flex-col items-center justify-center px-4 text-center">
          {art ? (
            <img
              src={art}
              alt=""
              className="pointer-events-none absolute inset-0 h-full w-full scale-110 object-cover opacity-30 blur-3xl"
            />
          ) : null}
          <div
            className="relative aspect-square w-full max-w-sm overflow-hidden rounded-[var(--kabin-radius-sheet)] shadow-[var(--kabin-shadow-tile-focus)]"
            style={
              art
                ? undefined
                : {
                    background:
                      "linear-gradient(145deg, hsl(145 42% 38%), hsl(145 28% 18%))",
                  }
            }
          >
            {art ? (
              <img src={art} alt="" className="h-full w-full object-cover" />
            ) : null}
          </div>
          <h2 className="relative mt-8 text-[calc(28px*var(--kabin-type-scale))] font-semibold tracking-tight">
            {track.label}
          </h2>
          <p className="relative mt-1 text-kabin-secondary">{session.title}</p>
          <audio
            ref={mediaRef as React.RefObject<HTMLAudioElement>}
            key={track.path}
            src={mediaSrc ?? undefined}
            autoPlay
            className="hidden"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
        </div>
      )}

      <div className="kabin-material-bar fixed inset-x-0 bottom-0 px-6 py-4">
        <div className="mx-auto flex max-w-4xl flex-col gap-3">
          <input
            type="range"
            min={0}
            max={duration || 1}
            value={currentTime}
            onChange={(e) => {
              const t = Number(e.target.value);
              setCurrentTime(t);
              if (mediaRef.current) mediaRef.current.currentTime = t;
            }}
            className="w-full accent-[var(--kabin-accent)]"
          />
          <div className="grid grid-cols-[4.5rem_1fr_4.5rem] items-center">
            <span className="text-left text-[calc(12px*var(--kabin-type-scale))] tabular-nums text-kabin-secondary">
              {formatClock(currentTime)}
            </span>
            <div className="flex items-center justify-center gap-2">
              {session.tracks.length > 1 ? (
                <>
                  <button
                    type="button"
                    onClick={() => changeTrack(-1)}
                    className="rounded-full p-2 text-kabin-primary hover:bg-kabin-grouped"
                    aria-label="Previous track"
                  >
                    <SkipBack size={22} strokeWidth={1.5} />
                  </button>
                  <button
                    type="button"
                    onClick={togglePlay}
                    className="rounded-full bg-kabin-accent p-3.5 text-white"
                    aria-label={playing ? "Pause" : "Play"}
                  >
                    {playing ? (
                      <Pause size={22} strokeWidth={1.5} className="fill-current" />
                    ) : (
                      <Play size={22} strokeWidth={1.5} className="fill-current" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => changeTrack(1)}
                    className="rounded-full p-2 text-kabin-primary hover:bg-kabin-grouped"
                    aria-label="Next track"
                  >
                    <SkipForward size={22} strokeWidth={1.5} />
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={togglePlay}
                  className="rounded-full bg-kabin-accent p-3.5 text-white"
                  aria-label={playing ? "Pause" : "Play"}
                >
                  {playing ? (
                    <Pause size={22} strokeWidth={1.5} className="fill-current" />
                  ) : (
                    <Play size={22} strokeWidth={1.5} className="fill-current" />
                  )}
                </button>
              )}
            </div>
            <span className="text-right text-[calc(12px*var(--kabin-type-scale))] tabular-nums text-kabin-secondary">
              {duration > 0
                ? `-${formatClock(Math.max(0, duration - currentTime))}`
                : "--:--"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
