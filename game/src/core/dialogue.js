// Dialogue system for NPC conversations
import { say } from '../audio/speech.js';
import { playSound } from '../audio/synth.js';
import { SOUNDS } from '../data/sounds.js';
import { openMenu, closeMenu } from '../ui/menu.js';
import { fireAction } from './actions.js';

let currentDialogue = null;
let dialogueIndex = 0;

export function startDialogue(dialogue) {
  currentDialogue = dialogue;
  dialogueIndex = 0;
  advanceDialogue();
}

function advanceDialogue() {
  if (!currentDialogue || dialogueIndex >= currentDialogue.length) {
    endDialogue();
    return;
  }
  
  const line = currentDialogue[dialogueIndex];
  
  if (line.choices) {
    // Show choices menu
    const choices = line.choices.map((choice, i) => ({
      label: choice.text,
      onSelect: () => {
        playSound(SOUNDS.select);
        if (choice.action) {
          choice.action();
        }
        dialogueIndex++;
        advanceDialogue();
      }
    }));
    
    openMenu({
      title: line.speaker || 'Choice',
      items: choices
    });
  } else {
    // Speak the line
    say(line.text, { interrupt: true });
    dialogueIndex++;
    
    // Auto-advance after delay
    setTimeout(() => {
      advanceDialogue();
    }, line.text.length * 50 + 1000);
  }
}

export function endDialogue() {
  currentDialogue = null;
  dialogueIndex = 0;
  closeMenu();
}

export function isInDialogue() {
  return currentDialogue !== null;
}
