// Action system - maps gestures to game actions
const actionHandlers = new Map();

export function onAction(action, handler) {
  if (!actionHandlers.has(action)) {
    actionHandlers.set(action, new Set());
  }
  actionHandlers.get(action).add(handler);
  
  // Return cleanup function
  return () => {
    actionHandlers.get(action).delete(handler);
  };
}

export function clearActions() {
  actionHandlers.clear();
}

export function fireAction(action, data) {
  const handlers = actionHandlers.get(action);
  if (handlers) {
    for (const handler of handlers) {
      handler(data);
    }
  }
}
