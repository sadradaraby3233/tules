// Settings menu with categories
import { openMenu, closeMenu } from './menu.js';
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { getState, saveGame } from '../core/state.js';
import { setMasterVolume, setSfxVolume, setMusicVolume, setSpeechVolume } from '../audio/context.js';
import { setSpeechRate, setSpeechPitch, setPreBlip } from '../audio/speech.js';
import { mainMenu } from './main-menu.js';

export function settingsMenu() {
  openMenu({
    title: 'Settings',
    items: [
      {
        label: 'General',
        onSelect: () => {
          playSound(SOUNDS.select);
          generalSettings();
        }
      },
      {
        label: 'Menus',
        onSelect: () => {
          playSound(SOUNDS.select);
          menusSettings();
        }
      },
      {
        label: 'Sound',
        onSelect: () => {
          playSound(SOUNDS.select);
          soundSettings();
        }
      },
      {
        label: 'Speech',
        onSelect: () => {
          playSound(SOUNDS.select);
          speechSettings();
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          playSound(SOUNDS.back);
          saveGame();
          mainMenu();
        }
      }
    ]
  });
}

function generalSettings() {
  const state = getState();
  
  openMenu({
    title: 'General Settings',
    items: [
      {
        label: 'Auto-save: ' + (state.settings.autoSave !== false ? 'On' : 'Off'),
        onSelect: () => {
          state.settings.autoSave = !state.settings.autoSave;
          say('Auto-save ' + (state.settings.autoSave ? 'enabled' : 'disabled'), { interrupt: true });
          generalSettings();
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          settingsMenu();
        }
      }
    ]
  });
}

function menusSettings() {
  const state = getState();
  
  openMenu({
    title: 'Menu Settings',
    items: [
      {
        label: 'Menu wrapping: ' + (state.settings.menuWrap ? 'On' : 'Off'),
        onSelect: () => {
          state.settings.menuWrap = !state.settings.menuWrap;
          say('Menu wrapping ' + (state.settings.menuWrap ? 'enabled' : 'disabled'), { interrupt: true });
          menusSettings();
        }
      },
      {
        label: 'Pre-speech blip: ' + (state.settings.preBlip ? 'On' : 'Off'),
        onSelect: () => {
          state.settings.preBlip = !state.settings.preBlip;
          setPreBlip(state.settings.preBlip);
          say('Pre-speech blip ' + (state.settings.preBlip ? 'enabled' : 'disabled'), { interrupt: true });
          menusSettings();
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          settingsMenu();
        }
      }
    ]
  });
}

function soundSettings() {
  const state = getState();
  
  openMenu({
    title: 'Sound Settings',
    items: [
      {
        label: 'Master volume: ' + Math.round(state.settings.masterVolume * 100) + '%',
        onSelect: () => {
          state.settings.masterVolume = Math.min(1.0, state.settings.masterVolume + 0.1);
          if (state.settings.masterVolume > 1.0) state.settings.masterVolume = 0.1;
          setMasterVolume(state.settings.masterVolume);
          playSound(SOUNDS.blip);
          soundSettings();
        }
      },
      {
        label: 'Sound effects: ' + Math.round(state.settings.sfxVolume * 100) + '%',
        onSelect: () => {
          state.settings.sfxVolume = Math.min(1.0, state.settings.sfxVolume + 0.1);
          if (state.settings.sfxVolume > 1.0) state.settings.sfxVolume = 0.1;
          setSfxVolume(state.settings.sfxVolume);
          playSound(SOUNDS.blip);
          soundSettings();
        }
      },
      {
        label: 'Music: ' + Math.round(state.settings.musicVolume * 100) + '%',
        onSelect: () => {
          state.settings.musicVolume = Math.min(1.0, state.settings.musicVolume + 0.1);
          if (state.settings.musicVolume > 1.0) state.settings.musicVolume = 0.1;
          setMusicVolume(state.settings.musicVolume);
          soundSettings();
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          settingsMenu();
        }
      }
    ]
  });
}

function speechSettings() {
  const state = getState();
  
  openMenu({
    title: 'Speech Settings',
    items: [
      {
        label: 'Speech volume: ' + Math.round(state.settings.speechVolume * 100) + '%',
        onSelect: () => {
          state.settings.speechVolume = Math.min(1.0, state.settings.speechVolume + 0.1);
          if (state.settings.speechVolume > 1.0) state.settings.speechVolume = 0.1;
          setSpeechVolume(state.settings.speechVolume);
          say('Volume adjusted', { interrupt: true });
          speechSettings();
        }
      },
      {
        label: 'Speech rate: ' + state.settings.speechRate.toFixed(1) + 'x',
        onSelect: () => {
          state.settings.speechRate = Math.min(2.0, state.settings.speechRate + 0.1);
          if (state.settings.speechRate > 2.0) state.settings.speechRate = 0.5;
          setSpeechRate(state.settings.speechRate);
          say('Rate adjusted', { interrupt: true });
          speechSettings();
        }
      },
      {
        label: 'Speech pitch: ' + state.settings.speechPitch.toFixed(1),
        onSelect: () => {
          state.settings.speechPitch = Math.min(2.0, state.settings.speechPitch + 0.1);
          if (state.settings.speechPitch > 2.0) state.settings.speechPitch = 0.5;
          setSpeechPitch(state.settings.speechPitch);
          say('Pitch adjusted', { interrupt: true });
          speechSettings();
        }
      },
      {
        label: 'Back',
        onSelect: () => {
          settingsMenu();
        }
      }
    ]
  });
}
