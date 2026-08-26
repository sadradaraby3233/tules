// Game menu (accessible during gameplay)
import { openMenu, closeMenu } from './menu.js';
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { getState, saveGame } from '../core/state.js';
import { settingsMenu } from './settings.js';
import { inventoryMenu } from './inventory.js';
import { mainMenu } from './main-menu.js';
import { music } from '../audio/music.js';
import { QUESTS } from '../data/quests.js';

export function gameMenu() {
  const state = getState();
  
  openMenu({
    title: 'Game Menu',
    items: [
      {
        label: 'Status',
        onSelect: () => {
          playSound(SOUNDS.select);
          statusMenu();
        }
      },
      {
        label: 'Inventory',
        onSelect: () => {
          playSound(SOUNDS.select);
          inventoryMenu();
        }
      },
      {
        label: 'Quests',
        onSelect: () => {
          playSound(SOUNDS.select);
          questsMenu();
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
        label: 'Save Game',
        onSelect: () => {
          saveGame();
          playSound(SOUNDS.select);
          say('Game saved', { interrupt: true });
        }
      },
      {
        label: 'Main Menu',
        onSelect: () => {
          playSound(SOUNDS.select);
          confirmMainMenu();
        }
      }
    ]
  });
}

function statusMenu() {
  const state = getState();
  const player = state.player;
  
  openMenu({
    title: 'Status',
    items: [
      { label: 'Level: ' + player.level, onSelect: () => statusMenu() },
      { label: 'Title: ' + player.title, onSelect: () => statusMenu() },
      { label: 'Money: $' + player.money, onSelect: () => statusMenu() },
      { label: 'Energy: ' + Math.round(player.energy) + '%', onSelect: () => statusMenu() },
      { label: 'Morale: ' + Math.round(player.morale) + '%', onSelect: () => statusMenu() },
      { label: 'Back', onSelect: () => gameMenu() }
    ]
  });
}

function questsMenu() {
  const state = getState();
  
  const activeQuests = state.quests.active.map(id => ({
    label: QUESTS[id].name,
    onSelect: () => {
      playSound(SOUNDS.select);
      questDetails(id);
    }
  }));
  
  if (activeQuests.length === 0) {
    activeQuests.push({
      label: 'No active quests',
      onSelect: () => questsMenu()
    });
  }
  
  activeQuests.push({
    label: 'Back',
    onSelect: () => gameMenu()
  });
  
  openMenu({
    title: 'Active Quests',
    items: activeQuests
  });
}

function questDetails(questId) {
  const quest = QUESTS[questId];
  
  const items = quest.objectives.map(obj => ({
    label: (obj.completed ? '✓ ' : '○ ') + obj.description,
    onSelect: () => questDetails(questId)
  }));
  
  items.push({
    label: 'Back',
    onSelect: () => questsMenu()
  });
  
  openMenu({
    title: quest.name,
    items
  });
}

function confirmMainMenu() {
  openMenu({
    title: 'Return to Main Menu?',
    items: [
      {
        label: 'Yes (unsaved progress will be lost)',
        onSelect: () => {
          playSound(SOUNDS.select);
          music.play('menu');
          mainMenu();
        }
      },
      {
        label: 'No',
        onSelect: () => {
          gameMenu();
        }
      }
    ]
  });
}
