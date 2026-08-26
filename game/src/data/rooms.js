// Room definitions
export const ROOMS = {
  lobby: {
    name: 'Lobby',
    description: 'The main entrance of Cheetos Co.',
    ambience: 'lobby_ambience',
    music: 'lobby',
    minX: 0, maxX: 5,
    minY: 0, maxY: 5,
    spawnX: 2, spawnY: 2,
    exits: [
      { x: 5, y: 2, to: 'hallway' }
    ]
  },
  
  hallway: {
    name: 'Main Hallway',
    description: 'A long corridor connecting different areas.',
    ambience: 'lobby_ambience',
    music: 'lobby',
    minX: 0, maxX: 10,
    minY: 0, maxY: 2,
    spawnX: 0, spawnY: 1,
    exits: [
      { x: 0, y: 1, to: 'lobby' },
      { x: 3, y: 0, to: 'mixing' },
      { x: 6, y: 0, to: 'cooking' },
      { x: 10, y: 1, to: 'warehouse' }
    ]
  },
  
  mixing: {
    name: 'Mixing Room',
    description: 'Where ingredients are combined.',
    ambience: 'factory_ambience',
    music: 'factory',
    minX: 0, maxX: 5,
    minY: 0, maxY: 5,
    spawnX: 2, spawnY: 5,
    exits: [
      { x: 2, y: 5, to: 'hallway' }
    ]
  },
  
  cooking: {
    name: 'Cooking Room',
    description: 'Where snacks are cooked to perfection.',
    ambience: 'factory_ambience',
    music: 'factory',
    minX: 0, maxX: 5,
    minY: 0, maxY: 5,
    spawnX: 2, spawnY: 5,
    exits: [
      { x: 2, y: 5, to: 'hallway' }
    ]
  },
  
  warehouse: {
    name: 'Warehouse',
    description: 'Storage area for finished products.',
    ambience: 'factory_ambience',
    music: 'factory',
    minX: 0, maxX: 8,
    minY: 0, maxY: 8,
    spawnX: 0, spawnY: 4,
    exits: [
      { x: 0, y: 4, to: 'hallway' }
    ]
  }
};

// Objects in the world
export const OBJECTS = [
  // Lobby
  {
    room: 'lobby',
    x: 1, y: 1,
    type: 'npc',
    npc: 'receptionist',
    description: 'The receptionist'
  },
  {
    room: 'lobby',
    x: 3, y: 1,
    type: 'sign',
    text: 'Welcome to Cheetos Co. - Where crunch meets innovation!'
  },
  
  // Hallway
  {
    room: 'hallway',
    x: 2, y: 1,
    type: 'npc',
    npc: 'janitor',
    description: 'A janitor cleaning the floors'
  },
  
  // Mixing Room
  {
    room: 'mixing',
    x: 2, y: 2,
    type: 'machine',
    machine: 'mixer',
    description: 'Industrial mixer for combining ingredients'
  },
  {
    room: 'mixing',
    x: 4, y: 3,
    type: 'container',
    description: 'Ingredient storage bins'
  },
  
  // Cooking Room
  {
    room: 'cooking',
    x: 2, y: 2,
    type: 'machine',
    machine: 'fryer',
    description: 'Deep fryer for cooking snacks'
  },
  {
    room: 'cooking',
    x: 2, y: 4,
    type: 'machine',
    machine: 'seasoner',
    description: 'Seasoning applicator'
  },
  
  // Warehouse
  {
    room: 'warehouse',
    x: 4, y: 4,
    type: 'container',
    description: 'Finished product storage'
  },
  {
    room: 'warehouse',
    x: 6, y: 2,
    type: 'item',
    itemId: 'cheetos',
    quantity: 5,
    description: 'A bag of cheetos'
  }
];
