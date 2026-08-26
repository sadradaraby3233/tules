// Recipe definitions
export const RECIPES = {
  cheetos: {
    name: 'Cheetos',
    machine: 'fryer',
    ingredients: {
      corn_meal: 2,
      cheese_powder: 1,
      oil: 1
    },
    time: 5,
    output: {
      itemId: 'cheetos',
      quantity: 1
    },
    xp: 10,
    level: 1
  },
  
  doritos: {
    name: 'Doritos',
    machine: 'fryer',
    ingredients: {
      corn_meal: 3,
      cheese_powder: 2,
      oil: 1
    },
    time: 6,
    output: {
      itemId: 'doritos',
      quantity: 1
    },
    xp: 15,
    level: 2
  },
  
  chips: {
    name: 'Potato Chips',
    machine: 'fryer',
    ingredients: {
      corn_meal: 1,
      oil: 1,
      salt: 1
    },
    time: 4,
    output: {
      itemId: 'chips',
      quantity: 1
    },
    xp: 8,
    level: 1
  }
};

export function getRecipesForMachine(machineId) {
  return Object.entries(RECIPES)
    .filter(([id, recipe]) => recipe.machine === machineId)
    .map(([id, recipe]) => ({ id, ...recipe }));
}

export function canCraft(recipeId, state) {
  const recipe = RECIPES[recipeId];
  if (!recipe) return false;
  
  // Check level
  if (state.player.level < recipe.level) return false;
  
  // Check ingredients
  for (const [itemId, quantity] of Object.entries(recipe.ingredients)) {
    if ((state.inventory[itemId] || 0) < quantity) {
      return false;
    }
  }
  
  return true;
}

export function craft(recipeId, state) {
  const recipe = RECIPES[recipeId];
  if (!recipe || !canCraft(recipeId, state)) return false;
  
  // Remove ingredients
  for (const [itemId, quantity] of Object.entries(recipe.ingredients)) {
    state.inventory[itemId] -= quantity;
    if (state.inventory[itemId] <= 0) {
      delete state.inventory[itemId];
    }
  }
  
  // Add output
  if (!state.inventory[recipe.output.itemId]) {
    state.inventory[recipe.output.itemId] = 0;
  }
  state.inventory[recipe.output.itemId] += recipe.output.quantity;
  
  return true;
}
