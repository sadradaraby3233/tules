// Player movement and interaction
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { getPlayer, setState, addItem } from '../core/state.js';
import { emit, EVENTS } from '../core/events.js';
import { ROOMS, OBJECTS } from '../data/rooms.js';
import { ITEMS } from '../data/items.js';
import { NPCS } from '../data/npcs.js';
import { startDialogue } from '../core/dialogue.js';
import { openCraftingMenu } from '../ui/crafting.js';

export function enterRoom(roomId) {
  const room = ROOMS[roomId];
  if (!room) return;
  
  const player = getPlayer();
  player.room = roomId;
  player.x = room.spawnX || 0;
  player.y = room.spawnY || 0;
  
  // Play room ambience
  if (room.ambience) {
    playSound(SOUNDS[room.ambience]);
  }
  
  emit(EVENTS.ROOM_ENTER, { roomId, room });
}

export function movePlayer(direction) {
  const player = getPlayer();
  const room = ROOMS[player.room];
  
  // Update facing
  player.facing = direction;
  
  // Calculate new position
  const dx = [0, 1, 0, -1][direction];
  const dy = [-1, 0, 1, 0][direction];
  const newX = player.x + dx;
  const newY = player.y + dy;
  
  // Check for room transition
  if (room.exits) {
    for (const exit of room.exits) {
      if (exit.x === newX && exit.y === newY) {
        // Transition to new room
        playSound(SOUNDS.door_open);
        enterRoom(exit.to);
        say('Entered ' + ROOMS[exit.to].name, { interrupt: true });
        return;
      }
    }
  }
  
  // Check bounds
  if (newX >= room.minX && newX <= room.maxX && newY >= room.minY && newY <= room.maxY) {
    player.x = newX;
    player.y = newY;
    
    // Play step sound
    playSound(SOUNDS.step);
    
    // Check for objects at new position
    checkObjectAtPosition(newX, newY);
  } else {
    // Can't move
    playSound(SOUNDS.error);
  }
}

export function interact() {
  const player = getPlayer();
  const room = ROOMS[player.room];
  
  // Check facing direction for objects
  const dx = [0, 1, 0, -1][player.facing];
  const dy = [-1, 0, 1, 0][player.facing];
  const targetX = player.x + dx;
  const targetY = player.y + dy;
  
  // Find object in front
  const objects = OBJECTS.filter(obj => 
    obj.room === player.room && 
    obj.x === targetX && 
    obj.y === targetY
  );
  
  if (objects.length > 0) {
    const obj = objects[0];
    handleObjectInteraction(obj);
  } else {
    say('Nothing to interact with', { interrupt: true });
    playSound(SOUNDS.error);
  }
}

function checkObjectAtPosition(x, y) {
  const player = getPlayer();
  const objects = OBJECTS.filter(obj => 
    obj.room === player.room && 
    obj.x === x && 
    obj.y === y
  );
  
  for (const obj of objects) {
    if (obj.type === 'item') {
      // Auto-pickup items
      pickupItem(obj);
    } else if (obj.type === 'sign') {
      // Read signs
      say(obj.text, { interrupt: true });
    }
  }
}

function handleObjectInteraction(obj) {
  switch (obj.type) {
    case 'machine':
      openCraftingMenu(obj);
      break;
      
    case 'npc':
      const npc = NPCS[obj.npc];
      if (npc) {
        say(npc.greeting || 'Hello!', { interrupt: true });
        if (npc.dialogue) {
          setTimeout(() => startDialogue(npc.dialogue), 1500);
        }
      }
      break;
      
    case 'container':
      say('A container. ' + (obj.description || ''), { interrupt: true });
      break;
      
    case 'shop':
      say('A shop. ' + (obj.description || ''), { interrupt: true });
      break;
      
    case 'item':
      pickupItem(obj);
      break;
      
    default:
      say(obj.description || 'An object', { interrupt: true });
  }
}

function pickupItem(obj) {
  if (obj.itemId) {
    const item = ITEMS[obj.itemId];
    if (item) {
      addItem(obj.itemId, obj.quantity || 1);
      say('Picked up ' + (item.name || obj.itemId), { interrupt: true });
      playSound(SOUNDS.pickup);
      
      // Remove object from world
      const index = OBJECTS.indexOf(obj);
      if (index > -1) {
        OBJECTS.splice(index, 1);
      }
    }
  }
}
