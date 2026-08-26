// Main game logic
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { music } from '../audio/music.js';
import { getState, getPlayer, saveGame } from '../core/state.js';
import { onAction } from '../core/actions.js';
import { emit, EVENTS } from '../core/events.js';
import { ROOMS } from '../data/rooms.js';
import { enterRoom, movePlayer, interact } from './player.js';
import { gameMenu } from '../ui/game-menu.js';
import { inventoryMenu } from '../ui/inventory.js';

let gameLoop = null;
let autoSaveInterval = null;

export function startGame() {
  const player = getPlayer();
  
  // Enter starting room
  enterRoom(player.room);
  
  // Bind game actions
  bindGameActions();
  
  // Start game loop
  startGameLoop();
  
  // Start auto-save
  startAutoSave();
  
  // Welcome message
  setTimeout(() => {
    say('Welcome to Cheetos Co. You are in the ' + ROOMS[player.room].name + '.', { interrupt: true });
    setTimeout(() => {
      say('Use arrow keys or WASD to move. Walk into objects to interact. Press M for menu.', { interrupt: true });
    }, 2000);
  }, 500);
}

function bindGameActions() {
  onAction('up', () => movePlayer(0));
  onAction('down', () => movePlayer(2));
  onAction('left', () => movePlayer(3));
  onAction('right', () => movePlayer(1));
  onAction('swipe-up', () => movePlayer(0));
  onAction('swipe-down', () => movePlayer(2));
  onAction('swipe-left', () => movePlayer(3));
  onAction('swipe-right', () => movePlayer(1));
  onAction('tap', () => interact());
  onAction('menu', () => gameMenu());
  onAction('inventory', () => inventoryMenu());
}

function startGameLoop() {
  let lastTime = Date.now();
  
  gameLoop = setInterval(() => {
    const now = Date.now();
    const delta = (now - lastTime) / 1000;
    lastTime = now;
    
    updateGame(delta);
  }, 100);
}

function updateGame(delta) {
  const state = getState();
  
  // Update time
  state.time.minute += delta * 10; // 10 game minutes per real second
  if (state.time.minute >= 60) {
    state.time.minute = 0;
    state.time.hour++;
    
    if (state.time.hour >= 24) {
      state.time.hour = 0;
      state.time.day++;
    }
    
    emit(EVENTS.TIME_TICK, { hour: state.time.hour, day: state.time.day });
  }
  
  // Energy drain
  if (state.player.energy > 0) {
    state.player.energy -= delta * 0.1;
    if (state.player.energy < 0) state.player.energy = 0;
  }
}

function startAutoSave() {
  const state = getState();
  if (state.settings.autoSave !== false) {
    autoSaveInterval = setInterval(() => {
      saveGame();
      say('Game saved', { interrupt: false });
    }, 60000); // Save every minute
  }
}

export function stopGame() {
  if (gameLoop) {
    clearInterval(gameLoop);
    gameLoop = null;
  }
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval);
    autoSaveInterval = null;
  }
}
