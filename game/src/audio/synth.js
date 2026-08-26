// Sound synthesis engine
import { getAudioContext, getSfxBus } from './context.js';

export function playSound(soundDef, options = {}) {
  const ctx = getAudioContext();
  if (!ctx || !soundDef) return;
  
  const output = options.output || getSfxBus();
  const startTime = ctx.currentTime + (options.delay || 0);
  
  for (const voice of soundDef) {
    playVoice(voice, startTime, output);
  }
}

function playVoice(voice, startTime, output) {
  const ctx = getAudioContext();
  if (!ctx) return;
  
  const duration = voice.duration || 0.1;
  const endTime = startTime + duration;
  
  // Create oscillator
  const osc = ctx.createOscillator();
  osc.type = voice.type || 'sine';
  
  // Frequency
  if (voice.frequency) {
    osc.frequency.setValueAtTime(voice.frequency, startTime);
    if (voice.frequencyEnd) {
      osc.frequency.exponentialRampToValueAtTime(voice.frequencyEnd, endTime);
    }
  }
  
  // Gain envelope
  const gain = ctx.createGain();
  const attack = voice.attack || 0.01;
  const release = voice.release || 0.1;
  const peakGain = voice.gain || 0.3;
  
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peakGain, startTime + attack);
  gain.gain.setValueAtTime(peakGain, endTime - release);
  gain.gain.linearRampToValueAtTime(0, endTime);
  
  // Filter
  if (voice.filter) {
    const filter = ctx.createBiquadFilter();
    filter.type = voice.filter.type || 'lowpass';
    filter.frequency.value = voice.filter.frequency || 1000;
    filter.Q.value = voice.filter.q || 1;
    
    osc.connect(filter);
    filter.connect(gain);
  } else {
    osc.connect(gain);
  }
  
  // Panning
  if (voice.pan !== undefined) {
    const panner = ctx.createStereoPanner();
    panner.pan.value = voice.pan;
    gain.connect(panner);
    panner.connect(output);
  } else {
    gain.connect(output);
  }
  
  osc.start(startTime);
  osc.stop(endTime + 0.1);
}

export function createNoise(duration, output) {
  const ctx = getAudioContext();
  if (!ctx) return;
  
  const bufferSize = ctx.sampleRate * duration;
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  
  for (let i = 0; i < bufferSize; i++) {
    data[i] = Math.random() * 2 - 1;
  }
  
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(output);
  source.start();
  
  return source;
}
