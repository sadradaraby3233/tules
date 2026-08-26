// Text-to-speech with queue and interruption
import { getSpeechBus } from './context.js';

let currentUtterance = null;
let speechQueue = [];
let isSpeaking = false;
let preBlipEnabled = true;
let speechRate = 1.0;
let speechPitch = 1.0;
let speechVolume = 1.0;

export function say(text, options = {}) {
  if (!text) return;
  
  const interrupt = options.interrupt !== false;
  
  if (interrupt) {
    // Cancel current speech
    cancelSpeech();
    speechQueue = [];
  }
  
  speechQueue.push({ text, options });
  processQueue();
}

async function processQueue() {
  if (isSpeaking || speechQueue.length === 0) return;
  
  isSpeaking = true;
  const { text, options } = speechQueue.shift();
  
  // Pre-blip
  if (preBlipEnabled && options.blip !== false) {
    const { playSound } = await import('./synth.js');
    const { SOUNDS } = await import('../data/sounds.js');
    playSound(SOUNDS.blip);
    await sleep(100);
  }
  
  // Speak
  if ('speechSynthesis' in window) {
    currentUtterance = new SpeechSynthesisUtterance(text);
    currentUtterance.rate = speechRate;
    currentUtterance.pitch = speechPitch;
    currentUtterance.volume = speechVolume;
    
    currentUtterance.onend = () => {
      isSpeaking = false;
      currentUtterance = null;
      setTimeout(processQueue, 50);
    };
    
    currentUtterance.onerror = () => {
      isSpeaking = false;
      currentUtterance = null;
      setTimeout(processQueue, 50);
    };
    
    window.speechSynthesis.speak(currentUtterance);
  }
}

export function cancelSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  isSpeaking = false;
  currentUtterance = null;
}

export function setPreBlip(enabled) {
  preBlipEnabled = enabled;
}

export function setSpeechRate(rate) {
  speechRate = rate;
}

export function setSpeechPitch(pitch) {
  speechPitch = pitch;
}

export function setSpeechVolume(volume) {
  speechVolume = volume;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
