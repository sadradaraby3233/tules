// Audio context management
let audioContext = null;
let masterGain = null;
let sfxBus = null;
let musicBus = null;
let speechBus = null;
let reverbNode = null;
let reverbSend = null;

export async function initAudio() {
  if (audioContext) return;
  
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  
  // Master gain
  masterGain = audioContext.createGain();
  masterGain.gain.value = 0.7;
  masterGain.connect(audioContext.destination);
  
  // Effect buses
  sfxBus = audioContext.createGain();
  sfxBus.gain.value = 1.0;
  sfxBus.connect(masterGain);
  
  musicBus = audioContext.createGain();
  musicBus.gain.value = 0.3;
  musicBus.connect(masterGain);
  
  speechBus = audioContext.createGain();
  speechBus.gain.value = 1.0;
  speechBus.connect(masterGain);
  
  // Reverb
  reverbNode = audioContext.createConvolver();
  reverbNode.buffer = await createReverbIR(2.5, 3.0);
  reverbSend = audioContext.createGain();
  reverbSend.gain.value = 0.2;
  reverbSend.connect(reverbNode);
  reverbNode.connect(masterGain);
  
  // Resume if suspended
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }
}

async function createReverbIR(duration, decay) {
  const sampleRate = audioContext.sampleRate;
  const length = sampleRate * duration;
  const impulse = audioContext.createBuffer(2, length, sampleRate);
  
  for (let channel = 0; channel < 2; channel++) {
    const channelData = impulse.getChannelData(channel);
    for (let i = 0; i < length; i++) {
      channelData[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
    }
  }
  
  return impulse;
}

export function getAudioContext() {
  return audioContext;
}

export function getSfxBus() {
  return sfxBus;
}

export function getMusicBus() {
  return musicBus;
}

export function getSpeechBus() {
  return speechBus;
}

export function setMasterVolume(value) {
  if (masterGain) {
    masterGain.gain.value = value;
  }
}

export function setSfxVolume(value) {
  if (sfxBus) {
    sfxBus.gain.value = value;
  }
}

export function setMusicVolume(value) {
  if (musicBus) {
    musicBus.gain.value = value;
  }
}

export function setSpeechVolume(value) {
  if (speechBus) {
    speechBus.gain.value = value;
  }
}
