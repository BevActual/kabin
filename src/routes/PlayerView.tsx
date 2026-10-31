import { Link, getRouteApi } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Pause, Play, SkipBack, SkipForward, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { coverUrl, getPlaybackSession, getTitle, savePlaybackProgress } from "../lib/kabin-api";
import { mediaSrc } from "../lib/media-src";
import type { PlaybackSession } from "../lib/kabin-api";
import { formatClock, useTransportStore } from "../store/transport";

const route = getRouteApi("/player/$titleId");

export function PlayerView() {
  const { titleId } = route.useParams();
  const sessionQuery = useQuery({
    queryKey: ["playback", titleId],
    queryFn: () => getPlaybackSession(titleId),
  });
  const metaQuery = useQuery({
    queryKey: ["title-preview", titleId],
    queryFn: () => getTitle(titleId),
  });

  if (sessionQuery.isLoading) {
    return <p className="text-kabin-secondary">Loading player…</p>;
  }

  const session = sessionQuery.data;
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

  const art = coverUrl(metaQuery.data?.coverPath);
  if (session.kind === "video" || session.kind === "tv") {
    return <VideoStage titleId={titleId} session={session} />;
  }

  return (
    <AudioStage
      titleId={titleId}
      session={session}
      art={art}
      accentHue={metaQuery.data?.accentHue ?? 145}
      coverPath={metaQuery.data?.coverPath}
    />
  );
}

function AudioStage({
  titleId,
  session,
  art,
  accentHue,
  coverPath,
}: {
  titleId: string;
  session: PlaybackSession;
  art: string | null;
  accentHue: number;
  coverPath?: string | null;
}) {
  const audio = useTransportStore((s) => (s.audio?.titleId === titleId ? s.audio : null));
  const beginAudio = useTransportStore((s) => s.beginAudio);
  const toggleAudio = useTransportStore((s) => s.toggleAudio);
  const seekAudio = useTransportStore((s) => s.seekAudio);
  const changeTrack = useTransportStore((s) => s.changeTrack);

  useEffect(() => {
    beginAudio({
      titleId,
      title: session.title,
      subtitle: session.subtitle,
      kind: session.kind,
      accentHue,
      coverPath,
      tracks: session.tracks,
      trackIndex: session.initialTrack,
      position: session.initialPosition,
    });
  }, [accentHue, beginAudio, coverPath, session, titleId]);

  const trackIndex = audio?.trackIndex ?? session.initialTrack;
  const track = session.tracks[trackIndex];
  const playing = audio?.playing ?? false;
  const currentTime = audio?.position ?? session.initialPosition;
  const duration = audio?.duration ?? 0;

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
                  background: `linear-gradient(145deg, hsl(${accentHue} 42% 38%), hsl(${accentHue} 28% 18%))`,
                }
          }
        >
          {art ? <img src={art} alt="" className="h-full w-full object-cover" /> : null}
        </div>
        <h2 className="relative mt-8 text-[calc(28px*var(--kabin-type-scale))] font-semibold tracking-tight">
          {track?.label ?? session.title}
        </h2>
        <p className="relative mt-1 text-kabin-secondary">{session.title}</p>
      </div>
      <TransportControls
        currentTime={currentTime}
        duration={duration}
        playing={playing}
        trackCount={session.tracks.length}
        onToggle={toggleAudio}
        onSeek={seekAudio}
        onTrack={changeTrack}
      />
    </div>
  );
}

