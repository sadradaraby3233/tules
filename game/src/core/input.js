// Touch gesture and keyboard input system
import { onAction } from './actions.js';

const SWIPE_THRESHOLD = 50;
const DOUBLE_TAP_DELAY = 300;
const HOLD_THRESHOLD = 500;

let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;
let lastTapTime = 0;
let holdTimeout = null;

export function initInput() {
  // Touch events
  document.addEventListener('touchstart', handleTouchStart, { passive: false });
  document.addEventListener('touchend', handleTouchEnd, { passive: false });
  
  // Keyboard events
  document.addEventListener('keydown', handleKeyDown);
  document.addEventListener('keyup', handleKeyUp);
}

function handleTouchStart(e) {
  e.preventDefault();
  const touch = e.touches[0];
  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
  touchStartTime = Date.now();
  
  // Start hold detection
  holdTimeout = setTimeout(() => {
    onAction('hold');
  }, HOLD_THRESHOLD);
}

function handleTouchEnd(e) {
  e.preventDefault();
  
  if (holdTimeout) {
    clearTimeout(holdTimeout);
    holdTimeout = null;
  }
  
  const touch = e.changedTouches[0];
  const deltaX = touch.clientX - touchStartX;
  const deltaY = touch.clientY - touchStartY;
  const deltaTime = Date.now() - touchStartTime;
  
  // Check if it's a swipe
  if (Math.abs(deltaX) > SWIPE_THRESHOLD || Math.abs(deltaY) > SWIPE_THRESHOLD) {
    if (Math.abs(deltaX) > Math.abs(deltaY)) {
      // Horizontal swipe
      if (deltaX > 0) {
        onAction('swipe-right');
      } else {
        onAction('swipe-left');
      }
    } else {
      // Vertical swipe
      if (deltaY > 0) {
        onAction('swipe-down');
      } else {
        onAction('swipe-up');
      }
    }
    return;
  }
  
  // Check if it's a tap or double-tap
  const currentTime = Date.now();
  if (currentTime - lastTapTime < DOUBLE_TAP_DELAY) {
    // Double-tap
    onAction('double-tap');
    lastTapTime = 0;
  } else {
    // Single tap (will be confirmed if no second tap comes)
    setTimeout(() => {
      if (lastTapTime !== 0) {
        onAction('tap');
        lastTapTime = currentTime;
      }
    }, DOUBLE_TAP_DELAY);
  }
}

function handleKeyDown(e) {
  switch(e.key) {
    case 'ArrowUp':
    case 'w':
    case 'W':
      e.preventDefault();
      onAction('up');
      break;
    case 'ArrowDown':
    case 's':
    case 'S':
      e.preventDefault();
      onAction('down');
      break;
    case 'ArrowLeft':
    case 'a':
    case 'A':
      e.preventDefault();
      onAction('left');
      break;
    case 'ArrowRight':
    case 'd':
    case 'D':
      e.preventDefault();
      onAction('right');
      break;
    case 'Enter':
    case ' ':
      e.preventDefault();
      onAction('select');
      break;
    case 'Escape':
    case 'Backspace':
      e.preventDefault();
      onAction('back');
      break;
    case 'm':
    case 'M':
      e.preventDefault();
      onAction('menu');
      break;
    case 'i':
    case 'I':
      e.preventDefault();
      onAction('inventory');
      break;
    case 'Tab':
      e.preventDefault();
      onAction('scan');
      break;
  }
}

function handleKeyUp(e) {
  // Reserved for future hold-release mechanics
}
