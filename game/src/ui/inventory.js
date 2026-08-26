// Inventory menu
import { openMenu, closeMenu } from './menu.js';
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { getState, getInventory } from '../core/state.js';
import { ITEMS } from '../data/items.js';
import { gameMenu } from './game-menu.js';

export function inventoryMenu() {
  const inventory = getInventory();
  const items = Object.entries(inventory);
  
  if (items.length === 0) {
    openMenu({
      title: 'Inventory',
      items: [
        { label: 'Inventory is empty', onSelect: () => inventoryMenu() },
        { label: 'Back', onSelect: () => gameMenu() }
      ]
    });
    return;
  }
  
  const menuItems = items.map(([itemId, quantity]) => {
    const item = ITEMS[itemId];
    const name = item ? item.name : itemId;
    
    return {
      label: `${name} x${quantity}`,
      onSelect: () => {
        playSound(SOUNDS.select);
        itemDetails(itemId, quantity);
      }
    };
  });
  
  menuItems.push({
    label: 'Back',
    onSelect: () => {
      playSound(SOUNDS.back);
      gameMenu();
    }
  });
  
  openMenu({
    title: 'Inventory',
    items: menuItems
  });
}

function itemDetails(itemId, quantity) {
  const item = ITEMS[itemId];
  
  const menuItems = [
    { label: item.name, onSelect: () => itemDetails(itemId, quantity) },
    { label: item.description, onSelect: () => itemDetails(itemId, quantity) },
    { label: 'Quantity: ' + quantity, onSelect: () => itemDetails(itemId, quantity) },
    { label: 'Value: $' + item.value, onSelect: () => itemDetails(itemId, quantity) }
  ];
  
  // Add use/drop options if applicable
  if (item.usable) {
    menuItems.push({
      label: 'Use',
      onSelect: () => {
        playSound(SOUNDS.select);
        say('Cannot use this item here', { interrupt: true });
        itemDetails(itemId, quantity);
      }
    });
  }
  
  menuItems.push({
    label: 'Back',
    onSelect: () => {
      playSound(SOUNDS.back);
      inventoryMenu();
    }
  });
  
  openMenu({
    title: 'Item Details',
    items: menuItems
  });
}
