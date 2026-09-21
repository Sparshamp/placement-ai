// Uncomment this to use edge TTS for TTS and remove next part after this
// src/features/interview-simulation/hooks/useSpeak.js
/*import { interviewApi } from "../api";

let currentAudio = null;

export async function speak(text) {
  if (!text) return;
  stopSpeaking();
  try {
    const audioBlob = await interviewApi.synthesizeSpeech(text);
    const url = URL.createObjectURL(audioBlob);
    currentAudio = new Audio(url);
    await currentAudio.play();
  } catch (err) {
    console.error("TTS playback failed", err);
  }
}

export function stopSpeaking() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
}*/

// src/features/interview-simulation/hooks/useSpeak.js
export function speak(text) {
  return new Promise((resolve) => {
    if (!text || !window.speechSynthesis) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

export function stopSpeaking() {
  window.speechSynthesis?.cancel();
}