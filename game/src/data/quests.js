// Quest definitions
import { addXp, addMoney } from '../core/state.js';

export const QUESTS = {
  first_day: {
    name: 'First Day on the Job',
    description: 'Get oriented at Cheetos Co.',
    objectives: [
      {
        type: 'visit_room',
        roomId: 'lobby',
        description: 'Enter the lobby',
        completed: false
      },
      {
        type: 'talk_to',
        npc: 'receptionist',
        description: 'Talk to the receptionist',
        completed: false
      },
      {
        type: 'visit_room',
        roomId: 'mixing',
        description: 'Visit the mixing room',
        completed: false
      }
    ],
    rewards: {
      xp: 50,
      money: 20
    }
  },
  
  production_training: {
    name: 'Production Training',
    description: 'Learn to make snacks',
    objectives: [
      {
        type: 'craft',
        recipeId: 'cheetos',
        quantity: 1,
        description: 'Make your first batch of Cheetos',
        completed: false
      },
      {
        type: 'craft',
        recipeId: 'chips',
        quantity: 2,
        description: 'Make 2 bags of potato chips',
        completed: false
      }
    ],
    rewards: {
      xp: 100,
      money: 50
    }
  }
};

export function getActiveQuests(state) {
  return QUESTS[state.quests.active] || null;
}

export function checkQuestCompletion(questId, state) {
  const quest = QUESTS[questId];
  if (!quest) return false;
  
  return quest.objectives.every(obj => obj.completed);
}

export function completeQuest(questId, state) {
  const quest = QUESTS[questId];
  if (!quest) return;
  
  // Give rewards
  if (quest.rewards.xp) addXp(quest.rewards.xp);
  if (quest.rewards.money) addMoney(quest.rewards.money);
  
  // Move to completed
  state.quests.completed.push(questId);
  state.quests.active = state.quests.active.filter(id => id !== questId);
}
