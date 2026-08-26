// Ambient music system
import { getAudioContext, getMusicBus } from './context.js';
import { playSound } from './synth.js';
import { MUSIC_TRACKS } from '../data/music.js';

let currentTrack = null;
let loopTimeout = null;
let isPlaying = false;

export const music = {
  play(trackName) {
    this.stop();
    
    const track = MUSIC_TRACKS[trackName];
    if (!track) return;
    
    currentTrack = track;
    isPlaying = true;
    playLoop();
  },
  
  stop() {
    isPlaying = false;
    if (loopTimeout) {
      clearTimeout(loopTimeout);
      loopTimeout = null;
    }
    currentTrack = null;
  },
  
  isPlaying() {
    return isPlaying;
  }
};

async function playLoop() {
  if (!isPlaying || !currentTrack) return;
  
  const track = currentTrack;
  
  // Play chord
  if (track.chord) {
    for (const note of track.chord) {
      playSound([
        {
          type: 'sine',
          frequency: note,
          duration: track.chordDuration || 4,
          gain: 0.05,
          attack: 1.0,
          release: 1.0
        }
      ]);
    }
  }
  
  // Play melody notes
  if (track.melody) {
    const noteDelay = (track.chordDuration || 4) / track.melody.length * 1000;
    
    track.melody.forEach((note, index) => {
      if (note > 0) {
        setTimeout(() => {
          if (!isPlaying) return;
          playSound([
            {
              type: 'triangle',
              frequency: note,
              duration: noteDelay / 1000 * 0.8,
              gain: 0.08,
              attack: 0.05,
              release: 0.2
            }
          ]);
        }, index * noteDelay);
      }
    });
  }
  
  // Schedule next loop
  const loopDuration = (track.chordDuration || 4) * 1000;
  loopTimeout = setTimeout(playLoop, loopDuration);
}
