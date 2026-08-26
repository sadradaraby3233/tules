// 3D positional audio
import { getAudioContext, getSfxBus } from './context.js';
import { playSound } from './synth.js';

export function playSoundAt(soundDef, x, y, listenerX, listenerY, listenerAngle) {
  const ctx = getAudioContext();
  if (!ctx || !soundDef) return;
  
  // Calculate distance and angle
  const dx = x - listenerX;
  const dy = y - listenerY;
  const distance = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx) - listenerAngle;
  
  // Calculate pan (-1 to 1)
  const pan = Math.sin(angle);
  
  // Calculate volume based on distance (inverse square law)
  const maxDistance = 10;
  const volume = Math.max(0, 1 - (distance / maxDistance));
  
  // Play with position
  const output = createPannedOutput(pan, volume);
  
  playSound(soundDef, { output });
}

function createPannedOutput(pan, volume) {
  const ctx = getAudioContext();
  if (!ctx) return getSfxBus();
  
  const gain = ctx.createGain();
  gain.gain.value = volume;
  
  const panner = ctx.createStereoPanner();
  panner.pan.value = pan;
  
  gain.connect(panner);
  panner.connect(getSfxBus());
  
  return gain;
}
