import { create } from "zustand";
import { savePlaybackProgress, type PlaybackTrack } from "../lib/kabin-api";
import { mediaSrc } from "../lib/media-src";

export type AudioSession = {
  titleId: string;
  title: string;
  subtitle: string;
  kind: string;
  accentHue: number;
  coverPath?: string | null;
  tracks: PlaybackTrack[];
  trackIndex: number;
  position: number;
  duration: number;
  playing: boolean;
};

export type ReadingSession = {
  titleId: string;
  title: string;
  subtitle: string;
  kind: string;
  accentHue: number;
  coverPath?: string | null;
  page: number;
  pageCount: number;
};

type BeginAudio = Omit<AudioSession, "duration" | "playing">;

type TransportState = {
  audio: AudioSession | null;
  reading: ReadingSession | null;
  beginAudio: (session: BeginAudio) => void;
  toggleAudio: () => void;
  seekAudio: (position: number) => void;
  changeTrack: (delta: number) => void;
  stopAudio: () => void;
  rememberReading: (session: ReadingSession) => void;
  clearReading: () => void;
};

let audioElement: HTMLAudioElement | null = null;
let saveTimer = 0;

export function bindAudioElement(element: HTMLAudioElement | null) {
  audioElement = element;
  if (element) ensureLoaded();
}

export const useTransportStore = create<TransportState>((set, get) => ({
  audio: null,
  reading: null,
  beginAudio: (session) => {
    const current = get().audio;
    if (current?.titleId === session.titleId) {
      set({
        audio: {
          ...current,
          title: session.title,
          subtitle: session.subtitle,
          accentHue: session.accentHue,
          coverPath: session.coverPath,
          tracks: session.tracks,
        },
      });
      return;
    }
    set({
      audio: {
        ...session,
        duration: 0,
        playing: true,
      },
    });
    loadTrack(true);
  },
  toggleAudio: () => {
    const audio = get().audio;
    if (!audio || !audioElement) return;
    if (audioElement.paused) {
      void audioElement.play().catch(() => setPlaying(false));
    } else {
      audioElement.pause();
    }
  },
  seekAudio: (position) => {
    if (audioElement) audioElement.currentTime = position;
    const audio = get().audio;
    if (!audio) return;
    set({ audio: { ...audio, position } });
  },
  changeTrack: (delta) => {
    const audio = get().audio;
    if (!audio) return;
    const trackIndex = Math.max(
      0,
      Math.min(audio.tracks.length - 1, audio.trackIndex + delta),
    );
    if (trackIndex === audio.trackIndex) return;
    set({
      audio: { ...audio, trackIndex, position: 0, duration: 0, playing: true },
    });
    loadTrack(true);
  },
  stopAudio: () => {
    if (audioElement) {
      audioElement.pause();
      audioElement.removeAttribute("src");
      audioElement.dataset.token = "";
    }
    window.clearTimeout(saveTimer);
    set({ audio: null });
  },
  rememberReading: (session) => {
    set({ reading: session });
  },
  clearReading: () => set({ reading: null }),
}));

function setPlaying(playing: boolean) {
  const audio = useTransportStore.getState().audio;
  if (!audio || audio.playing === playing) return;
  useTransportStore.setState({ audio: { ...audio, playing } });
}

function ensureLoaded() {
  const audio = useTransportStore.getState().audio;
  if (!audio || !audioElement) return;
  const token = `${audio.titleId}:${audio.trackIndex}`;
  if (audioElement.dataset.token === token && audioElement.getAttribute("src")) return;
  loadTrack(false);
}

function loadTrack(fromSessionPosition: boolean) {
  const audio = useTransportStore.getState().audio;
  const element = audioElement;
  if (!audio || !element) return;
  const track = audio.tracks[audio.trackIndex];
  const src = track ? mediaSrc(track.path) : null;
  if (!src) return;
  const token = `${audio.titleId}:${audio.trackIndex}`;
  if (element.dataset.token === token && element.getAttribute("src")) return;
  element.dataset.token = token;
  const startAt = fromSessionPosition ? audio.position : 0;
  element.src = src;
  element.addEventListener(
    "loadedmetadata",
    () => {
      if (startAt > 0 && Number.isFinite(element.duration)) {
        element.currentTime = Math.min(startAt, Math.max(0, element.duration - 0.25));
      }
      const playing = useTransportStore.getState().audio?.playing;
      if (playing) void element.play().catch(() => setPlaying(false));
    },
    { once: true },
  );
}

export function handleAudioTime() {
  const element = audioElement;
  const audio = useTransportStore.getState().audio;
  if (!element || !audio) return;
  const position = element.currentTime || 0;
  const duration = Number.isFinite(element.duration) ? element.duration : 0;
  if (
    Math.abs(position - audio.position) < 0.2 &&
    Math.abs(duration - audio.duration) < 0.2
  ) {
    return;
  }
  useTransportStore.setState({
    audio: { ...audio, position, duration },
  });
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    const latest = useTransportStore.getState().audio;
    if (!latest) return;
    void savePlaybackProgress(
      latest.titleId,
      latest.position,
      latest.duration,
      latest.trackIndex,
    );
  }, 800);
}

export function handleAudioEnded() {
  const audio = useTransportStore.getState().audio;
  if (!audio) return;
  if (audio.trackIndex < audio.tracks.length - 1) {
    useTransportStore.getState().changeTrack(1);
    return;
  }
  setPlaying(false);
}

export function formatClock(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}