function VideoStage({
  titleId,
  session,
}: {
  titleId: string;
  session: PlaybackSession;
}) {
  const stopAudio = useTransportStore((s) => s.stopAudio);
  const mediaRef = useRef<HTMLVideoElement | null>(null);
  const [trackIndex, setTrackIndex] = useState(session.initialTrack);
  const [playing, setPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(session.initialPosition);
  const [duration, setDuration] = useState(0);
  const saveTimer = useRef<number | null>(null);

  useEffect(() => {
    stopAudio();
  }, [stopAudio]);

  useEffect(() => {
    const element = mediaRef.current;
    const track = session.tracks[trackIndex];
    if (!element || !track) return;
    const persist = (position: number, dur: number) => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void savePlaybackProgress(titleId, position, dur, trackIndex);
      }, 800);
    };
    const onTime = () => {
      setCurrentTime(element.currentTime);
      setDuration(element.duration || 0);
      persist(element.currentTime, element.duration || 0);
    };
    const onLoaded = () => {
      if (trackIndex === session.initialTrack && session.initialPosition > 0) {
        element.currentTime = session.initialPosition;
      }
      void element.play().catch(() => setPlaying(false));
    };
    element.addEventListener("timeupdate", onTime);
    element.addEventListener("loadedmetadata", onLoaded);
    return () => {
      element.removeEventListener("timeupdate", onTime);
      element.removeEventListener("loadedmetadata", onLoaded);
    };
  }, [session, titleId, trackIndex]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.code !== "Space") return;
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }
      event.preventDefault();
      const element = mediaRef.current;
      if (!element) return;
      if (element.paused) {
        void element.play();
        setPlaying(true);
      } else {
        element.pause();
        setPlaying(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const track = session.tracks[trackIndex];
  const changeTrack = (delta: number) => {
    const next = Math.max(0, Math.min(session.tracks.length - 1, trackIndex + delta));
    setTrackIndex(next);
    setCurrentTime(0);
    setPlaying(true);
  };

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
      <div className="overflow-hidden rounded-[var(--kabin-radius-sheet)] bg-black shadow-[var(--kabin-shadow-tile-focus)]">
        <video
          ref={mediaRef}
          key={track?.path}
          src={mediaSrc(track?.path) ?? undefined}
          className="aspect-video w-full bg-black"
          playsInline
          autoPlay
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
      </div>
      <TransportControls
        currentTime={currentTime}
        duration={duration}
        playing={playing}
        trackCount={session.tracks.length}
        onToggle={() => {
          const element = mediaRef.current;
          if (!element) return;
          if (element.paused) {
            void element.play();
            setPlaying(true);
          } else {
            element.pause();
            setPlaying(false);
          }
        }}
        onSeek={(time) => {
          setCurrentTime(time);
          if (mediaRef.current) mediaRef.current.currentTime = time;
        }}
        onTrack={changeTrack}
      />
    </div>
  );
}

function TransportControls({
  currentTime,
  duration,
  playing,
  trackCount,
  onToggle,
  onSeek,
  onTrack,
}: {
  currentTime: number;
  duration: number;
  playing: boolean;
  trackCount: number;
  onToggle: () => void;
  onSeek: (time: number) => void;
  onTrack: (delta: number) => void;
}) {
  return (
    <div className="kabin-material-bar fixed inset-x-0 bottom-0 px-6 py-4">
      <div className="mx-auto flex max-w-4xl flex-col gap-3">
        <input
          type="range"
          min={0}
          max={duration || 1}
          value={currentTime}
          onChange={(event) => onSeek(Number(event.target.value))}
          className="w-full accent-[var(--kabin-accent)]"
        />
        <div className="grid grid-cols-[4.5rem_1fr_4.5rem] items-center">
          <span className="text-left text-[calc(12px*var(--kabin-type-scale))] tabular-nums text-kabin-secondary">
            {formatClock(currentTime)}
          </span>
          <div className="flex items-center justify-center gap-2">
            {trackCount > 1 ? (
              <button
                type="button"
                onClick={() => onTrack(-1)}
                className="rounded-full p-2 text-kabin-primary hover:bg-kabin-grouped"
                aria-label="Previous track"
              >
                <SkipBack size={22} strokeWidth={1.5} />
              </button>
            ) : null}
            <button
              type="button"
              onClick={onToggle}
              className="rounded-full bg-kabin-accent p-3.5 text-white"
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? (
                <Pause size={22} strokeWidth={1.5} className="fill-current" />
              ) : (
                <Play size={22} strokeWidth={1.5} className="fill-current" />
              )}
            </button>
            {trackCount > 1 ? (
              <button
                type="button"
                onClick={() => onTrack(1)}
                className="rounded-full p-2 text-kabin-primary hover:bg-kabin-grouped"
                aria-label="Next track"
              >
                <SkipForward size={22} strokeWidth={1.5} />
              </button>
            ) : null}
          </div>
          <span className="text-right text-[calc(12px*var(--kabin-type-scale))] tabular-nums text-kabin-secondary">
            {duration > 0 ? `-${formatClock(Math.max(0, duration - currentTime))}` : "--:--"}
          </span>
        </div>
      </div>
    </div>
  );
}
