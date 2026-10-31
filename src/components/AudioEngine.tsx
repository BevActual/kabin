import { useEffect, useRef } from "react";
import {
  bindAudioElement,
  handleAudioEnded,
  handleAudioTime,
  useTransportStore,
} from "../store/transport";

export function AudioEngine() {
  const ref = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const onPlay = () => {
      const audio = useTransportStore.getState().audio;
      if (!audio || audio.playing) return;
      useTransportStore.setState({ audio: { ...audio, playing: true } });
    };
    const onPause = () => {
      const audio = useTransportStore.getState().audio;
      if (!audio || !audio.playing) return;
      useTransportStore.setState({ audio: { ...audio, playing: false } });
    };
    element.addEventListener("timeupdate", handleAudioTime);
    element.addEventListener("play", onPlay);
    element.addEventListener("pause", onPause);
    element.addEventListener("ended", handleAudioEnded);
    return () => {
      element.removeEventListener("timeupdate", handleAudioTime);
      element.removeEventListener("play", onPlay);
      element.removeEventListener("pause", onPause);
      element.removeEventListener("ended", handleAudioEnded);
    };
  }, []);

  return (
    <audio
      ref={(node) => {
        ref.current = node;
        bindAudioElement(node);
      }}
      preload="auto"
      className="kabin-audio-engine"
    />
  );
}
