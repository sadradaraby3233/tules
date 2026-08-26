// Game state management
import { emit, EVENTS } from './events.js';

let state = {
  player: {
    x: 0,
    y: 0,
    room: 'lobby',
    facing: 0, // 0=north, 1=east, 2=south, 3=west
    level: 1,
    xp: 0,
    money: 50,
    energy: 100,
    morale: 80,
    title: 'New Recruit'
  },
  inventory: {},
  skills: {},
  quests: {
    active: [],
    completed: []
  },
  npcs: {},
  achievements: [],
  stats: {
    totalCrafts: 0,
    totalSales: 0,
    roomsVisited: [],
    npcsMet: []
  },
  settings: {
    masterVolume: 0.7,
    sfxVolume: 1.0,
    musicVolume: 0.3,
    speechVolume: 1.0,
    speechRate: 1.0,
    speechPitch: 1.0,
    preBlip: true,
    menuWrap: true
  },
  time: {
    day: 1,
    hour: 9,
    minute: 0,
    shiftStart: null
  }
};

export function getState() {
  return state;
}

export function setState(newState) {
  state = { ...state, ...newState };
}

export function getPlayer() {
  return state.player;
}

export function getInventory() {
  return state.inventory;
}

export function addItem(itemId, quantity = 1) {
  if (!state.inventory[itemId]) {
    state.inventory[itemId] = 0;
  }
  state.inventory[itemId] += quantity;
  emit(EVENTS.ITEM_PICKUP, { itemId, quantity });
}

export function removeItem(itemId, quantity = 1) {
  if (state.inventory[itemId]) {
    state.inventory[itemId] -= quantity;
    if (state.inventory[itemId] <= 0) {
      delete state.inventory[itemId];
    }
    return true;
  }
  return false;
}

export function hasItem(itemId, quantity = 1) {
  return (state.inventory[itemId] || 0) >= quantity;
}

export function addMoney(amount) {
  state.player.money += amount;
  emit(EVENTS.MONEY_CHANGE, { amount, total: state.player.money });
}

export function spendMoney(amount) {
  if (state.player.money >= amount) {
    state.player.money -= amount;
    emit(EVENTS.MONEY_CHANGE, { amount: -amount, total: state.player.money });
    return true;
  }
  return false;
}

export function addXp(amount) {
  state.player.xp += amount;
  const xpNeeded = getXpForLevel(state.player.level + 1);
  
  if (state.player.xp >= xpNeeded) {
    state.player.xp -= xpNeeded;
    state.player.level++;
    state.player.title = getTitleForLevel(state.player.level);
    emit(EVENTS.LEVEL_UP, { level: state.player.level, title: state.player.title });
  }
}

export function getXpForLevel(level) {
  return level * 100;
}

export function getTitleForLevel(level) {
  const titles = [
    'New Recruit',
    'Junior Worker',
    'Worker',
    'Senior Worker',
    'Team Lead',
    'Supervisor',
    'Manager',
    'Senior Manager',
    'Director',
    'Vice President',
    'CEO'
  ];
  return titles[Math.min(level - 1, titles.length - 1)];
}

export function addEnergy(amount) {
  state.player.energy = Math.max(0, Math.min(100, state.player.energy + amount));
  emit(EVENTS.ENERGY_CHANGE, { energy: state.player.energy });
}

export function addMorale(amount) {
  state.player.morale = Math.max(0, Math.min(100, state.player.morale + amount));
}

export function saveGame() {
  localStorage.setItem('cheetosco-save', JSON.stringify(state));
  emit(EVENTS.GAME_SAVE);
}

export function loadGame() {
  const saved = localStorage.getItem('cheetosco-save');
  if (saved) {
    state = JSON.parse(saved);
    emit(EVENTS.GAME_LOAD);
    return true;
  }
  return false;
}

export function hasSave() {
  return localStorage.getItem('cheetosco-save') !== null;
}

export function resetGame() {
  state = {
    player: {
      x: 0,
      y: 0,
      room: 'lobby',
      facing: 0,
      level: 1,
      xp: 0,
      money: 50,
      energy: 100,
      morale: 80,
      title: 'New Recruit'
    },
    inventory: {},
    skills: {},
    quests: {
      active: [],
      completed: []
    },
    npcs: {},
    achievements: [],
    stats: {
      totalCrafts: 0,
      totalSales: 0,
      roomsVisited: [],
      npcsMet: []
    },
    settings: state.settings, // Keep settings
    time: {
      day: 1,
      hour: 9,
      minute: 0,
      shiftStart: null
    }
  };
  localStorage.removeItem('cheetosco-save');
}
