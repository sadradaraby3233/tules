// Menu system - gesture-driven, audio-only
import { say, cancelSpeech } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { onAction } from '../core/actions.js';
import { getState } from '../core/state.js';
import { emit, EVENTS } from '../core/events.js';

let currentMenu = null;
let menuStack = [];
let selectedIndex = 0;
let gestureCleanup = [];

export function initMenus() {
  // Menus are initialized, ready to use
}

export function openMenu(menu) {
  cancelSpeech();
  playSound(SOUNDS.focus);
  
  // Push current menu to stack
  if (currentMenu) {
    menuStack.push({ menu: currentMenu, index: selectedIndex });
  }
  
  currentMenu = menu;
  selectedIndex = 0;
  
  bindGestures();
  speakCurrent();
  
  emit(EVENTS.MENU_OPEN, { menu });
}

export function closeMenu() {
  if (menuStack.length > 0) {
    // Pop from stack
    const { menu, index } = menuStack.pop();
    currentMenu = menu;
    selectedIndex = index;
    speakCurrent();
  } else {
    currentMenu = null;
    selectedIndex = 0;
    unbindGestures();
  }
  
  playSound(SOUNDS.back);
  emit(EVENTS.MENU_CLOSE);
}

export function isMenuOpen() {
  return currentMenu !== null;
}

function bindGestures() {
  unbindGestures();
  
  const cleanups = [
    onAction('up', moveUp),
    onAction('down', moveDown),
    onAction('swipe-up', moveUp),
    onAction('swipe-down', moveDown),
    onAction('swipe-left', goBack),
    onAction('back', goBack),
    onAction('tap', repeatCurrent),
    onAction('double-tap', selectCurrent),
    onAction('select', selectCurrent)
  ];
  
  gestureCleanup = cleanups;
}

function unbindGestures() {
  for (const cleanup of gestureCleanup) {
    cleanup();
  }
  gestureCleanup = [];
}

function moveUp() {
  if (!currentMenu) return;
  
  const items = currentMenu.items;
  const wrap = getState().settings.menuWrap;
  
  if (wrap) {
    selectedIndex = (selectedIndex - 1 + items.length) % items.length;
  } else {
    if (selectedIndex > 0) {
      selectedIndex--;
    }
  }
  
  speakCurrent();
}

function moveDown() {
  if (!currentMenu) return;
  
  const items = currentMenu.items;
  const wrap = getState().settings.menuWrap;
  
  if (wrap) {
    selectedIndex = (selectedIndex + 1) % items.length;
  } else {
    if (selectedIndex < items.length - 1) {
      selectedIndex++;
    }
  }
  
  speakCurrent();
}

function selectCurrent() {
  if (!currentMenu) return;
  
  const item = currentMenu.items[selectedIndex];
  if (item && item.onSelect) {
    playSound(SOUNDS.select);
    cancelSpeech();
    item.onSelect();
  }
}

function repeatCurrent() {
  if (!currentMenu) return;
  speakCurrent();
}

function goBack() {
  if (currentMenu && currentMenu.onBack) {
    playSound(SOUNDS.back);
    currentMenu.onBack();
  } else {
    closeMenu();
  }
}

function speakCurrent() {
  if (!currentMenu) return;
  
  const item = currentMenu.items[selectedIndex];
  if (item) {
    say(item.label, { interrupt: true, blip: 'focus' });
  }
}
