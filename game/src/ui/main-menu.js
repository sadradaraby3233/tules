// Main menu
import { openMenu, closeMenu } from './menu.js';
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { hasSave, loadGame, resetGame } from '../core/state.js';
import { settingsMenu } from './settings.js';
import { startGame } from '../game/game.js';
import { music } from '../audio/music.js';

export function mainMenu() {
  const hasSaveData = hasSave();
  
  const items = [
    {
      label: 'Start New Game',
      onSelect: () => {
        playSound(SOUNDS.select);
        resetGame();
        music.stop();
        startGame();
      }
    },
    {
      label: hasSaveData ? 'Continue Game' : 'Continue (No Save)',
      onSelect: () => {
        if (hasSaveData) {
          playSound(SOUNDS.select);
          loadGame();
          music.stop();
          startGame();
        } else {
          say('No save file found.', { interrupt: true });
        }
      }
    },
    {
      label: 'Test Speakers',
      onSelect: () => {
        playSound(SOUNDS.select);
        testSpeakers();
      }
    },
    {
      label: 'Settings',
      onSelect: () => {
        playSound(SOUNDS.select);
        settingsMenu();
      }
    },
    {
      label: 'How to Play',
      onSelect: () => {
        playSound(SOUNDS.select);
        howToPlay();
      }
    }
  ];
  
  openMenu({
    title: 'Cheetos Co.',
    items
  });
  
  setTimeout(() => {
    say('Main menu. Swipe to browse, double-tap to select.', { interrupt: true });
  }, 500);
}

function testSpeakers() {
  say('Testing speakers.', { interrupt: true });
  
  setTimeout(() => {
    playSound([
      { type: 'sine', frequency: 440, duration: 1.0, gain: 0.3, pan: -1 }
    ]);
    say('Left', { interrupt: false });
  }, 1500);
  
  setTimeout(() => {
    playSound([
      { type: 'sine', frequency: 440, duration: 1.0, gain: 0.3, pan: 0 }
    ]);
    say('Center', { interrupt: false });
  }, 3500);
  
  setTimeout(() => {
    playSound([
      { type: 'sine', frequency: 440, duration: 1.0, gain: 0.3, pan: 1 }
    ]);
    say('Right', { interrupt: false });
  }, 5500);
  
  setTimeout(() => {
    mainMenu();
  }, 7500);
}

function howToPlay() {
  openMenu({
    title: 'How to Play',
    items: [
      {
        label: 'Swipe up/down to navigate menus',
        onSelect: () => {
          say('Swipe up or down to move through menu options.', { interrupt: true });
        }
      },
      {
        label: 'Double-tap to select',
        onSelect: () => {
          say('Double-tap to choose an option.', { interrupt: true });
        }
      },
      {
        label: 'Single tap to repeat',
        onSelect: () => {
          say('Single tap to hear the current option again.', { interrupt: true });
        }
      },
      {
        label: 'Swipe left to go back',
        onSelect: () => {
          say('Swipe left to go back or close a menu.', { interrupt: true });
        }
      },
      {
        label: 'Walk into objects to interact',
        onSelect: () => {
          say('Use arrow keys or WASD to move. Walk into machines to craft, NPCs to talk.', { interrupt: true });
        }
      },
      {
        label: 'Press M for menu, I for inventory',
        onSelect: () => {
          say('Press M to open the game menu, I for your inventory.', { interrupt: true });
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          mainMenu();
        }
      }
    ]
  });
}
