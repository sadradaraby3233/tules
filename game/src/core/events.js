// Event bus for game systems
const listeners = new Map();

export function on(event, callback) {
  if (!listeners.has(event)) {
    listeners.set(event, new Set());
  }
  listeners.get(event).add(callback);
}

export function off(event, callback) {
  if (listeners.has(event)) {
    listeners.get(event).delete(callback);
  }
}

export function emit(event, data) {
  if (listeners.has(event)) {
    for (const callback of listeners.get(event)) {
      callback(data);
    }
  }
}

export const EVENTS = {
  ROOM_ENTER: 'room:enter',
  ROOM_EXIT: 'room:exit',
  ITEM_PICKUP: 'item:pickup',
  ITEM_USE: 'item:use',
  CRAFT_START: 'craft:start',
  CRAFT_COMPLETE: 'craft:complete',
  QUEST_UPDATE: 'quest:update',
  QUEST_COMPLETE: 'quest:complete',
  NPC_TALK: 'npc:talk',
  NPC_RELATION: 'npc:relation',
  LEVEL_UP: 'level:up',
  MONEY_CHANGE: 'money:change',
  ENERGY_CHANGE: 'energy:change',
  ACHIEVEMENT_UNLOCK: 'achievement:unlock',
  GAME_SAVE: 'game:save',
  GAME_LOAD: 'game:load',
  MENU_OPEN: 'menu:open',
  MENU_CLOSE: 'menu:close',
  TIME_TICK: 'time:tick'
};
