// Sound definitions
export const SOUNDS = {
  // UI sounds
  blip: [
    { type: 'sine', frequency: 800, duration: 0.05, gain: 0.2, attack: 0.001, release: 0.04 }
  ],
  focus: [
    { type: 'sine', frequency: 600, duration: 0.08, gain: 0.15, attack: 0.002, release: 0.06 }
  ],
  select: [
    { type: 'sine', frequency: 523, duration: 0.06, gain: 0.2, attack: 0.001, release: 0.05 },
    { type: 'sine', frequency: 659, duration: 0.06, gain: 0.2, delay: 0.06, attack: 0.001, release: 0.05 }
  ],
  back: [
    { type: 'triangle', frequency: 400, frequencyEnd: 300, duration: 0.1, gain: 0.15, attack: 0.002, release: 0.08 }
  ],
  error: [
    { type: 'sawtooth', frequency: 150, duration: 0.15, gain: 0.2, attack: 0.005, release: 0.1, filter: { type: 'lowpass', frequency: 800 } }
  ],
  
  // Movement
  step: [
    { type: 'noise', duration: 0.08, gain: 0.1, filter: { type: 'bandpass', frequency: 400, q: 2 } }
  ],
  door_open: [
    { type: 'sine', frequency: 200, frequencyEnd: 400, duration: 0.3, gain: 0.15, attack: 0.05, release: 0.2 }
  ],
  
  // Items
  pickup: [
    { type: 'sine', frequency: 880, duration: 0.1, gain: 0.2, attack: 0.005, release: 0.08 },
    { type: 'sine', frequency: 1320, duration: 0.1, gain: 0.15, delay: 0.08, attack: 0.005, release: 0.08 }
  ],
  
  // Machines
  machine_start: [
    { type: 'sine', frequency: 100, frequencyEnd: 200, duration: 0.5, gain: 0.1, attack: 0.1, release: 0.3 }
  ],
  machine_run: [
    { type: 'sawtooth', frequency: 60, duration: 2.0, gain: 0.05, attack: 0.1, release: 0.5, filter: { type: 'lowpass', frequency: 300 } }
  ],
  machine_complete: [
    { type: 'sine', frequency: 523, duration: 0.15, gain: 0.2, attack: 0.01, release: 0.1 },
    { type: 'sine', frequency: 659, duration: 0.15, gain: 0.2, delay: 0.15, attack: 0.01, release: 0.1 },
    { type: 'sine', frequency: 784, duration: 0.2, gain: 0.25, delay: 0.3, attack: 0.01, release: 0.15 }
  ],
  
  // Money
  coin: [
    { type: 'sine', frequency: 2000, duration: 0.05, gain: 0.15, attack: 0.001, release: 0.04 },
    { type: 'sine', frequency: 2500, duration: 0.05, gain: 0.15, delay: 0.05, attack: 0.001, release: 0.04 }
  ],
  
  // Ambience
  lobby_ambience: [
    { type: 'sine', frequency: 80, duration: 4.0, gain: 0.02, attack: 0.5, release: 1.0, filter: { type: 'lowpass', frequency: 200 } }
  ],
  factory_ambience: [
    { type: 'sawtooth', frequency: 50, duration: 4.0, gain: 0.03, attack: 0.5, release: 1.0, filter: { type: 'lowpass', frequency: 150 } }
  ]
};
