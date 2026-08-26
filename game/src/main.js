// Main entry point
import { initAudio } from './audio/context.js';
import { initInput } from './core/input.js';
import { initMenus } from './ui/menu.js';
import { say } from './audio/speech.js';
import { playSound } from './audio/synth.js';
import { SOUNDS } from './data/sounds.js';
import { music } from './audio/music.js';
import { mainMenu } from './ui/main-menu.js';

let initialized = false;

async function init() {
  if (initialized) return;
  initialized = true;
  
  try {
    await initAudio();
    initInput();
    initMenus();
    
    // Start ambient music
    music.play('menu');
    
    // Welcome message
    setTimeout(() => {
      say('Welcome to Cheetos Company. Swipe up and down to browse. Double-tap to select.', { interrupt: true });
      mainMenu();
    }, 500);
    
    // Hide gate
    document.getElementById('gate').style.display = 'none';
  } catch (error) {
    console.error('Initialization failed:', error);
    say('Error starting game. Please refresh.', { interrupt: true });
  }
}

// Boot on first interaction
function boot(e) {
  if (initialized) return;
  e.preventDefault();
  init();
}

document.addEventListener('touchstart', boot, { passive: false, once: true });
document.addEventListener('click', boot, { once: true });
document.addEventListener('keydown', boot, { once: true });
