import { coverUrl } from "./kabin-api";

let toneUrl: string | null = null;

function previewToneUrl() {
  if (toneUrl) return toneUrl;
  const sampleRate = 8000;
  const seconds = 30;
  const samples = sampleRate * seconds;
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i += 1) {
    const sample = Math.sin((2 * Math.PI * 220 * i) / sampleRate) * 0.12;
    view.setInt16(44 + i * 2, sample * 0x7fff, true);
  }
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  toneUrl = `data:audio/wav;base64,${btoa(binary)}`;
  return toneUrl;
}

export function mediaSrc(path?: string | null) {
  if (!path) return null;
  if (path.startsWith("preview:")) return previewToneUrl();
  return coverUrl(path);
}
