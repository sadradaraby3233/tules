# Cheetos Co. - An Audio Adventure

A blind-accessible audio adventure game built entirely with HTML, CSS, and JavaScript. No visuals - everything is experienced through synthesized sounds and text-to-speech.

## Features

- **Pure Audio Experience**: No visuals required. All game elements are conveyed through procedural audio synthesis and speech.
- **Touch & Keyboard Controls**: Play on any device with intuitive gesture controls or keyboard navigation.
- **Data-Driven Architecture**: Easy to expand with new rooms, items, recipes, NPCs, and quests.
- **Save System**: Automatic and manual save support.
- **Customizable Settings**: Adjust volumes, speech rate, menu behavior, and more.

## Controls

### Touch
- **Swipe up/down**: Navigate menus
- **Swipe left**: Go back
- **Single tap**: Repeat current option
- **Double-tap**: Select option

### Keyboard
- **Arrow keys / WASD**: Move and navigate
- **Enter / Space**: Select
- **Escape / Backspace**: Go back
- **M**: Open game menu
- **I**: Open inventory
- **Tab**: Scan surroundings

## Game Systems

- **Crafting**: Combine ingredients at machines to create products
- **Quests**: Complete objectives to progress and earn rewards
- **Economy**: Earn money by crafting and selling products
- **Leveling**: Gain experience and unlock new abilities
- **NPCs**: Interact with characters throughout the factory

## Building

Requires Node.js 18+ and npm.

```bash
# Install dependencies
npm install

# Build single HTML file
npm run build

# Run development server
npm run dev
```

The build process creates a single `cheetosco.html` file that contains all CSS and JavaScript bundled together. This file can be opened directly in any modern web browser or deployed to any web server.

## Architecture

```
game/
├── src/
│   ├── audio/          # Audio synthesis and music
│   ├── core/           # Game state, input, events
│   ├── data/           # Game data (rooms, items, recipes, etc.)
│   ├── game/           # Game logic and player movement
│   ├── ui/             # Menu systems
│   └── main.js         # Entry point
├── index.html          # HTML template
├── styles.css          # Minimal styles
├── build.mjs           # Build script
└── package.json        # Dependencies
```

## Adding Content

### New Room
Add to `src/data/rooms.js`:
```javascript
export const ROOMS = {
  my_room: {
    name: 'My Room',
    description: 'A new room',
    ambience: 'factory_ambience',
    music: 'factory',
    minX: 0, maxX: 5,
    minY: 0, maxY: 5,
    spawnX: 2, spawnY: 2,
    exits: [
      { x: 5, y: 2, to: 'hallway' }
    ]
  }
};
```

### New Item
Add to `src/data/items.js`:
```javascript
export const ITEMS = {
  my_item: {
    name: 'My Item',
    description: 'A custom item',
    value: 10,
    stackable: true
  }
};
```

### New Recipe
Add to `src/data/recipes.js`:
```javascript
export const RECIPES = {
  my_recipe: {
    name: 'My Recipe',
    machine: 'fryer',
    ingredients: {
      corn_meal: 2,
      cheese_powder: 1
    },
    time: 5,
    output: {
      itemId: 'cheetos',
      quantity: 1
    },
    xp: 10,
    level: 1
  }
};
```

### New NPC
Add to `src/data/npcs.js`:
```javascript
export const NPCS = {
  my_npc: {
    name: 'My NPC',
    greeting: 'Hello there!',
    dialogue: [
      { text: 'Welcome to the factory.' },
      { choices: [
        { text: 'Tell me more', action: () => {} },
        { text: 'Goodbye', action: () => {} }
      ]}
    ]
  }
};
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers with Web Audio API support

## License

MIT

## Credits

Created as a demonstration of accessible game design using web technologies.
