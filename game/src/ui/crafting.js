// Crafting menu
import { openMenu, closeMenu } from './menu.js';
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { getState, addXp } from '../core/state.js';
import { emit, EVENTS } from '../core/events.js';
import { getRecipesForMachine, canCraft, craft, RECIPES } from '../data/recipes.js';
import { ITEMS } from '../data/items.js';

let craftingInProgress = false;

export function openCraftingMenu(machineObj) {
  const machineId = machineObj.machine;
  const recipes = getRecipesForMachine(machineId);
  const state = getState();
  
  const menuItems = recipes.map(recipe => {
    const craftable = canCraft(recipe.id, state);
    const ingredientList = Object.entries(recipe.ingredients)
      .map(([id, qty]) => {
        const item = ITEMS[id];
        const have = state.inventory[id] || 0;
        const status = have >= qty ? '✓' : '✗';
        return `${qty} ${item?.name || id} (${have}) ${status}`;
      })
      .join(', ');
    
    return {
      label: recipe.name + (craftable ? '' : ' (missing ingredients)'),
      onSelect: () => {
        if (craftable) {
          playSound(SOUNDS.select);
          startCrafting(recipe, machineObj);
        } else {
          say('Missing ingredients: ' + ingredientList, { interrupt: true });
        }
      }
    };
  });
  
  menuItems.push({
    label: 'Back',
    onSelect: () => {
      playSound(SOUNDS.back);
      closeMenu();
    }
  });
  
  openMenu({
    title: machineObj.description || 'Machine',
    items: menuItems
  });
}

function startCrafting(recipe, machineObj) {
  closeMenu();
  
  const state = getState();
  craftingInProgress = true;
  
  // Start machine sound
  playSound(SOUNDS.machine_start);
  
  setTimeout(() => {
    playSound(SOUNDS.machine_run);
  }, 500);
  
  // Craft the item
  const success = craft(recipe.id, state);
  
  setTimeout(() => {
    craftingInProgress = false;
    
    if (success) {
      playSound(SOUNDS.machine_complete);
      
      const outputItem = ITEMS[recipe.output.itemId];
      const quantity = recipe.output.quantity;
      
      say(`Crafted ${quantity} ${outputItem?.name || recipe.output.itemId}`, { interrupt: true });
      
      emit(EVENTS.CRAFT_COMPLETE, {
        recipeId: recipe.id,
        output: recipe.output
      });
      
      state.stats.totalCrafts++;
    } else {
      playSound(SOUNDS.error);
      say('Crafting failed', { interrupt: true });
    }
  }, recipe.time * 1000);
}

export function isCraftingInProgress() {
  return craftingInProgress;
}
